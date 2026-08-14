"""Seed synthetic evolution snapshots spanning the last 14 days.

QA Stage 3.5 + B4: when real materialised snapshots don't yet exist, seed
14 daily derived rows per demo position so /evolution/snapshots returns a
non-empty time series immediately.
"""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import get_session_factory

# 每个演示岗位的代表性技能（演示快照无需真实演化明细）
DEMO_POSITIONS: dict[str, list[dict[str, str]]] = {
    "大模型应用工程师": [
        {"name": "LLM", "proficiency": "advanced"},
        {"name": "RAG", "proficiency": "advanced"},
        {"name": "Prompt Engineering", "proficiency": "advanced"},
    ],
    "Java 开发工程师": [
        {"name": "Java", "proficiency": "advanced"},
        {"name": "Spring Boot", "proficiency": "advanced"},
    ],
    "前端开发工程师": [
        {"name": "JavaScript", "proficiency": "advanced"},
        {"name": "Vue.js", "proficiency": "advanced"},
    ],
    "数据分析师": [
        {"name": "SQL", "proficiency": "advanced"},
        {"name": "Python", "proficiency": "advanced"},
    ],
}


async def seed() -> None:
    """Best-effort demo seeding.

    Idempotent: skips (position_name, snapshot_date) 已存在的行。
    """
    try:
        from app.models.evolution_models import EvolutionSnapshot  # type: ignore
    except ImportError:
        print("  - skip: EvolutionSnapshot model not available (run migrations first)")
        return

    sf = get_session_factory()
    base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    inserted = 0
    async with sf() as session:
        for position, skills in DEMO_POSITIONS.items():
            for offset in range(14):
                day = base - timedelta(days=offset)
                existing = (
                    await session.execute(
                        select(EvolutionSnapshot.id)
                        .where(EvolutionSnapshot.position_name == position)
                        .where(EvolutionSnapshot.snapshot_date == day)
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if existing:
                    print(f"  - skip: snapshot {position} {day.date()} exists")
                    continue
                session.add(EvolutionSnapshot(
                    position_name=position,
                    snapshot_date=day,
                    required_skills=skills,
                    preferred_skills=[],
                    source_count=random.randint(2, 8),
                    metadata_json={"seed": True, "demo": True},
                    created_at=datetime.now(UTC),
                ))
                inserted += 1
                print(f"  + insert: snapshot {position} {day.date()}")
        await session.commit()
    print(f"  seeded {inserted} evolution snapshots")


if __name__ == "__main__":
    asyncio.run(seed())
