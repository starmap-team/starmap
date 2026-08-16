#!/usr/bin/env bash
# CONCERN 3.4 (correctness audit 2026-08-15): CI guard banning the illegal
# run_type literal "bootstrap".
#
# Background: PipelineRun.run_type is constrained (DB CHECK or enum-style) to
# {"full", "incremental"}. Commit e0f7431f (P0-AUDIT-FIX 2026-08-13) removed
# the lone "bootstrap" caller. Re-introducing that literal would crash
# trigger_and_start at insert time (the column is NOT NULL with the enum
# constraint).
#
# This script fails CI if a string literal "bootstrap" appears in any of:
#   - backend/app/api/v1/pipeline/   (HTTP routes)
#   - backend/app/services/pipeline_service.py   (service layer)
#
# Implementation: grep for ``"bootstrap"`` as a Python string literal
# (single OR double quotes). Allowlist of false-positive call sites:
#   - test files (don't ship)
#   - the bootstrap module itself (``backend/app/core/pipeline/bootstrap.py``)
#     which is the legitimate pipeline-bootstrap path used at lifespan startup.

set -euo pipefail

ROOTS=(
    "backend/app/api/v1/pipeline"
    "backend/app/services/pipeline_service.py"
)

violations=""
for root in "${ROOTS[@]}"; do
    matches=$(grep -rn --include="*.py" \
        -E "['\"]bootstrap['\"]" \
        "$root" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        violations+="$matches"$'\n'
    fi
done

if [ -n "$violations" ]; then
    echo "FAIL: illegal run_type literal \"bootstrap\" found (CONCERN 3.4):"
    echo "$violations"
    echo ""
    echo "PipelineRun.run_type must be one of: full | incremental."
    echo "See commit e0f7431f for the original fix that removed the"
    echo "\"bootstrap\" caller; the literal must NOT re-appear in pipeline"
    echo "routes or the pipeline service layer."
    exit 1
fi

echo "OK: no illegal run_type literal \"bootstrap\" in pipeline routes / service"
exit 0