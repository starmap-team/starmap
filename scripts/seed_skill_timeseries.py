"""Seed skill_timeseries for emergence detection (Z-score based).

Creates 6 monthly windows of frequency data for key skills,
enabling EmergenceFinder.detect() to produce meaningful Z-scores.

Skills like LLM, RAG, LangChain show a clear rising pattern,
while stable skills like Python maintain steady frequency.

Requires: POSTGRES_URI env var or defaults to local docker.

Usage:
  cd starmap
  python scripts/seed_skill_timeseries.py
"""
from __future__ import annotations

import asyncio
import os
import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DEFAULT_PG_URI = "postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap"

# 6 monthly windows ending now
# Each skill has a list of 6 frequencies (oldest to newest)
# Rising skills: accelerating growth. Stable: flat. Declining: dropping.
SKILL_TIMESERIES_DATA: dict[str, dict] = {
    # ── Rising / Emerging skills (for demo: LLM ecosystem) ──
    "LLM": {
        "frequencies": [3, 5, 8, 15, 28, 45],
        "source_count": [2, 3, 4, 6, 8, 10],
        "positions": ["大模型应用工程师", "AI工程师", "AI算法工程师"],
        "category": "hard_skill",
    },
    "RAG": {
        "frequencies": [2, 4, 7, 12, 22, 38],
        "source_count": [2, 3, 4, 5, 7, 9],
        "positions": ["大模型应用工程师", "AI工程师"],
        "category": "hard_skill",
    },
    "LangChain": {
        "frequencies": [1, 3, 6, 10, 18, 30],
        "source_count": [1, 2, 3, 5, 6, 8],
        "positions": ["大模型应用工程师"],
        "category": "tool",
    },
    "Prompt Engineering": {
        "frequencies": [2, 4, 8, 14, 24, 40],
        "source_count": [2, 3, 4, 6, 7, 10],
        "positions": ["大模型应用工程师", "AI工程师"],
        "category": "hard_skill",
    },
    "Fine-tuning": {
        "frequencies": [1, 2, 4, 7, 12, 20],
        "source_count": [1, 2, 3, 4, 5, 7],
        "positions": ["大模型应用工程师", "AI算法工程师"],
        "category": "hard_skill",
    },
    "Hugging Face": {
        "frequencies": [3, 5, 8, 12, 18, 25],
        "source_count": [2, 3, 4, 5, 6, 8],
        "positions": ["AI工程师", "AI算法工程师"],
        "category": "tool",
    },
    "TypeScript": {
        "frequencies": [8, 10, 13, 16, 20, 25],
        "source_count": [4, 5, 5, 6, 7, 8],
        "positions": ["前端开发工程师", "前端工程师"],
        "category": "hard_skill",
    },
    # ── Stable skills ──
    "Python": {
        "frequencies": [30, 32, 29, 31, 33, 30],
        "source_count": [10, 10, 10, 10, 10, 10],
        "positions": ["后端工程师", "AI工程师", "数据分析师", "大模型应用工程师", "DevOps工程师"],
        "category": "hard_skill",
    },
    "Java": {
        "frequencies": [25, 27, 24, 26, 25, 24],
        "source_count": [8, 8, 8, 8, 8, 8],
        "positions": ["后端工程师", "高级后端工程师"],
        "category": "hard_skill",
    },
    "JavaScript": {
        "frequencies": [22, 23, 21, 22, 23, 22],
        "source_count": [7, 7, 7, 7, 7, 7],
        "positions": ["前端开发工程师", "前端工程师"],
        "category": "hard_skill",
    },
    "Docker": {
        "frequencies": [18, 19, 20, 19, 21, 20],
        "source_count": [6, 6, 6, 6, 7, 7],
        "positions": ["后端工程师", "DevOps工程师", "大模型应用工程师"],
        "category": "tool",
    },
    "PostgreSQL": {
        "frequencies": [15, 16, 14, 15, 16, 15],
        "source_count": [5, 5, 5, 5, 5, 5],
        "positions": ["后端工程师"],
        "category": "hard_skill",
    },
    "React": {
        "frequencies": [14, 15, 13, 14, 15, 14],
        "source_count": [5, 5, 5, 5, 5, 5],
        "positions": ["前端开发工程师"],
        "category": "hard_skill",
    },
    "Vue.js": {
        "frequencies": [12, 13, 12, 13, 14, 13],
        "source_count": [4, 4, 4, 4, 5, 5],
        "positions": ["前端开发工程师", "前端工程师"],
        "category": "hard_skill",
    },
    # ── Declining skills ──
    "jQuery": {
        "frequencies": [10, 8, 6, 5, 3, 2],
        "source_count": [4, 3, 3, 2, 2, 1],
        "positions": ["前端开发工程师"],
        "category": "hard_skill",
    },
    "SVN": {
        "frequencies": [8, 6, 5, 3, 2, 1],
        "source_count": [3, 3, 2, 2, 1, 1],
        "positions": ["后端工程师"],
        "category": "tool",
    },
}


async def main() -> None:
    pg_uri = os.getenv("POSTGRES_URI", DEFAULT_PG_URI)
    engine = create_async_engine(pg_uri, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    now = datetime.now(UTC)
    window_days = 30  # 6 windows of 30 days each

    inserted = 0

    async with session_factory() as session:
        for skill_name, data in SKILL_TIMESERIES_DATA.items():
            freqs = data["frequencies"]
            sources = data["source_count"]
            positions = data["positions"]
            category = data["category"]

            for i in range(len(freqs)):
                window_start = now - timedelta(days=(len(freqs) - i) * window_days)
                window_end = window_start + timedelta(days=window_days)

                record = {
                    "id": str(uuid4()),
                    "skill_name": skill_name,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "frequency": freqs[i],
                    "source_count": sources[i],
                    "positions": str(positions).replace("'", '"'),  # JSON array
                    "category": category,
                    "created_at": now.isoformat(),
                }

                await session.execute(
                    text(
                        """
                        INSERT INTO skill_timeseries
                        (id, skill_name, window_start, window_end,
                         frequency, source_count, positions, category, created_at)
                        VALUES
                        (:id, :skill_name, :window_start, :window_end,
                         :frequency, :source_count, :positions::jsonb, :category, :created_at)
                        """
                    ),
                    record,
                )
                inserted += 1

        await session.commit()

    print(f"Inserted skill_timeseries records: {inserted}")
    print(f"Skills covered: {len(SKILL_TIMESERIES_DATA)}")
    print("Rising skills: LLM, RAG, LangChain, Prompt Engineering, Fine-tuning, Hugging Face, TypeScript")
    print("Stable skills: Python, Java, JavaScript, Docker, PostgreSQL, React, Vue.js")
    print("Declining skills: jQuery, SVN")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
