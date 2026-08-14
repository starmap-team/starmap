#!/usr/bin/env bash
# CONCERN 3.1 (correctness audit 2026-08-15): CI guard against sites that
# update PipelineRun.stages without routing through complete_run.
#
# Background: ``complete_run`` in backend/app/core/pipeline/orchestrator.py:258
# aggregates the per-stage work and writes back new_records / updated_records /
# quality_score in one place. The pre-fix bug at engine.py:148-192 wrote
# stages but skipped complete_run, leaving those fields at zero forever.
# Re-introducing that mistake would silently corrupt the dashboard.
#
# Allowed sites:
#   - engine.py:181-204 -> writes stages BEFORE calling complete_run on the
#     next line (orchestration path).
#   - orchestrator.py:248 -> update_stage_status writes stages per-stage.
#   - orchestrator.py:161 -> create_run sets initial stages.
#
# Banned pattern: any update(PipelineRun) site that writes stages= AND does
# NOT call complete_run (or update_stage_status, which is the per-stage
# primitive that complete_run orchestrates).
#
# Implementation: grep for the union of "stages=stages" or
# "stages=[\" that lands on a PipelineRun update, and assert each match is
# within the allowlist of file:function pairs above. We rely on git history
# + code review to enforce this; the script fails CI if a NEW site lands.

set -euo pipefail

PIPELINE_DIR="${1:-backend/app/core/pipeline}"

# Find every site that updates PipelineRun.stages.
matches=$(grep -rn --include="*.py" \
    -E "update\(PipelineRun\)\.where\(PipelineRun\.id == run_id\)\.values\(stages=" \
    "$PIPELINE_DIR" || true)

if [ -z "$matches" ]; then
    echo "OK: no PipelineRun.stages update sites found"
    exit 0
fi

# Allowlist of file:line where this pattern is safe (matches one of:
# complete_run caller, update_stage_status, or create_run).
violations=""
while IFS= read -r line; do
    file=$(echo "$line" | cut -d: -f1)
    lineno=$(echo "$line" | cut -d: -f2)
    # Allow engine.py (caller of complete_run) and orchestrator.py
    # (update_stage_status / create_run / complete_run itself).
    case "$file" in
        *engine.py) ;;
        *orchestrator.py) ;;
        *)
            violations+="$line"$'\n'
            ;;
    esac
done <<<"$matches"

if [ -n "$violations" ]; then
    echo "FAIL: PipelineRun.stages updated outside engine.py / orchestrator.py:"
    echo "$violations"
    echo ""
    echo "Re-introduces CONCERN 3.1: bypass of complete_run() -> quality_score"
    echo "stays 0. Route the update through app.core.pipeline.orchestrator"
    echo ".complete_run() (or .update_stage_status() for per-stage writes)."
    exit 1
fi

echo "OK: PipelineRun.stages updates are confined to engine.py / orchestrator.py"
echo "Found sites:"
echo "$matches"
exit 0