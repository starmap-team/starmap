"""Phase 3.8.9: 注入 mock JD 数据 + 验证 import 闭环"""
import asyncio
import uuid
from datetime import datetime

from sqlalchemy import text

from app.db.session import get_session_factory

MOCK_JDS = [
 {
 "job_title": "Python 后端工程师",
 "company": "字节跳动",
 "salary_min": 25,
 "salary_max": 50,
 "location": "北京",
 "publish_date": "2026-07-15",
 "raw_html": "<div>Python 后端工程师 — 字节跳动 — 25K-50K — 北京</div>",
 "clean_text": "Python 后端工程师 — 字节跳动 — 25K-50K — 北京。负责服务端开发, 熟悉 Django/Flask。",
 "source_site": "bosszhipin",
 "source_url": f"https://www.zhipin.com/job/{uuid.uuid4}.html",
 },
 {
 "job_title": "Java 开发工程师",
 "company": "腾讯",
 "salary_min": 20,
 "salary_max": 40,
 "location": "深圳",
 "publish_date": "2026-07-14",
 "raw_html": "<div>Java 开发工程师 — 腾讯 — 20K-40K — 深圳</div>",
 "clean_text": "Java 开发工程师 — 腾讯 — 20K-40K — 深圳。Spring Boot/MySQL/Redis。",
 "source_site": "bosszhipin",
 "source_url": f"https://www.zhipin.com/job/{uuid.uuid4}.html",
 },
 {
 "job_title": "前端工程师 (React)",
 "company": "阿里巴巴",
 "salary_min": 22,
 "salary_max": 45,
 "location": "杭州",
 "publish_date": "2026-07-13",
 "raw_html": "<div>前端 React — 阿里巴巴 — 22K-45K — 杭州</div>",
 "clean_text": "前端 React — 阿里巴巴 — 22K-45K — 杭州。TypeScript/Next.js。",
 "source_site": "lagou",
 "source_url": f"https://www.lagou.com/jobs/{uuid.uuid4}.html",
 },
 {
 "job_title": "数据分析师",
 "company": "美团",
 "salary_min": 18,
 "salary_max": 35,
 "location": "北京",
 "publish_date": "2026-07-12",
 "raw_html": "<div>数据分析师 — 美团 — 18K-35K — 北京</div>",
 "clean_text": "数据分析师 — 美团 — 18K-35K — 北京。SQL/Python/Tableau。",
 "source_site": "51job",
 "source_url": f"https://jobs.51job.com/{uuid.uuid4}.html",
 },
 {
 "job_title": "全栈工程师",
 "company": "小米",
 "salary_min": 20,
 "salary_max": 40,
 "location": "北京",
 "publish_date": "2026-07-11",
 "raw_html": "<div>全栈工程师 — 小米 — 20K-40K — 北京</div>",
 "clean_text": "全栈工程师 — 小米 — 20K-40K — 北京。React + Node.js + Python。",
 "source_site": "bosszhipin",
 "source_url": f"https://www.zhipin.com/job/{uuid.uuid4}.html",
 },
]

async def inject:
 """直接 INSERT 到 jd_raw, 跳过爬虫."""
 sm = get_session_factory
 inserted = 0
 async with sm as session:
 async with session.begin:
 for jd in MOCK_JDS:
 # gen_random_uuid
 await session.execute(text("""
 INSERT INTO jd_raw (
 source_site, source_url, raw_html, clean_text,
 job_title, company, salary_min, salary_max, location,
 publish_date, crawled_at, content_hash, status
 ) VALUES (
 :site, :url, :html, :text,
 :title, :company, :smin, :smax, :loc,
 :pdate, NOW, :hash, 'raw'::jd_status
 )
 """), {
 "site": jd["source_site"],
 "url": jd["source_url"],
 "html": jd["raw_html"],
 "text": jd["clean_text"],
 "title": jd["job_title"],
 "company": jd["company"],
 "smin": jd["salary_min"] * 1000,
 "smax": jd["salary_max"] * 1000,
 "loc": jd["location"],
 "pdate": datetime.fromisoformat(jd["publish_date"]).date,
 "hash": str(uuid.uuid4),
 })
 inserted += 1
 print(f"Injected {inserted} mock JDs to jd_raw")
 return inserted

if __name__ == "__main__":
 asyncio.run(inject)
