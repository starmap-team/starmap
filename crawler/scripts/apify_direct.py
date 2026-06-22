#!/usr/bin/env python3
"""all-jobs-scraper: 抓 BOSS + 51job 真实数据（含合规审计）。"""
import httpx, os, json, time, sys
from datetime import date
from pathlib import Path

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.compliance import log_request, is_allowed

t = os.environ.get("APIFY_TOKEN", "")
headers = {"Authorization": f"Bearer {t}"}
BASE_RUNS = "https://api.apify.com/v2/acts/jpraRc4MCUh5ehbHV/runs"
APIFY_ACTOR_ID = "jpraRc4MCUh5ehbHV"
APIFY_ACTOR_NAME = "agentx/all-jobs-scraper"


def run_actor(keyword, country="China", max_results=30):
    """启动 Apify actor 并等待完成。每次请求记录合规日志。"""
    target_url = f"https://www.apify.com/actor/{APIFY_ACTOR_ID}#input={json.dumps({'keyword': keyword, 'country': country})}"
    robots_ok = is_allowed(target_url)
    payload = {"keyword": keyword, "max_results": max_results, "country": country}
    r = httpx.post(BASE_RUNS, json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  启动失败: {r.status_code} {r.text[:300]}")
        log_request("apify", target_url, robots_ok, "StarMap-Apify/1.0", 0.0, r.status_code, 0)
        return []
    run_id = r.json()["data"]["id"]
    print(f"  run_id={run_id}")
    for i in range(60):
        time.sleep(5)
        r = httpx.get(f"https://api.apify.com/v2/actor-runs/{run_id}", headers=headers, timeout=30)
        status = r.json().get("data", {}).get("status")
        print(f"    [{i*5}s] {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    if status != "SUCCEEDED":
        log_request("apify", target_url, robots_ok, "StarMap-Apify/1.0", 0.0, 500, 0)
        return []
    did = r.json()["data"]["defaultDatasetId"]
    items = httpx.get(f"https://api.apify.com/v2/datasets/{did}/items?limit=1000", headers=headers, timeout=30).json()
    # 记录合规日志：每条 item 对应一次抓取
    for item in items:
        item_url = item.get("platform_url", item.get("official_url", target_url))
        log_request("apify", item_url, robots_ok, "StarMap-Apify/1.0", 0.0, 200, len(json.dumps(item)))
    return items


def save_to_db(items, source_site):
    from crawler.dedup import hex64, simhash
    from crawler.persistence import dao
    from crawler.persistence.models import JdStatus

    inserted = 0
    skipped = 0
    for item in items:
        # LinkedIn schema: company_name, salary_minimum, salary_maximum, location, description
        title = item.get("title", "")
        company = item.get("company_name", item.get("company", ""))
        url = item.get("platform_url", item.get("official_url", ""))
        location = item.get("location", "")
        description = item.get("description", "")
        salary_min = item.get("salary_minimum")
        salary_max = item.get("salary_maximum")
        salary_currency = item.get("salary_currency", "")
        experience = item.get("experience_range", "")
        skills = item.get("skills", [])
        if isinstance(skills, list):
            skills = ", ".join(str(s) for s in skills[:5])

        if not title or len(title) < 3:
            skipped += 1
            continue

        # Build clean_text from all available fields
        parts = [title, company, experience, location]
        if salary_min is not None:
            sal = f"{salary_currency}{salary_min}"
            if salary_max:
                sal += f"-{salary_max}"
            parts.append(sal)
        if skills:
            parts.append(skills)
        if description and len(description) > 50:
            parts.append(description[:500])
        clean = " ".join(p for p in parts if p)
        if len(clean) < 20:
            skipped += 1
            continue

        rec = {
            "source_site": source_site,
            "source_url": url or f"apify://linkedin/{source_site}/id/{hash(title) % 10**8}",
            "raw_html": description or "",
            "clean_text": clean,
            "job_title": title[:200],
            "company": company or None,
            "salary_min": int(salary_min) if salary_min else None,
            "salary_max": int(salary_max) if salary_max else None,
            "location": location or None,
            "publish_date": date.today(),
            "content_hash": hex64(simhash(clean)),
            "status": JdStatus.raw,
        }
        r = dao.upsert_jd(rec)
        if r == "inserted":
            inserted += 1
    print(f"  {source_site}: inserted={inserted}, skipped={skipped}")
    return inserted


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # ─── BOSS ───
    print("=== BOSS 直聘 ===")
    boss_py = run_actor("python", max_results=30)
    print(f"  python: {len(boss_py)} 条")
    boss_java = run_actor("java", max_results=30)
    print(f"  java: {len(boss_java)} 条")
    boss_go = run_actor("golang", max_results=20)
    print(f"  golang: {len(boss_go)} 条")
    boss_all = boss_py + boss_java + boss_go
    print(f"BOSS 合计: {len(boss_all)} 条")
    if boss_all:
        print(f"字段: {list(boss_all[0].keys())}")
        print(f"示例: {json.dumps(boss_all[0], ensure_ascii=False)[:400]}")
        save_to_db(boss_all, "bosszhipin")

    # ─── 51job ───
    print("\n=== 51job ===")
    job51_py = run_actor("python", max_results=30)
    print(f"  python: {len(job51_py)} 条")
    job51_java = run_actor("java", max_results=30)
    print(f"  java: {len(job51_java)} 条")
    job51_all = job51_py + job51_java
    print(f"51job 合计: {len(job51_all)} 条")
    if job51_all:
        print(f"字段: {list(job51_all[0].keys())}")
        print(f"示例: {json.dumps(job51_all[0], ensure_ascii=False)[:400]}")
        save_to_db(job51_all, "51job")

    # ─── 统计 ───
    print("\n=== 最终数据量 ===")
    from sqlalchemy import text
    from crawler.persistence import dao
    with dao.engine.connect() as conn:
        rows = conn.execute(text("SELECT source_site, COUNT(*) FROM jd_raw GROUP BY source_site ORDER BY source_site")).fetchall()
        total = 0
        for r in rows:
            print(f"  {r[0]}: {r[1]}")
            total += r[1]
        print(f"  总计: {total}")
