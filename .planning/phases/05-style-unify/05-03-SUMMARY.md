---
phase: 05-style-unify
plan: 03
type: execute
subsystem: tests-e2e
tags: [color-consistency, playwright, ka-node, d-08, d-11]
tech-stack:
  added: []
  patterns:
    - "stdlib PNG decode via zlib (PIL optional inside try/except)"
    - "smoke_test.py Colors/log/check helpers reused verbatim"
    - "argparse mirror of --base-url / --output-dir CLI conventions"
dependency-graph:
  requires: []
  provides:
    - "tests/e2e/test_2d_3d_color_consistency.py"
  affects: []
key-files:
  created:
    - tests/e2e/test_2d_3d_color_consistency.py
  modified: []
decisions:
  - "D-08 satisfied: standalone Playwright script (not bolted into smoke_test.py) keeps scope tight"
  - "D-09 satisfied: --base-url / --output-dir argparse mirror smoke_test.py; Colors/log/check copied verbatim"
  - "D-10 satisfied: PIL inside try/except; stdlib zlib PNG decode is the fallback — no new pip dep"
  - "D-11 satisfied: rgb_diff returns max channel diff; default --tolerance=5"
metrics:
  duration: "~5 min"
  completed_date: 2026-07-07
---

# Phase 5 Plan 3: 2D/3D KA Color Consistency — Summary

**One-liner:** Standalone Playwright script that navigates Home.vue in 2D/3D view modes, screenshots the same KA node, and asserts dominant colors match within ±5 RGB.

## What was built

`tests/e2e/test_2d_3d_color_consistency.py` (348 lines) — TDD-GREEN deliverable for COLOR-04.

### Structure

| Layer | Purpose |
|-------|---------|
| `Colors` / `log` / `check` | Verbatim copy from `tests/e2e/smoke_test.py` (D-09) |
| `rgb_diff(c1, c2)` | Pure function returning max channel abs diff (testable, no I/O) |
| `dominant_color_from_bytes(png_bytes, region)` | Mean RGB of centered region; PIL preferred, stdlib zlib fallback |
| `run_self_test()` | 8 assertions proving diff math + stdlib PNG decoder; needs no Playwright/network |
| `run_live_check(args)` | Playwright Chromium → click `.vm-btn:has-text("2D"/"3D")` → screenshot bbox → diff |
| `main()` | argparse `--base-url / --node-id / --tolerance / --output-dir / --self-test` |

### Self-test result (8/8 PASS)

```
[PASS] rgb_diff identical = 0
[PASS] rgb_diff((255,0,0),(250,0,0)) = 5
[PASS] 5 <= tolerance=5 holds
[PASS] rgb_diff uses max channel
[PASS] stdlib PNG decode returns correct mean
[PASS] stdlib PNG decode handles another color
[PASS] diff between (255,0,0) and (250,0,0) <= tolerance=5
[PASS] diff between (255,0,0) and (245,0,0) > tolerance=5

Self-test: PASS  (exit 0)
```

A synthetic 32×32 RGB PNG was built via stdlib `zlib` (`_make_solid_png`) and round-tripped through `dominant_color_from_bytes` to prove the decoder handles real PNG output, not just numeric theory.

## Deviations from Plan

**None** — plan executed exactly as written. All 9 action items (docstring → imports → helpers → diff fn → PNG decoder → self-test → live check → main → entrypoint) shipped in a single commit.

### Notes (informational, not deviations)

- `PIL.Image.getdata` emitted a `DeprecationWarning` (Pillow 14, 2027-10-15). Non-blocking; flagged for future migration to `get_flattened_data`. Acceptable since PIL is optional and the stdlib path is the documented fallback.
- The live check is gated behind `--base-url` so the default invocation (`--self-test`) runs in CI without Playwright installed.

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| File at `tests/e2e/test_2d_3d_color_consistency.py` | ✅ created, 348 lines (≥120) |
| `--self-test` exits 0 | ✅ confirmed (`EXIT=0`) |
| PASS lines for rgb_diff zero and 5-channel-diff | ✅ both printed |
| `rgb_diff((255,0,0),(250,0,0)) == 5` | ✅ asserted and verified |
| `argparse` defines `--base-url / --tolerance / --self-test` | ✅ all present (lines 335/337/339) |
| No hard top-level PIL import | ✅ inside `try/except` (line 53) |
| Reuses `Colors` / `log` / `check` | ✅ all three defined (lines 31/39/46) |

## How to run

```bash
# Standalone self-test (no browser needed)
python tests/e2e/test_2d_3d_color_consistency.py --self-test

# Against running dev server
python tests/e2e/test_2d_3d_color_consistency.py --base-url http://localhost:5173

# Custom tolerance + node
python tests/e2e/test_2d_3d_color_consistency.py --base-url http://localhost:5173 \
    --node-id ka-042 --tolerance 10
```

## Self-Check: PASSED

- File exists at `tests/e2e/test_2d_3d_color_consistency.py` ✅
- Commit `1080c99` exists in `git log` ✅
- Self-test exit code 0 ✅