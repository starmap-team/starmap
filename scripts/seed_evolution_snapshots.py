"""Seed evolution snapshots for all positions in PostgreSQL.

Creates two point-in-time snapshots per position:
- 3 months ago: a simplified skill profile (fewer skills)
- current: the full current skill profile

Requires environment variables or defaults used by the project:
- POSTGRES_URI (default: postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap)

Usage:
  cd starmap
  python scripts/seed_evolution_snapshots.py
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DEFAULT_PG_URI = "postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap"

POSITION_PROFILES: dict[str, dict[str, object]] = {
    "后端工程师": {
        "required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Docker", "category": "tool", "proficiency": "了解"},
            {"name": "REST API", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "preferred": [
            {"name": "Kubernetes", "category": "tool", "proficiency": "了解"},
            {"name": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "FastAPI", "category": "hard_skill", "proficiency": "了解"},
            {"name": "PostgreSQL", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Redis", "category": "hard_skill", "proficiency": "了解"},
            {"name": "REST API", "category": "hard_skill", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [
            {"name": "Docker", "category": "tool", "proficiency": "了解"},
        ],
    },
    "前端开发工程师": {
        "required": [
            {"name": "JavaScript", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "TypeScript", "category": "hard_skill", "proficiency": "了解"},
        ],
        "preferred": [
            {"name": "Node.js", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Webpack", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "JavaScript", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Vue.js", "category": "hard_skill", "proficiency": "了解"},
            {"name": "HTML5", "category": "hard_skill", "proficiency": "了解"},
            {"name": "CSS3", "category": "hard_skill", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [
            {"name": "TypeScript", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "数据分析师": {
        "required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Pandas", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Excel", "category": "tool", "proficiency": "熟悉"},
            {"name": "统计学", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "preferred": [
            {"name": "Tableau", "category": "tool", "proficiency": "了解"},
            {"name": "Machine Learning", "category": "hard_skill", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Excel", "category": "tool", "proficiency": "熟悉"},
            {"name": "Pandas", "category": "hard_skill", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [
            {"name": "Python", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "AI工程师": {
        "required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "PyTorch", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "scikit-learn", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "TensorFlow", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Linux", "category": "tool", "proficiency": "熟悉"},
            {"name": "Git", "category": "tool", "proficiency": "熟悉"},
        ],
        "preferred": [
            {"name": "Hugging Face", "category": "tool", "proficiency": "了解"},
            {"name": "Docker", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "PyTorch", "category": "hard_skill", "proficiency": "了解"},
            {"name": "scikit-learn", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Git", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [],
    },
    "DevOps工程师": {
        "required": [
            {"name": "Docker", "category": "tool", "proficiency": "熟悉"},
            {"name": "Kubernetes", "category": "tool", "proficiency": "熟悉"},
            {"name": "Terraform", "category": "tool", "proficiency": "熟悉"},
            {"name": "Ansible", "category": "tool", "proficiency": "熟悉"},
            {"name": "Prometheus", "category": "tool", "proficiency": "熟悉"},
            {"name": "Grafana", "category": "tool", "proficiency": "熟悉"},
            {"name": "CI/CD", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "preferred": [
            {"name": "Linux", "category": "tool", "proficiency": "熟悉"},
            {"name": "AWS", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "Docker", "category": "tool", "proficiency": "熟悉"},
            {"name": "Kubernetes", "category": "tool", "proficiency": "了解"},
            {"name": "CI/CD", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Prometheus", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [
            {"name": "Linux", "category": "tool", "proficiency": "了解"},
        ],
    },
    "大模型应用工程师": {
        "required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "LLM", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "RAG", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "LangChain", "category": "tool", "proficiency": "熟悉"},
            {"name": "Prompt Engineering", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "preferred": [
            {"name": "Fine-tuning", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Docker", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "LLM", "category": "hard_skill", "proficiency": "了解"},
            {"name": "RAG", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Prompt Engineering", "category": "hard_skill", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [],
    },
    "安全工程师": {
        "required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Penetration Testing", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "SIEM", "category": "tool", "proficiency": "熟悉"},
            {"name": "Kubernetes", "category": "tool", "proficiency": "了解"},
            {"name": "Cloud Security", "category": "hard_skill", "proficiency": "了解"},
        ],
        "preferred": [
            {"name": "Linux", "category": "tool", "proficiency": "了解"},
            {"name": "Docker", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_required": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Penetration Testing", "category": "hard_skill", "proficiency": "了解"},
            {"name": "Linux", "category": "tool", "proficiency": "了解"},
        ],
        "snapshot_delta_preferred": [],
    },
}


async def main() -> None:
    import os

    pg_uri = os.getenv("POSTGRES_URI", DEFAULT_PG_URI)
    engine = create_async_engine(pg_uri, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    now = datetime.now(UTC)
    three_months_ago = now - timedelta(days=90)

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT name FROM position_records ORDER BY name")
        )
        rows = result.fetchall()
        existing_positions = [r[0] for r in rows]

    if not existing_positions:
        print("No position_records found. Run scripts/seed_position_skill_records.py first.")
        return

    inserted = 0
    async with session_factory() as session:
        for position_name in existing_positions:
            profile = POSITION_PROFILES.get(position_name)
            if profile is None:
                continue

            required_current = profile["required"]
            preferred_current = profile["preferred"]
            required_old = profile["snapshot_delta_required"]
            preferred_old = profile["snapshot_delta_preferred"]

            snapshot_old = {
                "id": str(uuid4()),
                "position_name": position_name,
                "snapshot_date": three_months_ago.isoformat(),
                "required_skills": json.dumps(required_old, ensure_ascii=False),
                "preferred_skills": json.dumps(preferred_old, ensure_ascii=False),
                "source_count": max(1, len(required_old) + len(preferred_old)),
                "metadata_json": json.dumps(
                    {"window": "90d", "phase": "seed", "note": "3-months-ago baseline"},
                    ensure_ascii=False,
                ),
                "created_at": now.isoformat(),
            }

            snapshot_new = {
                "id": str(uuid4()),
                "position_name": position_name,
                "snapshot_date": now.isoformat(),
                "required_skills": json.dumps(required_current, ensure_ascii=False),
                "preferred_skills": json.dumps(preferred_current, ensure_ascii=False),
                "source_count": max(1, len(required_current) + len(preferred_current)),
                "metadata_json": json.dumps(
                    {"window": "latest", "phase": "seed", "note": "current snapshot"},
                    ensure_ascii=False,
                ),
                "created_at": now.isoformat(),
            }

            for snap in [snapshot_old, snapshot_new]:
                await session.execute(
                    text(
                        """
                        INSERT INTO evolution_snapshots
                        (
                            id,
                            position_name,
                            snapshot_date,
                            required_skills,
                            preferred_skills,
                            source_count,
                            metadata_json,
                            created_at
                        )
                        VALUES
                        (
                            :id,
                            :position_name,
                            :snapshot_date,
                            :required_skills,
                            :preferred_skills,
                            :source_count,
                            :metadata_json,
                            :created_at
                        )
                        """
                    ),
                    snap,
                )
                inserted += 1

        await session.commit()

    print(f"Inserted evolution snapshots: {inserted}")
    print(f"Positions covered: {sum(1 for p in existing_positions if p in POSITION_PROFILES)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
