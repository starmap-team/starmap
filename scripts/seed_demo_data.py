"""Demo data seeding script.

QA Stage 3.5: bootstrap sample datasources / pipeline stages / evolution
snapshots so the zero-state pages (DataSources / PipelineMonitor /
EvolutionDashboard) stop showing flat empty lists.

Run from starmap project root:

    python scripts/seed_demo_data.py

The script is idempotent (`SELECT … LIMIT 1` checks before each insert) and
safe to run against any environment with the same Postgres / Neo4j
connection settings — production credentials must NOT be used; the script
exits if APP_ENV=production.

Implementation note: the per-table seed sub-scripts (seed_datasources.py,
seed_pipeline_stages.py, seed_evolution_snapshots.py) are intentionally
left as small, focused modules so each can be re-run independently. This
top-level file just orchestrates them in the right order.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure `scripts/` is importable when invoked from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings  # noqa: E402  (after sys.path mutation)


def _ensure_not_production() -> None:
    if getattr(settings, "app_env", "") == "production":
        raise SystemExit("Refusing to seed demo data when APP_ENV=production")


def _run_sub(name: str) -> None:
    print(f"\n--- seed_demo_data: {name} ---")
    mod = __import__(name)
    if hasattr(mod, "main"):
        mod.main()
    elif hasattr(mod, "seed"):
        mod.seed()
    else:
        # Convention: importing the module runs its top-level insertion.
        # Sub-scripts that follow this contract need no entry point.
        pass


def main() -> None:
    _ensure_not_production()

    # Order matters: pipeline stages / evolution snapshots depend on the
    # datasource IDs being deterministic.
    _run_sub("seed_datasources")
    _run_sub("seed_pipeline_stages")
    _run_sub("seed_evolution_snapshots")

    print("\nseed_demo_data: done.")


if __name__ == "__main__":
    main()