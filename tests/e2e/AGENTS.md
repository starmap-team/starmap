# E2E & verification knowledge base

## OVERVIEW
End-to-end smoke tests, browser QA, team simulation verification, and generated verification reports. Validates all subsystems wire together against a running stack.

## STRUCTURE
```text
tests/e2e/
├── smoke_test.py              # 4-scenario daily integration smoke
├── smoke_test_fixed.py        # Patched smoke variant
├── team_simulation.py         # Team-member simulation: unit-level + integration checks
├── browser_test.py            # Playwright-based frontend browser verification
├── browser_dom_smoke.py       # Playwright DOM assertions for key pages
├── browser_qa_full.py         # Full 8-page browser QA with screenshots
├── browser_qa_test.py         # Browser QA test runner
├── browser_qa_match_extract.py # Match + extract flow browser tests
├── browser_interaction/       # Browser interaction test artifacts
├── browser_qa_screenshots/    # QA screenshot artifacts
├── browser_qa_match_extract/  # Match/extract QA artifacts
├── browser_smoke/             # Browser smoke test artifacts
├── browser-qa/                # Browser QA screenshots (admin, evolution, extract, home, match, positions, quality, smoke)
│   └── screenshots/           # 40+ screenshots from QA runs
├── playwright_smoke/          # Playwright smoke test artifacts
├── E2E_TEST_PLAN.md           # Test plan document
├── E2E_FINAL_REPORT.md        # Final E2E results
├── E2E_CLOSURE_v2.1.md        # StarMap v2.1 E2E closure summary
├── FINAL_VERIFICATION_REPORT.md
├── VERIFICATION_REPORT.md
├── M4_ACCEPTANCE.md           # M4 milestone acceptance
├── CP4_ACCEPTANCE.md          # CP4 final acceptance
├── ACCURACY_MEASUREMENT_REPORT.md
├── PROMPT_AB_REPORT.md        # Prompt A/B test results
├── ROADMAP_CHECKLIST_v2.1.md  # Roadmap completion checklist
├── prompt_ab_results.json     # A/B test raw results
├── real_llm_accuracy_results.json
└── 功能验证报告_20260627.md     # Chinese functional verification
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|---|
| Run daily smoke | `smoke_test.py --base-url http://localhost:8000 --all` | 4 scenarios: discovery, update, match, deploy |
| Run single scenario | `smoke_test.py --scenario e2e-1` | e2e-1 through e2e-4 |
| Run team simulation | `team_simulation.py` | Imports backend modules directly; needs PYTHONPATH=backend/ |
| Run full browser QA | `browser_qa_full.py` | 8-page Playwright QA with screenshots |
| Run DOM smoke | `browser_dom_smoke.py` | Lightweight DOM assertions |
| Check verification status | `FINAL_VERIFICATION_REPORT.md` | Most recent full-verification summary |
| Review v2.1 closure | `E2E_CLOSURE_v2.1.md` | Final API + browser closure evidence |

## CONVENTIONS
- Smoke tests hit live API endpoints; backend must be running on localhost:8000.
- Team simulation imports backend modules directly — run from starmap root.
- Reports are generated artifacts; do not edit them manually.
- Browser QA screenshots are stored in `browser-qa/screenshots/` — reference them for visual regression.
- Acceptance docs (M4, CP4) are milestone evidence artifacts.

## ANTI-PATTERNS
- Do **not** run smoke tests against production without explicit approval.
- Do **not** commit changes to generated report files.
- Do **not** add backend unit tests here — they belong in `backend/tests/`.
- Do **not** delete screenshot artifacts without documenting why.
