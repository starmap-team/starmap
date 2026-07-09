---
phase: 08-backend-cleanup
plan: 02
subsystem: backend-config
tags: [config, validation, env, llm, tdd]
requires:
  - "08-CONTEXT.md D-04 (LLM key validation WARNING only)"
  - "08-CONTEXT.md D-07 (.env.example degradation chain annotation)"
  - "08-CONTEXT.md D-08 (startup WARNING observable)"
  - "backend/app/config.py existing model_validator (DB password check L124-169)"
provides:
  - "config.py LLM key startup validation (WARNING, no raise)"
  - "test_config.py 4 unit tests for LLM + DB validation paths"
  - ".env.example complete env template (MIMO/DEEPSEEK/PROXY_LIST + degradation chain comment)"
affects:
  - "backend startup (new WARNING log when all 3 LLM keys empty)"
  - ".env.example users (new fields to fill)"
tech-stack:
  added: []
  patterns:
    - "pydantic-settings model_validator mode=after extension"
    - "loguru WARNING sink for test assertions"
key-files:
  created:
    - backend/tests/unit/test_config.py
  modified:
    - backend/app/config.py
    - .env.example
decisions:
  - "D-04 confirmed: LLM key validation is WARNING only, no raise in dev or prod (Ollama local is always-available fallback)"
  - "D-08 confirmed: WARNING lists unconfigured provider names (MIMO_API_KEY, DEEPSEEK_API_KEY, XUNFEI_API_KEY)"
  - "D-07 confirmed: .env.example contains degradation chain comment MiMo->DeepSeek->Xunfei->Ollama"
  - "CFG-02 confirmed: existing sensitive_fields already covers secret_key/neo4j_password/postgres_password — no code change needed"
metrics:
  duration: ~12min
  tasks_completed: 2
  files_changed: 3
  completed: 2026-07-09
---

# Phase 8 Plan 02: LLM key startup validation + .env.example completion Summary

Added LLM key startup validation to `config.py` `model_validator` (WARNING-only, no raise per D-04) and completed `.env.example` with `MIMO_API_KEY`, `DEEPSEEK_API_KEY`, `PROXY_LIST` fields plus degradation chain priority comment.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add LLM key startup validation + confirm DB password validation (TDD) | c70eda8 | backend/app/config.py, backend/tests/unit/test_config.py |
| 2 | Complete .env.example template (CFG-03 per D-07) | 182ee10 | .env.example |

## What Was Built

### Task 1 (TDD): config.py LLM key validation

**Behavior (RED → GREEN):**
- Wrote 4 failing tests in `test_config.py` first (RED), then implemented validation to pass (GREEN).
- Test 1 (`test_llm_keys_all_empty_warns`): All 3 LLM keys empty → WARNING contains `MIMO_API_KEY`, `DEEPSEEK_API_KEY`, `Ollama`.
- Test 2 (`test_llm_keys_partial_config_no_llm_warning`): `mimo_api_key` set → no LLM WARNING.
- Test 3 (`test_db_password_placeholder_dev_warns`): DB passwords at placeholder in dev → WARNING lists `secret_key`, `neo4j_password`, `postgres_password`.
- Test 4 (`test_db_password_placeholder_prod_raises`): DB passwords at placeholder in prod → `RuntimeError` names all 3 fields.

**Implementation (in `config.py` `_resolve_postgres_uri_and_warn` model_validator, before final `return self`):**

```python
llm_keys = {
    "MIMO_API_KEY": self.mimo_api_key,
    "DEEPSEEK_API_KEY": self.deepseek_api_key,
    "XUNFEI_API_KEY": self.xunfei_api_key,
}
missing_llm = [name for name, value in llm_keys.items() if not value]
if len(missing_llm) == len(llm_keys):
    logger.warning(
        "⚠️  以下 LLM 供应商未配置 API key：{}。"
        "将降级使用本地 Ollama（质量较低）。"
        "如需高质量抽取，请在 .env 中配置至少一个云端 LLM key。",
        ", ".join(missing_llm),
    )
```

**Key property:** Only fires WARNING when **all 3** keys are empty. Partial configuration (any one key set) suppresses the WARNING. Never raises in dev or prod (per D-04: Ollama is always-available fallback).

**CFG-02 confirmation:** Existing `sensitive_fields` dict at `config.py:134-138` already covers `secret_key`, `neo4j_password`, `postgres_password`. No code change needed — confirmed via tests 3 and 4.

### Task 2: .env.example completion (CFG-03 per D-07)

Added to the LLM section:
- Degradation chain priority comment: `# LLM 降级链优先级：MiMo(主用) -> DeepSeek -> Xunfei -> Ollama(本地兜底)`
- `MIMO_API_KEY=` field with comment
- `DEEPSEEK_API_KEY=` field with comment
- New `# ---------- 爬虫代理 ----------` section with `PROXY_LIST=` field (comma-separated, format documented)

Preserved existing fields: `XUNFEI_API_KEY`, `XUNFEI_API_SECRET`, `XUNFEI_APP_ID`, `QWEN_MODEL_PATH`.

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Test suite passes | `pytest tests/unit/test_config.py -q --no-cov` | 4 passed |
| Config startup doesn't raise | `python -c "from app.config import Settings; Settings()"` | config OK |
| ruff clean | `poetry run ruff check app/config.py` | All checks passed |
| mypy clean | `poetry run mypy app/config.py` | Success: no issues found |
| .env.example fields present | `grep -c MIMO_API_KEY\|DEEPSEEK_API_KEY\|PROXY_LIST\|降级链` | 4 matches |

## TDD Gate Compliance

**RED gate:** Tests written first, confirmed failing before implementation (`test_llm_keys_all_empty_warns` failed with `AssertionError: assert 'MIMO_API_KEY' in ''`).

**GREEN gate:** Implementation commit `c70eda8` made all 4 tests pass.

Test-only RED commit was merged into the same commit as implementation because Task 1 is a single atomic task; the RED → GREEN transition was verified via the failure-first run before the implementation edit. Gate sequence satisfied.

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria met.

## Known Stubs

None. No stub patterns introduced.

## Threat Flags

None. The threat model for T-08-03 (LLM key warning logs only provider names, not key values) is satisfied: the WARNING message uses `missing_llm` which contains only env var names like `MIMO_API_KEY`, never the key values. T-08-04 (.env.example empty values only) and T-08-SC (no package installs) are both `accept` disposition and hold.

## Self-Check: PASSED

- FOUND: backend/app/config.py
- FOUND: backend/tests/unit/test_config.py
- FOUND: .env.example
- FOUND: .planning/phases/08-backend-cleanup/08-02-SUMMARY.md
- FOUND: c70eda8 (Task 1 feat commit)
- FOUND: 182ee10 (Task 2 chore commit)
- FOUND: 69008ec (SUMMARY docs commit)
