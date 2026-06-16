"""M1 验收脚本：建表 + 生成 300 条 mock 数据 + 验证查询。"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
sys.path.insert(0, str(ROOT))

from crawler.config import KEYWORDS  # noqa: E402
from crawler.dedup import hex64, simhash  # noqa: E402
from crawler.persistence import dao  # noqa: E402
from crawler.persistence.models import JdStatus  # noqa: E402
from crawler.persistence.database import get_jd_raw_session  # noqa: E402
from sqlalchemy import select, func  # noqa: E402
from crawler.persistence.models import JdRaw, ComplianceLog  # noqa: E402


SITES = ["lagou", "51job", "bosszhipin"]
CITIES = ["北京", "上海", "深圳", "杭州", "广州", "成都", "南京", "武汉"]
COMPANIES = ["字节跳动", "腾讯", "阿里", "美团", "京东", "小米", "华为", "网易", "百度", "滴滴"]
SKILL_POOL = [
    "Python", "Java", "Go", "JavaScript", "TypeScript", "React", "Vue",
    "Spring Boot", "MySQL", "Redis", "Kafka", "Docker", "Kubernetes",
    "PyTorch", "TensorFlow", "NLP", "大模型微调", "RAG", "知识图谱",
    "Neo4j", "Elasticsearch", "MongoDB", "GraphQL", "微服务", "CI/CD",
]


def gen_jd(site: str, idx: int) -> dict:
    kw = random.choice(KEYWORDS)
    company = random.choice(COMPANIES)
    city = random.choice(CITIES)
    salary_min = random.choice([15, 20, 25, 30, 40, 50]) * 1000
    salary_max = salary_min + random.choice([5, 10, 20, 30]) * 1000
    skills = random.sample(SKILL_POOL, k=random.randint(3, 8))
    title_prefix = random.choice(["高级", "资深", "中级", "初级", "Lead"])
    job_title = f"{title_prefix}{kw}工程师"

    body = (
        f"{company} 诚招 {job_title}（{city}）\n\n"
        f"薪资：{salary_min // 1000}K-{salary_max // 1000}K · {random.randint(13, 16)}薪\n\n"
        "【岗位职责】\n"
        "1. 负责核心业务模块的设计与开发\n"
        "2. 跟进业界前沿技术并落地\n"
        "3. 参与技术方案评审与 code review\n\n"
        "【任职要求】\n"
        f"1. 熟练掌握：{' / '.join(skills)}\n"
        "2. 计算机基础扎实（数据结构、算法、网络、操作系统）\n"
        "3. 良好的沟通协作能力\n"
    )

    return {
        "source_site": site,
        "source_url": f"https://mock.{site}.com/job/{idx:05d}",
        "raw_html": f"<html><body><h1>{job_title}</h1><pre>{body}</pre></body></html>",
        "clean_text": body,
        "job_title": job_title,
        "company": company,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "location": city,
        "publish_date": date.today() - timedelta(days=random.randint(0, 30)),
        "content_hash": hex64(simhash(body)),
        "status": JdStatus.raw,
    }


def seed(target: int = 300) -> dict:
    """每个站点均分 target 条。"""
    per_site = target // len(SITES)
    inserted_total = 0
    duplicate_total = 0
    failed_total = 0
    for site in SITES:
        for i in range(per_site):
            rec = gen_jd(site, i)
            r = dao.upsert_jd(rec)
            if r == "inserted":
                inserted_total += 1
            elif r == "duplicate":
                duplicate_total += 1
            else:
                failed_total += 1
    return {
        "inserted": inserted_total,
        "duplicate": duplicate_total,
        "failed": failed_total,
        "total": inserted_total + duplicate_total,
    }


def stats() -> dict:
    with get_jd_raw_session() as s:
        total = s.scalar(select(func.count(JdRaw.id))) or 0
        by_site = dict(
            s.execute(
                select(JdRaw.source_site, func.count(JdRaw.id)).group_by(JdRaw.source_site)
            ).all()
        )
        by_status = dict(
            s.execute(
                select(JdRaw.status, func.count(JdRaw.id)).group_by(JdRaw.status)
            ).all()
        )
        compliance_total = s.scalar(select(func.count(ComplianceLog.id))) or 0
    return {
        "total": total,
        "by_site": {k: v for k, v in by_site.items()},
        "by_status": {k.value: v for k, v in by_status.items()},
        "compliance_log_total": compliance_total,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--target", type=int, default=300)
    p.add_argument("--seed", action="store_true", help="建表+灌 mock 数据")
    args = p.parse_args()

    if args.seed:
        print(">>> 建表 ...")
        dao.init_schema()
        print(">>> 灌 mock 数据 ...")
        r = seed(target=args.target)
        print(json.dumps(r, ensure_ascii=False, indent=2))

    print(">>> 统计 ...")
    s = stats()
    print(json.dumps(s, ensure_ascii=False, indent=2))
