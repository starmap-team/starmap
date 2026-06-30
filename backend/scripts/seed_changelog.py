
"""Seed changelog entries into PostgreSQL for evolution demo."""
import asyncio
from datetime import datetime, timedelta

from app.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

CHANGELOG_ENTRIES = [
    {
        "position": "AI\u7b97\u6cd5\u5de5\u7a0b\u5e08",
        "changes": [
            {"skill": "LLM", "action": "added", "old_value": None, "new_value": "required", "source": "BOSS\u76f4\u8058+\u62c9\u52fe JD\u878d\u5408", "confidence": 0.92},
            {"skill": "RAG", "action": "added", "old_value": None, "new_value": "required", "source": "\u591a\u6e90JD\u878d\u5408", "confidence": 0.88},
            {"skill": "LangChain", "action": "added", "old_value": None, "new_value": "bonus", "source": "\u6280\u672f\u535a\u5ba2\u9891\u7387\u5206\u6790", "confidence": 0.85},
            {"skill": "Python", "action": "updated", "old_value": "0.7", "new_value": "0.9", "source": "JD\u9891\u7387\u7edf\u8ba1", "confidence": 0.95},
        ],
    },
    {
        "position": "\u524d\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08",
        "changes": [
            {"skill": "TypeScript", "action": "added", "old_value": None, "new_value": "required", "source": "BOSS\u76f4\u8058JD\u7edf\u8ba1", "confidence": 0.93},
            {"skill": "React", "action": "updated", "old_value": "0.7", "new_value": "0.85", "source": "JD\u9891\u7387\u5206\u6790", "confidence": 0.90},
            {"skill": "Tailwind CSS", "action": "added", "old_value": None, "new_value": "bonus", "source": "\u62c9\u52feJD\u63d0\u53d6", "confidence": 0.82},
        ],
    },
    {
        "position": "\u6570\u636e\u5de5\u7a0b\u5e08",
        "changes": [
            {"skill": "Spark", "action": "updated", "old_value": "0.6", "new_value": "0.8", "source": "JD\u9891\u7387\u7edf\u8ba1", "confidence": 0.88},
            {"skill": "Flink", "action": "added", "old_value": None, "new_value": "required", "source": "\u591a\u6e90\u878d\u5408", "confidence": 0.86},
            {"skill": "dbt", "action": "added", "old_value": None, "new_value": "bonus", "source": "\u6280\u672f\u535a\u5ba2\u5206\u6790", "confidence": 0.78},
        ],
    },
    {
        "position": "\u540e\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08",
        "changes": [
            {"skill": "Go", "action": "added", "old_value": None, "new_value": "bonus", "source": "BOSS\u76f4\u8058\u7edf\u8ba1", "confidence": 0.84},
            {"skill": "Microservices", "action": "updated", "old_value": "0.5", "new_value": "0.75", "source": "JD\u878d\u5408\u5206\u6790", "confidence": 0.89},
        ],
    },
    {
        "position": "\u8fd0\u7ef4\u5de5\u7a0b\u5e08",
        "changes": [
            {"skill": "Kubernetes", "action": "updated", "old_value": "0.7", "new_value": "0.9", "source": "JD\u9891\u7387\u7edf\u8ba1", "confidence": 0.91},
            {"skill": "Terraform", "action": "added", "old_value": None, "new_value": "required", "source": "\u591a\u6e90\u878d\u5408", "confidence": 0.87},
            {"skill": "Prometheus", "action": "added", "old_value": None, "new_value": "bonus", "source": "\u6280\u672f\u535a\u5ba2\u5206\u6790", "confidence": 0.80},
        ],
    },
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        for entry in CHANGELOG_ENTRIES:
            now = datetime.utcnow()
            for i, change in enumerate(entry["changes"]):
                ts = now - timedelta(days=len(entry["changes"]) - i)
                await session.execute(
                    text("""
                        INSERT INTO evolution_changelog (position_name, skill_name, change_action, old_value, new_value, source, confidence, detected_at)
                        VALUES (:pos, :skill, :action, :old_val, :new_val, :source, :conf, :ts)
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "pos": entry["position"],
                        "skill": change["skill"],
                        "action": change["action"],
                        "old_val": change.get("old_value"),
                        "new_val": change.get("new_value"),
                        "source": change.get("source", ""),
                        "conf": change.get("confidence", 0.8),
                        "ts": ts,
                    },
                )
        await session.commit()
        print(f"Seeded {sum(len(e['changes']) for e in CHANGELOG_ENTRIES)} changelog entries")


if __name__ == "__main__":
    asyncio.run(seed())
