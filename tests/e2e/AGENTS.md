# E2E and live-stack verification knowledge base

## OVERVIEW

Live API and browser scenarios live here. Historical QA reports were moved to `docs/archive/reports/`; this directory now contains executable tests and their ignored runtime artifacts only.

## ENTRYPOINTS

| Scenario | Entry |
|---|---|
| Cross-domain API smoke | `smoke_test.py` |
| Pipeline smoke | `pipeline_smoke_test.py` |
| Startup readiness | `startup_smoke.py` |
| Browser DOM smoke | `browser_dom_smoke.py` |
| Full business/browser flows | `full_e2e_test.py`, `full_role_browser_test.py`, `full-business-flow.spec.ts` |

## CONVENTIONS

- Run only against an explicitly selected non-production base URL.
- Keep screenshots, traces and temporary auth state in ignored artifact directories.
- A report generated from one run belongs in `docs/archive/reports/<date>/e2e/`, not here.
- Tests assert user-observable outcomes and API contracts, not historical seeded counts.
- Document required services, credentials and destructive actions in the test CLI/help.

## EXAMPLE

```bash
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```