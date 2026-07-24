# GitHub automation knowledge base

## OVERVIEW
GitHub workflows and PR governance live under `.github/`. The repo enforces contract-first changes, backend quality gates, frontend quality gates, and optional Docker smoke testing.

## STRUCTURE
```
.github/
├── pull_request_template.md
└── workflows/
    ├── ci.yml
    └── doc-lint.yml
```

## WHERE TO LOOK
| Task | Location |
|---|---|
| Adjust CI gate order | `.github/workflows/ci.yml` |
| Change PR checklist expectations | `.github/pull_request_template.md` |
| Add workflow_dispatch smoke runs | `.github/workflows/ci.yml` |

## CONVENTIONS
- Contract validation runs first.
- Backend CI runs ruff, mypy, pytest and contract consistency.
- Frontend CI regenerates types, lints, typechecks, tests, builds.
- Docker smoke is manual or scheduled, not normal PR-triggered.
- Documentation checks run via `scripts/check-docs.ps1`.

## ANTI-PATTERNS
- Do not change API surfaces without passing contract validation first.
- Do not merge PRs that depend on untested manual verification when CI already gates the same concern.
- Do not hard-code test counts, file counts, or drift-prone numbers in workflow files.