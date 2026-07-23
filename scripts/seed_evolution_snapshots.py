"""Seed synthetic evolution snapshots spanning the last 14 days.

QA Stage 3.5 + B4: when JDExtractionRecord aggregation doesn't yet exist as
materialised snapshots, materialise 14 daily derived rows so that
/evolution/snapshots returns a non-empty time series immediately.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.dependencies import get_session_factory  # type: ignore


def seed() -> None:
    """Best-effort demo seeding.

    The evolution snapshot table name and ORM class may evolve; we attempt
    a generic select/insert pattern that doesn't crash if the model
    migrations haven't run yet. Idempotent: skips rows whose (date,
    scope) already exists.
    """
    try:
        from app.models.evolution_models import EvolutionSnapshot  # type: ignore
    except ImportError:
        print("  - skip: EvolutionSnapshot model not available (run migrations first)")
        return

    sf = get_session_factory()
    base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with sf() as session:
        for offset in range(14):
            day = base - timedelta(days=offset)
            existing = session.execute(
                select(EvolutionSnapshot.id)
                .where(EvolutionSnapshot.snapshot_date == day.date())
                .limit(1)
            ).scalar_one_or_none()
            if existing:
                print(f"  - skip: snapshot {day.date()} exists")
                continue
            session.add(EvolutionSnapshot(
                snapshot_date=day.date(),
                scope="global",
                total_skills=random.randint(8, 18),
                new_skills=random.randint(0, 3),
                cii_index=round(100 + random.uniform(-8, 12), 2),
                created_at=datetime.now(UTC),
            ))
            print(f"  + insert: snapshot {day.date()}")
        session.commit()


if __name__ == "__main__":
    seed()