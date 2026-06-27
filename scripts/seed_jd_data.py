"""Seed PostgreSQL with sample JD records for demo."""
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SAMPLE_JDS = [
    {
        "title": "大模型应用工程师",
        "jd": "岗位：大模型应用工程师\n要求：精通Python、LangChain、RAG、Prompt Engineering、Fine-tuning、LLM；熟悉LlamaIndex、ChromaDB、OpenAI API、PyTorch；3年经验；硕士",
        "skills": {"required": ["Python", "LangChain", "RAG", "Prompt Engineering", "Fine-tuning", "LLM"], "preferred": ["LlamaIndex", "ChromaDB", "OpenAI API", "PyTorch"]},
        "exp": 3, "edu": "硕士",
    },
    {
        "title": "高级后端工程师",
        "jd": "岗位：高级后端工程师\n要求：精通Python、FastAPI、PostgreSQL、Docker、Kubernetes；熟悉Redis、Celery；5年经验；本科",
        "skills": {"required": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"], "preferred": ["Redis", "Celery", "Nginx"]},
        "exp": 5, "edu": "本科",
    },
    {
        "title": "前端开发工程师",
        "jd": "岗位：前端开发工程师\n要求：精通JavaScript、TypeScript、Vue.js、HTML5、CSS3；熟悉React、Vite；3年经验；本科",
        "skills": {"required": ["JavaScript", "TypeScript", "Vue.js", "HTML5", "CSS3"], "preferred": ["React", "Vite", "Webpack", "Tailwind CSS"]},
        "exp": 3, "edu": "本科",
    },
    {
        "title": "数据工程师",
        "jd": "岗位：数据工程师\n要求：精通Python、SQL、Spark、Kafka；熟悉Flink、Airflow；3年经验；本科",
        "skills": {"required": ["Python", "SQL", "Spark", "Kafka", "Airflow"], "preferred": ["Flink", "ClickHouse", "Snowflake"]},
        "exp": 3, "edu": "本科",
    },
    {
        "title": "DevOps工程师",
        "jd": "岗位：DevOps工程师\n要求：精通Docker、Kubernetes、Terraform、CI/CD、Prometheus；熟悉Ansible、Grafana；3年经验；本科",
        "skills": {"required": ["Docker", "Kubernetes", "Terraform", "CI/CD", "Prometheus"], "preferred": ["Ansible", "Grafana", "Helm", "Jenkins"]},
        "exp": 3, "edu": "本科",
    },
    {
        "title": "AI算法工程师",
        "jd": "岗位：AI算法工程师\n要求：精通Python、PyTorch、TensorFlow、scikit-learn、Hugging Face；5年经验；硕士",
        "skills": {"required": ["Python", "PyTorch", "TensorFlow", "scikit-learn", "Hugging Face"], "preferred": ["OpenCV", "CUDA", "MLflow"]},
        "exp": 5, "edu": "硕士",
    },
    {
        "title": "安全工程师",
        "jd": "岗位：安全工程师\n要求：精通Python、渗透测试、SIEM、Kubernetes、云安全；3年经验；本科",
        "skills": {"required": ["Python", "Penetration Testing", "SIEM", "Kubernetes", "Cloud Security"], "preferred": ["OWASP", "Burp Suite", "Nmap"]},
        "exp": 3, "edu": "本科",
    },
]


async def seed_jds():
    pg_uri = sys.argv[1] if len(sys.argv) > 1 else "postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap"
    engine = create_async_engine(pg_uri, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(text("SELECT count(*) FROM raw_jd_records"))
        count = result.scalar()
        if count and count > 0:
            print(f"Already {count} JD records, skipping.")
            return

        now = datetime.now(UTC)
        jd_ids = []
        for jd in SAMPLE_JDS:
            jd_id = uuid4()
            jd_ids.append((jd_id, jd))
            content_hash = hashlib.sha256(jd["jd"].encode()).hexdigest()[:64]
            await session.execute(
                text("""INSERT INTO raw_jd_records (id, source_url, source_platform, raw_text, title_raw, crawl_time, hash_dedup, status)
                        VALUES (:id, :url, :platform, :raw, :title, :crawl, :hash, :status)"""),
                {"id": jd_id, "url": f"seed://{jd['title']}", "platform": "seed", "raw": jd["jd"],
                 "title": jd["title"], "crawl": now, "hash": content_hash, "status": "completed"},
            )
        await session.flush()

        for jd_id, jd in jd_ids:
            all_skills = []
            for s in jd["skills"]["required"]:
                all_skills.append({"skill": s, "category": "hard_skill", "proficiency": "熟悉", "type": "required"})
            for s in jd["skills"]["preferred"]:
                all_skills.append({"skill": s, "category": "hard_skill", "proficiency": "了解", "type": "preferred"})
            await session.execute(
                text("""INSERT INTO jd_extraction_records
                        (id, jd_content, job_title, extracted_skills, experience_years, education, confidence, hallucination_score, created_at, status)
                        VALUES (:id, :jd, :title, :skills, :exp, :edu, :conf, :hall, :created, :status)"""),
                {"id": uuid4(), "jd": jd["jd"], "title": jd["title"], "skills": json.dumps(all_skills, ensure_ascii=False),
                 "exp": jd["exp"], "edu": jd["edu"], "conf": 0.87, "hall": 0.05, "created": now, "status": "completed"},
            )

        await session.commit()

        result = await session.execute(text("SELECT count(*) FROM raw_jd_records"))
        print(f"Seeded {result.scalar()} JD records")
        result = await session.execute(text("SELECT count(*) FROM jd_extraction_records"))
        print(f"Seeded {result.scalar()} extraction records")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_jds())