"""Seed 5 demo data sources into the data_sources table.

Sources: BOSS直聘, 拉勾网, 51Job, GitHub, ESCO

Usage:
    cd backend && python -m scripts.seed_datasources_demo
"""
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings

DATA_SOURCES = [
    {
        "name": "BOSS直聘",
        "source_type": "crawler",
        "authority_score": 0.92,
        "status": "active",
        "total_records": 48_520,
        "valid_records": 45_613,
        "duplicate_rate": 0.06,
        "avg_quality_score": 0.91,
        "config": {
            "base_url": "https://www.zhipin.com",
            "crawl_interval_hours": 6,
            "max_pages": 200,
            "categories": ["技术", "产品", "设计"],
            "proxy_pool": "default",
        },
    },
    {
        "name": "拉勾网",
        "source_type": "crawler",
        "authority_score": 0.85,
        "status": "active",
        "total_records": 31_207,
        "valid_records": 29_132,
        "duplicate_rate": 0.07,
        "avg_quality_score": 0.87,
        "config": {
            "base_url": "https://www.lagou.com",
            "crawl_interval_hours": 8,
            "max_pages": 150,
            "categories": ["技术", "数据"],
            "anti_bot_delay_ms": 3000,
        },
    },
    {
        "name": "51Job",
        "source_type": "crawler",
        "authority_score": 0.78,
        "status": "active",
        "total_records": 52_891,
        "valid_records": 48_660,
        "duplicate_rate": 0.08,
        "avg_quality_score": 0.82,
        "config": {
            "base_url": "https://www.51job.com",
            "crawl_interval_hours": 12,
            "max_pages": 300,
            "categories": ["全行业"],
        },
    },
    {
        "name": "GitHub",
        "source_type": "api",
        "authority_score": 0.88,
        "status": "active",
        "total_records": 15_342,
        "valid_records": 14_877,
        "duplicate_rate": 0.03,
        "avg_quality_score": 0.93,
        "config": {
            "api_base": "https://api.github.com",
            "rate_limit_per_hour": 5000,
            "repos": [
                "awesome-python",
                "developer-roadmap",
                "free-programming-books",
            ],
            "track_topics": True,
        },
    },
    {
        "name": "ESCO",
        "source_type": "import",
        "authority_score": 0.95,
        "status": "active",
        "total_records": 13_485,
        "valid_records": 13_485,
        "duplicate_rate": 0.0,
        "avg_quality_score": 0.97,
        "config": {
            "version": "v1.2.0",
            "import_format": "csv",
            "locale": "en",
            "skill_groups": ["ICT", "engineering", "data_science"],
        },
    },
]


async def seed() -> None:
    engine = create_async_engine(settings.postgres_uri)
    now = datetime.now(UTC)

    async with AsyncSession(engine) as session:
        for i, src in enumerate(DATA_SOURCES):
            # Stagger last_crawl_at: most recent for first source
            last_crawl = now - timedelta(hours=i * 4 + 1)
            await session.execute(
                text("""
                    INSERT INTO data_sources
                        (id, name, source_type, authority_score, status,
                         last_crawl_at, total_records, valid_records,
                         duplicate_rate, avg_quality_score, config)
                    VALUES
                        (:id, :name, :source_type, :authority_score, :status,
                         :last_crawl_at, :total_records, :valid_records,
                         :duplicate_rate, :avg_quality_score, :config::json)
                    ON CONFLICT (name) DO UPDATE SET
                        authority_score = EXCLUDED.authority_score,
                        status = EXCLUDED.status,
                        last_crawl_at = EXCLUDED.last_crawl_at,
                        total_records = EXCLUDED.total_records,
                        valid_records = EXCLUDED.valid_records,
                        duplicate_rate = EXCLUDED.duplicate_rate,
                        avg_quality_score = EXCLUDED.avg_quality_score,
                        config = EXCLUDED.config
                """),
                {
                    "id": str(uuid.uuid4()),
                    "name": src["name"],
                    "source_type": src["source_type"],
                    "authority_score": src["authority_score"],
                    "status": src["status"],
                    "last_crawl_at": last_crawl.isoformat(),
                    "total_records": src["total_records"],
                    "valid_records": src["valid_records"],
                    "duplicate_rate": src["duplicate_rate"],
                    "avg_quality_score": src["avg_quality_score"],
                    "config": __import__("json").dumps(src["config"]),
                },
            )

        await session.commit()
        print(f"Seeded {len(DATA_SOURCES)} data sources:")
        for src in DATA_SOURCES:
            print(f"  - {src['name']} ({src['source_type']}, auth={src['authority_score']})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
