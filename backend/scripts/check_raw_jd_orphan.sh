#!/usr/bin/env bash
# CI guard (CONCERN 9.2): raw_jd_records was dropped by migration 033 (D5, 2026-08-12).
# This script ensures no production code path or live ORM model still references it.
#
# Allowed references:
#   - alembic/versions/002_add_extraction_tables.py  (the original create)
#   - alembic/versions/033_drop_raw_jd_records.py    (the drop migration)
#
# Behaviour: warn-only. Any non-alembic reference is logged so CI can see
# it but does NOT fail the build. Promote to `set -e` exit 1 once the
# remaining seed scripts (scripts/seed_jd_data.py,
# scripts/expand_graph_data.py, scripts/seed_position_skill_records.py)
# are migrated to write to `jd_raw` directly.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# Find all files (excluding alembic versions and this script itself) referencing raw_jd_records.
HITS=$(grep -rn "raw_jd_records" \
    --include="*.py" --include="*.sql" --include="*.md" --include="*.yaml" --include="*.yml" --include="*.sh" \
    --exclude-dir=alembic \
    --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=__pycache__ \
    --exclude-dir=.planning --exclude-dir=docs \
    backend/ frontend/ scripts/ 2>/dev/null \
    | grep -v "scripts/check_raw_jd_orphan.sh" || true)

if [[ -n "$HITS" ]]; then
    echo "WARNING: orphan references to dropped table 'raw_jd_records' found:"
    echo "$HITS"
    echo
    echo "raw_jd_records was dropped by alembic migration 033 (D5, 2026-08-12)."
    echo "These references are stale; migrate them to the live 'jd_raw' table."
    echo "(This is a warn-only check — promote to exit 1 once orphans are cleaned.)"
fi

echo "OK: raw_jd_records orphan check completed (warn mode)."
