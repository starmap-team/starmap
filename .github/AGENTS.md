# GitHub CI knowledge base

## OVERVIEW
GitHub workflows and PR governance live under ``.github/``. The repo enforces contract-first changes, backend quality gates, frontend quality gates, and optional Docker smoke testing.

## STRUCTURE
```text
.github/
├── pull_request_template.md
└── workflows/
    └── ci.yml
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Adjust CI gate order | ``.github/workflows/ci.yml`` | contracts run first, then backend/frontend/crawler |
| Change PR checklist expectations | ``.github/pull_request_template.md`` | merge discipline is captured here |
| Add workflow_dispatch smoke runs | ``.github/workflows/ci.yml`` | Docker smoke is manual/scheduled, not normal PR-triggered |

## CONVENTIONS
- Contract validation is the first CI job.
- Backend CI runs ruff, mypy, pytest, and an exported-vs-contract path check.
- Frontend CI runs lint, typecheck, build, and contract-generated API types.
- Docker smoke is intentionally limited to scheduled/manual runs.

## ANTI-PATTERNS
- Do **not** change API surfaces without contract validation passing first.
- Do **not** merge PRs expecting untested manual verification when CI already gates the same concern.
- Do **not** add heavy Docker-dependent tests to normal PR workflows without considering runner constraints.
