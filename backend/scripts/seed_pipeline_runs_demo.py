"""Seed simulated pipeline run history into pipeline_runs table.

Generates 15 demo runs: a mix of completed, running, and failed runs
with realistic stage data.

Usage:
    cd backend && python -m scripts.seed_pipeline_runs_demo
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings


def _build_stages(
    statuses: list[str],
    base_duration: int = 1200,
    records_per_stage: int = 500,
    error_stage: str | None = None,
) -> list[dict]:
    """Build a stages JSON array with realistic timing data."""
    stage_names = ["crawl", "dedup", "clean", "import", "graph_sync"]
    now = datetime.now(UTC)
    stages = []
    cursor = now - timedelta(minutes=30)

    for i, name in enumerate(stage_names):
        if i < len(statuses):
            status = statuses[i]
        else:
            status = "pending"

        if status == "pending":
            stages.append({
                "name": name,
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration_ms": 0,
                "records_processed": 0,
                "errors": [],
            })
            continue

        # Simulate timing
        started = cursor
        duration = base_duration + (i * 300)  # Later stages take longer
        records = max(0, records_per_stage - i * 50)  # Records decrease through stages
        completed = started + timedelta(milliseconds=duration)
        cursor = completed + timedelta(seconds=2)  # Small gap between stages

        errors = []
        if name == error_stage:
            errors = [f"Simulated error in {name} stage: connection timeout"]

        stages.append({
            "name": name,
            "status": status,
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "duration_ms": duration,
            "records_processed": records,
            "errors": errors,
        })

    return stages


DEMO_RUNS = [
    # ── Completed runs (most recent) ──
    {
        "run_type": "full",
        "status": "completed",
        "hours_ago": 2,
        "stages": _build_stages(["completed"] * 5, base_duration=1800, records_per_stage=2400),
        "total_records": 2400,
        "new_records": 312,
        "updated_records": 187,
        "quality_score": 0.93,
    },
    {
        "run_type": "incremental",
        "status": "completed",
        "hours_ago": 8,
        "stages": _build_stages(["completed"] * 5, base_duration=900, records_per_stage=680),
        "total_records": 680,
        "new_records": 95,
        "updated_records": 42,
        "quality_score": 0.91,
    },
    {
        "run_type": "full",
        "status": "completed",
        "hours_ago": 26,
        "stages": _build_stages(["completed"] * 5, base_duration=2100, records_per_stage=3200),
        "total_records": 3200,
        "new_records": 478,
        "updated_records": 256,
        "quality_score": 0.89,
    },
    {
        "run_type": "incremental",
        "status": "completed",
        "hours_ago": 32,
        "stages": _build_stages(["completed"] * 5, base_duration=750, records_per_stage=420),
        "total_records": 420,
        "new_records": 37,
        "updated_records": 21,
        "quality_score": 0.92,
    },
    {
        "run_type": "source_sync",
        "status": "completed",
        "hours_ago": 50,
        "stages": _build_stages(["completed"] * 5, base_duration=600, records_per_stage=180),
        "total_records": 180,
        "new_records": 15,
        "updated_records": 8,
        "quality_score": 0.95,
    },
    # ── Failed run ──
    {
        "run_type": "full",
        "status": "failed",
        "hours_ago": 72,
        "stages": _build_stages(
            ["completed", "completed", "failed", "pending", "pending"],
            base_duration=1500,
            records_per_stage=2100,
            error_stage="clean",
        ),
        "total_records": 0,
        "new_records": 0,
        "updated_records": 0,
        "quality_score": 0.0,
        "error_log": "Clean stage failed: DataValidationError - 15 records with malformed JSON in source BOSS直聘",
    },
    # ── Running (in-progress) ──
    {
        "run_type": "full",
        "status": "running",
        "hours_ago": 0,
        "stages": _build_stages(
            ["completed", "completed", "running", "pending", "pending"],
            base_duration=2000,
            records_per_stage=2800,
        ),
        "total_records": 0,
        "new_records": 0,
        "updated_records": 0,
        "quality_score": 0.0,
    },
    # ── More completed runs ──
    {
        "run_type": "incremental",
        "status": "completed",
        "hours_ago": 96,
        "stages": _build_stages(["completed"] * 5, base_duration=800, records_per_stage=550),
        "total_records": 550,
        "new_records": 62,
        "updated_records": 35,
        "quality_score": 0.90,
    },
    {
        "run_type": "full",
        "status": "completed",
        "hours_ago": 120,
        "stages": _build_stages(["completed"] * 5, base_duration=2400, records_per_stage=4100),
        "total_records": 4100,
        "new_records": 620,
        "updated_records": 310,
        "quality_score": 0.87,
    },
    {
        "run_type": "incremental",
        "status": "completed",
        "hours_ago": 144,
        "stages": _build_stages(["completed"] * 5, base_duration=700, records_per_stage=380),
        "total_records": 380,
        "new_records": 28,
        "updated_records": 15,
        "quality_score": 0.93,
    },
    # ── Another failed ──
    {
        "run_type": "incremental",
        "status": "failed",
        "hours_ago": 168,
        "stages": _build_stages(
            ["completed", "failed", "pending", "pending", "pending"],
            base_duration=900,
            records_per_stage=600,
            error_stage="dedup",
        ),
        "total_records": 0,
        "new_records": 0,
        "updated_records": 0,
        "quality_score": 0.0,
        "error_log": "Dedup stage failed: SimHashEngine - OutOfMemory processing batch 42/50",
    },
    # ── Older completed runs ──
    {
        "run_type": "full",
        "status": "completed",
        "hours_ago": 192,
        "stages": _build_stages(["completed"] * 5, base_duration=1900, records_per_stage=2900),
        "total_records": 2900,
        "new_records": 410,
        "updated_records": 195,
        "quality_score": 0.88,
    },
    {
        "run_type": "source_sync",
        "status": "completed",
        "hours_ago": 216,
        "stages": _build_stages(["completed"] * 5, base_duration=500, records_per_stage=120),
        "total_records": 120,
        "new_records": 8,
        "updated_records": 5,
        "quality_score": 0.94,
    },
    {
        "run_type": "incremental",
        "status": "completed",
        "hours_ago": 240,
        "stages": _build_stages(["completed"] * 5, base_duration=850, records_per_stage=720),
        "total_records": 720,
        "new_records": 88,
        "updated_records": 45,
        "quality_score": 0.91,
    },
    {
        "run_type": "full",
        "status": "completed",
        "hours_ago": 264,
        "stages": _build_stages(["completed"] * 5, base_duration=2000, records_per_stage=3500),
        "total_records": 3500,
        "new_records": 520,
        "updated_records": 280,
        "quality_score": 0.86,
    },
]


async def seed() -> None:
    engine = create_async_engine(settings.postgres_uri)
    now = datetime.now(UTC)

    async with AsyncSession(engine) as session:
        for run in DEMO_RUNS:
            run_id = uuid.uuid4()
            started = now - timedelta(hours=run["hours_ago"])
            completed = None
            if run["status"] in ("completed", "failed"):
                # Estimate completion time from stages
                total_ms = sum(s.get("duration_ms", 0) for s in run["stages"])
                completed = started + timedelta(milliseconds=total_ms + 5000)

            await session.execute(
                text("""
                    INSERT INTO pipeline_runs
                        (id, run_type, status, started_at, completed_at,
                         stages, total_records, new_records, updated_records,
                         quality_score, error_log)
                    VALUES
                        (:id, :run_type, :status, :started_at, :completed_at,
                         :stages::json, :total_records, :new_records, :updated_records,
                         :quality_score, :error_log)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": str(run_id),
                    "run_type": run["run_type"],
                    "status": run["status"],
                    "started_at": started.isoformat(),
                    "completed_at": completed.isoformat() if completed else None,
                    "stages": json.dumps(run["stages"]),
                    "total_records": run["total_records"],
                    "new_records": run["new_records"],
                    "updated_records": run["updated_records"],
                    "quality_score": run["quality_score"],
                    "error_log": run.get("error_log"),
                },
            )

        await session.commit()
        print(f"Seeded {len(DEMO_RUNS)} pipeline runs:")
        completed = sum(1 for r in DEMO_RUNS if r["status"] == "completed")
        failed = sum(1 for r in DEMO_RUNS if r["status"] == "failed")
        running = sum(1 for r in DEMO_RUNS if r["status"] == "running")
        print(f"  - {completed} completed, {failed} failed, {running} running")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
