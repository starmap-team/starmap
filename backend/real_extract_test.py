"""REAL LLM extraction end-to-end:
1. Pick the just-crawled V2EX JD (real data)
2. Run extract_from_jd() to LLM-extract skills
3. Verify JDExtractionRecord rows for V2EX-style job titles
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, '.')
for k, v in {
    'APP_ENV': 'development',
    'POSTGRES_HOST': 'localhost', 'POSTGRES_PORT': '5433',
    'POSTGRES_USER': 'starmap', 'POSTGRES_PASSWORD': 'starmap123456',
    'POSTGRES_DB': 'starmap',
    'REDIS_URI': 'redis://localhost:6379/0',
    'NEO4J_URI': 'bolt://localhost:7687',
    'NEO4J_USER': 'neo4j', 'NEO4J_PASSWORD': 'starmap123456',
}.items():
    os.environ.setdefault(k, v)
try:
    from dotenv import load_dotenv
    if Path(__file__).parent / '.env':
        load_dotenv(dotenv_path=str(Path(__file__).parent / '.env'), override=False)
except Exception:
    pass

from sqlalchemy import func, select

from app.core.extraction.jd_extract import extract_from_jd
from app.db.session import get_session_factory
from app.models.extraction_models import JDExtractionRecord, RawJDRecord


async def main():
    sf = get_session_factory()

    print("=== Pre-state ===")
    async with sf() as s:
        n_raw = (await s.execute(select(func.count(RawJDRecord.id)))).scalar() or 0
        n_extr = (await s.execute(select(func.count(JDExtractionRecord.id)))).scalar() or 0
        print(f"  raw_jd_records        : {n_raw}")
        print(f"  jd_extraction_records : {n_extr}")

    print("\n=== Pick first 3 raw records and run LLM extract_from_jd ===")
    async with sf() as s:
        result = await s.execute(select(RawJDRecord).order_by(RawJDRecord.id.asc()).limit(3))
        recs = list(result.scalars())
        for rec in recs:
            text = (rec.raw_text or '')[:6000]
            print(f"\n  source={rec.source_platform} | title={rec.title_raw[:50]} | text_len={len(text)}")
            try:
                r = await extract_from_jd(text, options={})
                if r.get("success"):
                    data = r["data"]
                    req = data.get("required_skills", [])
                    pref = data.get("preferred_skills", [])
                    print(f"    [LLM] position_name: {data.get('position_name', '?')}")
                    print(f"    [LLM] required_skills ({len(req)}):")
                    for sk in req[:5]:
                        nm = sk.get("name", "") if isinstance(sk, dict) else str(sk)
                        print(f"      - {nm}")
                    print(f"    [LLM] preferred_skills ({len(pref)}):")
                    for sk in pref[:3]:
                        nm = sk.get("name", "") if isinstance(sk, dict) else str(sk)
                        print(f"      - {nm}")
                    print(f"    [LLM] confidence: {r['data'].get('validation', {}).get('confidence', '?')}")
                else:
                    print(f"    [LLM FAIL] {r.get('error', '?')}")
            except Exception as e:
                print(f"    [LLM EXC] {type(e).__name__}: {e}")

    print("\n=== Post-state ===")
    async with sf() as s:
        n_raw2 = (await s.execute(select(func.count(RawJDRecord.id)))).scalar() or 0
        n_extr2 = (await s.execute(select(func.count(JDExtractionRecord.id)))).scalar() or 0
        print(f"  raw_jd_records        : {n_raw2}")
        print(f"  jd_extraction_records : {n_extr2}  (delta {n_extr2 - n_extr})")
        # Check what we just extracted
        rows = (await s.execute(
            select(JDExtractionRecord).order_by(JDExtractionRecord.created_at.desc()).limit(3)
        )).scalars().all()
        print("\n  Latest JDExtractionRecord rows:")
        for r in rows:
            extracted = r.extracted_skills or {}
            pos = extracted.get('position_name') or r.job_title
            n_req = len(extracted.get('required_skills', []) or [])
            print(f"    id={str(r.id)[:8]} position='{pos[:40]}' conf={r.confidence:.2f} req_skills={n_req} src=jdextract")

asyncio.run(main())
