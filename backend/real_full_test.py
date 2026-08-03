"""REAL end-to-end with qwen2.5:7b:
1. Fetch v2ex + remotive LIVE
2. Run extract_from_jd via local Qwen (no MiMo)
3. Persist JDExtractionRecord
4. Run orchestrator
5. Verify evolution API endpoints return data
"""
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, '.')
for k, v in {
    'APP_ENV': 'development', 'POSTGRES_HOST': 'localhost',
    'POSTGRES_PORT': '5433', 'POSTGRES_USER': 'starmap',
    'POSTGRES_PASSWORD': 'starmap123456', 'POSTGRES_DB': 'starmap',
    'REDIS_URI': 'redis://localhost:6379/0',
    'NEO4J_URI': 'bolt://localhost:7687', 'NEO4J_USER': 'neo4j',
    'NEO4J_PASSWORD': 'starmap123456',
    'QWEN_MODEL_PATH': 'http://localhost:11434',
    'MIMO_API_KEY': '', 'MIMO_API_BASE': '',
    'DEEPSEEK_API_KEY': '',
    'XUNFEI_API_KEY': '',
}.items():
    os.environ.setdefault(k, v)
try:
    from dotenv import load_dotenv
    if Path(__file__).parent / '.env':
        load_dotenv(dotenv_path=str(Path(__file__).parent / '.env'), override=False)
except Exception:
    pass

from crawler.spiders.v2ex_remote import run_sync as v2ex_run
from sqlalchemy import func, select

from app.core.evolution.orchestrator import run_evolution_pipeline
from app.core.extraction.jd_extract import extract_from_jd
from app.db.session import get_session_factory
from app.models.extraction_models import JDExtractionRecord, RawJDRecord


async def main():
    sf = get_session_factory()

    # ─── Step 1: live internet crawl (already proven, reconfirm) ───
    print("=" * 70)
    print("STEP 1: real internet crawl (v2ex + remotive)")
    print("=" * 70)
    items = v2ex_run(keyword="python", max_count=5)
    print(f"  spider returned {len(items)} items in live HTTP")
    if not items:
        print("ABORT: no items from v2ex")
        return
    for i, it in enumerate(items[:3]):
        print(f"    [{i}] {it['source_site']:8} | {it['job_title'][:50]}")

    # ─── Step 2: persist to raw_jd_records ───
    print("\n" + "=" * 70)
    print("STEP 2: persist to raw_jd_records (live v2ex data)")
    print("=" * 70)
    from datetime import UTC, datetime
    async with sf() as s:
        n_pre_raw = (await s.execute(select(func.count(RawJDRecord.id)))).scalar() or 0
        print(f"  pre-count: {n_pre_raw}")
        inserted_raw = 0
        for it in items:
            h = it.get("content_hash") or hashlib.sha256(it.get("source_url", "").encode()).hexdigest()[:64]
            existing = (await s.execute(
                select(RawJDRecord).where(RawJDRecord.hash_dedup == h)
            )).scalar_one_or_none()
            if existing:
                continue
            row = RawJDRecord(
                source_platform=it.get("source_site", "v2ex")[:50],
                source_url=it.get("source_url", "")[:512],
                raw_text=(it.get("raw_html") or it.get("clean_text") or "")[:50000],
                title_raw=(it.get("job_title") or "未命名")[:255],
                company_name=(it.get("company") or "")[:255],
                crawl_time=datetime.now(UTC),
                hash_dedup=h,
                status="raw",
            )
            s.add(row)
            inserted_raw += 1
        await s.commit()
        n_post_raw = (await s.execute(select(func.count(RawJDRecord.id)))).scalar() or 0
        print(f"  inserted={inserted_raw}, post-count={n_post_raw}")

    # ─── Step 3: real LLM extraction with qwen2.5:7b ───
    print("\n" + "=" * 70)
    print("STEP 3: real LLM extract via qwen2.5:7b (no MiMo)")
    print("=" * 70)
    async with sf() as s:
        recs = (await s.execute(
            select(RawJDRecord).order_by(RawJDRecord.id.asc()).limit(5)
        )).scalars().all()

    n_real_extractions = 0
    for rec in recs:
        text = (rec.raw_text or "")[:6000]
        if not text.strip():
            print(f"  skip empty raw (id={rec.id})")
            continue
        print(f"\n  extract {rec.title_raw[:60]!r} ({len(text)} chars)")
        t0 = time.monotonic()
        try:
            r = await extract_from_jd(text, options={"skip_anti_hallucination": False})
            elapsed = time.monotonic() - t0
            print(f"    LLM call took {elapsed:.1f}s")
            if r.get("success"):
                data = r["data"]
                position_name = data.get("position_name", "?")
                req = data.get("required_skills", [])
                pref = data.get("preferred_skills", [])
                val = data.get("validation", {})
                print(f"    LLM output: position={position_name[:50]}")
                print(f"    LLM output: required_skills ({len(req)})  preferred_skills ({len(pref)})")
                print(f"    LLM output: confidence={val.get('confidence', '?')} hallucinated={len(val.get('hallucinated_skills', []))} missing={len(val.get('missing_skills', []))}")
                if req or pref:
                    # Persist as JDExtractionRecord
                    async with sf() as s2:
                        s2.add(JDExtractionRecord(
                            jd_content=text[:50000],
                            job_title=position_name[:255],
                            extracted_skills=data,
                            experience_years=data.get("experience_required"),
                            education=data.get("education_required"),
                            confidence=float(val.get("confidence", 0.85) or 0.85),
                            hallucination_score=float(val.get("hallucination_score", 0.05) or 0.05) if "hallucination_score" in val else 0.05,
                            status="completed",
                        ))
                        await s2.commit()
                        n_real_extractions += 1
                        print("    PERSISTED -> JDExtractionRecord")
        except Exception as e:
            print(f"    FAIL: {type(e).__name__}: {e}")

    print(f"\n  total real-LLM-driven extractions persisted: {n_real_extractions}")

    # ─── Step 4: orchestrator (uses both fixture + real data) ───
    print("\n" + "=" * 70)
    print("STEP 4: orchestrator run_evolution_pipeline")
    print("=" * 70)
    result = await run_evolution_pipeline(months_back=6)
    print(f"  positions_processed: {result.get('positions_processed')}")
    print(f"  snapshots_created: {result.get('snapshots_created')}")
    print(f"  changelogs_written: {result.get('changelogs_written')}")
    print(f"  paths_written: {result.get('paths_written')}")
    print(f"  timeseries: {result.get('timeseries')}")
    print(f"  errors: {result.get('errors')}")

    # ─── Step 5: verify evolution API endpoints ───
    print("\n" + "=" * 70)
    print("STEP 5: final API state via :8001")
    print("=" * 70)
    import urllib.request
    req = urllib.request.Request(
        "http://localhost:8001/api/v1/auth/login",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    token = json.loads(urllib.request.urlopen(req).read())["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    for ep in ["snapshots", "paths/all"]:
        url = f"http://localhost:8001/api/v1/evolution/{ep}?limit=10"
        r = urllib.request.Request(url, headers=auth)
        body = urllib.request.urlopen(r).read()
        data = json.loads(body)
        if isinstance(data, list):
            print(f"  {ep:25} : {len(data)} items")
        else:
            print(f"  {ep:25} : 1 item (non-list)")


asyncio.run(main())
