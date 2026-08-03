"""REAL end-to-end pipeline test:
1. Clear raw_jd_records (so we know all new data is from real v2ex)
2. Run v2ex_remote.run_sync() directly against the real internet
3. Feed each item into dao.upsert_jd() (what executor.execute_crawl does)
4. Verify raw_jd_records has source_platform='v2ex' rows
5. Print result summary
"""
import asyncio
import os
import socket
import sys
import time

sys.path.insert(0, '.')
os.environ.setdefault('APP_ENV', 'development')

from crawler.persistence import dao
from crawler.spiders.v2ex_remote import run_sync as v2ex_run


def check_internet():
    """Quick probe: is the box actually able to reach v2ex.com today?"""
    try:
        socket.create_connection(("www.v2ex.com", 443), timeout=5)
        return True
    except (TimeoutError, OSError, ConnectionRefusedError) as e:
        return e


async def main():
    print("=== Internet reachability probe ===")
    reach = check_internet()
    print(f"v2ex.com reachable: {reach}")

    print("\n=== Clear raw_jd_records (isolated clean-slate) ===")
    from sqlalchemy import delete

    from app.db.session import get_session_factory
    from app.models.extraction_models import RawJDRecord
    sf = get_session_factory()
    async with sf() as s:
        async with s.begin():
            dres = await s.execute(delete(RawJDRecord))
            print(f"deleted {dres.rowcount} raw_jd_records rows")

    print("\n=== Direct spider call: run_sync(keyword='python', max_count=5) ===")
    t0 = time.monotonic()
    items = v2ex_run(keyword="python", max_count=5)
    elapsed = time.monotonic() - t0
    print(f"spider returned {len(items)} items in {elapsed:.2f}s")
    if not items:
        print("!!! spider returned ZERO items. Check network or spider source.\n")
    for it in items[:5]:
        print(f"  - {it['source_site']:8} | {it['job_title'][:60]} | url={it['source_url'][:55]}")

    print("\n=== Persist via dao.upsert_jd (matches executor.execute_crawl) ===")
    inserted = 0
    duplicates = 0
    failed = 0
    from crawler.persistence.models import JdStatus
    for it in items:
        try:
            rec = {
                "source_site": it["source_site"],
                "source_url": it["source_url"],
                "raw_html": it.get("raw_html", ""),
                "clean_text": it.get("clean_text", ""),
                "job_title": it.get("job_title", "未命名")[:200],
                "company": it.get("company", ""),
                "salary_min": it.get("salary_min", 0),
                "salary_max": it.get("salary_max", 0),
                "location": it.get("location", ""),
                "publish_date": it.get("publish_date", ""),
                "content_hash": it.get("content_hash", ""),
                "status": JdStatus.raw.value if hasattr(JdStatus, 'raw') else "raw",
            }
            result = dao.upsert_jd(rec)
            label = "inserted" if result == "inserted" else ("duplicate" if result == "duplicate" else result)
            if result == "inserted":
                inserted += 1
            elif result == "duplicate":
                duplicates += 1
            else:
                failed += 1
            print(f"  {label:9} | {it['source_site']:8} | {rec['job_title'][:50]}")
        except Exception as e:
            failed += 1
            print(f"  FAILED    | {it.get('source_site', '?')} | {e}")

    print("\n=== Final summary ===")
    print(f"  spider items returned : {len(items)}")
    print(f"  inserted (raw)        : {inserted}")
    print(f"  duplicates (raw)      : {duplicates}")
    print(f"  failed                : {failed}")

    print("\n=== DB distribution check ===")
    async with sf() as s:
        from sqlalchemy import func, select
        rows = (await s.execute(select(RawJDRecord.source_platform, func.count(RawJDRecord.id)).group_by(RawJDRecord.source_platform))).all()
        for p, c in rows:
            print(f"  source_platform={p!r}  count={c}")

    print("\n=== Sample real v2ex record (first 400 chars of clean_text) ===")
    async with sf() as s:
        from sqlalchemy import select
        r = (await s.execute(select(RawJDRecord).where(RawJDRecord.source_platform == "v2ex").limit(1))).scalar_one_or_none()
        if r:
            print(f"  id={r.id}  title={r.job_title[:60]}")
            print(f"  clean_text[:400]: {(r.clean_text or '')[:400]}")
        else:
            print("  no v2ex rows in DB")


asyncio.run(main())
