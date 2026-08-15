"""CI guard (CONCERN 3.8): detect stale ``starmap-contracts/schemas/*.json``.

The JSON Schemas in starmap-contracts/schemas/ are generated from the
Pydantic models in backend/app/schemas/*.py via
``scripts/export_json_schemas.py``. When a Pydantic model is edited, the
generator must be re-run or the contract drifts from the implementation.

This guard compares the mtime of each schema.json against the mtime of
its most likely source Pydantic module. If the schema is older than the
source, the contract has drifted — fail CI.

Warn-only on dev machines (CI config can promote to hard-fail via
``--strict``).
"""
from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = REPO / "starmap-contracts" / "schemas"
BACKEND_SCHEMAS_DIR = REPO / "backend" / "app" / "schemas"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="exit 1 on drift")
    args = parser.parse_args()

    if not SCHEMAS_DIR.exists():
        print(f"OK: {SCHEMAS_DIR} missing — skip.")
        return 0

    drift: list[tuple[str, str]] = []  # (schema_path, latest_source_mtime_holder)

    for schema in sorted(SCHEMAS_DIR.glob("*.json")):
        stem = schema.stem.replace(".schema", "")
        # Schema name → Pydantic source module (matches scripts/export_json_schemas.py).
        candidate = BACKEND_SCHEMAS_DIR / f"{stem}.py"
        if not candidate.exists():
            # Some schemas come from nested routes; skip silently.
            continue
        if schema.stat().st_mtime < candidate.stat().st_mtime:
            drift.append((str(schema), str(candidate)))

    if drift:
        print(
            f"WARNING: {len(drift)} JSON Schemas may be stale relative to "
            f"Pydantic sources:"
        )
        for s, src in drift:
            print(f"  {s}\n    older than: {src}")
        print()
        print("Re-run: cd backend && poetry run python ../scripts/export_json_schemas.py")
        if args.strict:
            return 1

    print(
        f"OK: JSON Schema drift check completed ({len(drift)} stale of "
        f"{len(list(SCHEMAS_DIR.glob('*.json')))} total)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
