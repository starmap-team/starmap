---
wave: 2
depends_on: [PLAN-01]
files_modified:
  - backend/tests/unit/test_llm_client.py
  - backend/tests/unit/test_extract_api.py
  - backend/tests/unit/test_graph_api.py
  - backend/tests/unit/test_pipeline_orchestrator.py
  - backend/tests/unit/test_auth_guard.py
autonomous: true
requirements: [TEST-01, TEST-02, TEST-03]
---

# PLAN-02: Backend Deep Tests

**Wave:** 2 (depends on PLAN-01 — bug fixes must be in place first)
**Goal:** Add deep tests for core business logic per DEC-023 (depth-first coverage). Target: Pipeline executor 9%→50%+, LLM client 23%→60%+, Extract API 37%→60%+, Graph API 44%→65%+. Add auth guard tests for all API endpoints (TEST-02).

## Tasks

### Task 2.1: Deep tests for LLM client (llm_client.py, 14%→50%+)

<read_first>
- backend/app/core/extraction/llm_client.py (full file)
- backend/tests/unit/test_llm_client.py (existing file — check current coverage)
- backend/app/core/extraction/llm_client.py functions: call_mimo_llm, call_xunfei_llm, call_deepseek_llm, call_llm_with_fallback, parse_llm_json_response, LLMClient.extract_from_jd, LLMClient.validate_extraction, LLMClient.judge_quality
</read_first>

<action>
Create or expand `backend/tests/unit/test_llm_client.py` with the following test classes and methods:

**Class `TestParseLlmJsonResponse`** (pure function, easy to test):
- `test_plain_json_object` — input `'{"key": "value"}'` returns parsed dict
- `test_json_in_markdown_fences` — input `'```json\n{"key": "value"}\n```'` returns parsed dict
- `test_json_with_trailing_text` — input `'{"key": "value"} some text'` returns parsed dict
- `test_invalid_json_raises` — input `'not json at all'` raises `LLMResponseError`
- `test_empty_string_raises` — input `''` raises `LLMResponseError`
- `test_nested_json` — input with nested objects/arrays parses correctly

**Class `TestCallLlmWithFallback`** (mock individual LLM functions):
- `test_mimo_succeeds_first` — mock `call_mimo_llm` to return valid response, verify no fallback called
- `test_mimo_fails_deepseek_succeeds` — mock `call_mimo_llm` to raise `LLMConnectionError`, mock `call_deepseek_llm` to return valid response
- `test_mimo_deepseek_fail_xunfei_succeeds` — first two fail, xunfei succeeds
- `test_all_providers_fail_raises` — all LLM calls raise, verify `LLMConnectionError` propagated
- `test_timeout_triggers_fallback` — mock `call_mimo_llm` to raise `LLMTimeoutError`, verify fallback

**Class `TestLLMClientMethods`** (mock `call_llm_with_fallback`):
- `test_extract_from_jd_success` — mock fallback to return valid JSON, verify result
- `test_extract_from_jd_parse_error` — mock fallback to return unparseable content
- `test_validate_extraction_success` — mock fallback, verify AntiHallucinationResult-like output
- `test_judge_quality_success` — mock fallback, verify quality score output

Use `unittest.mock.patch` with `new_callable=AsyncMock` for all LLM function mocks. Use `@pytest.mark.asyncio` for async tests.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_llm_client.py -v` — all new tests pass
- `cd backend && poetry run pytest --cov=app/core/extraction/llm_client --cov-report=term-missing -q` shows coverage >= 50%
- At least 15 new test methods added
- All pure function tests (parse_llm_json_response) have no external dependencies
- All async tests use proper AsyncMock patterns
</acceptance_criteria>

---

### Task 2.2: Deep tests for Extract API (extract.py, 24%→60%+)

<read_first>
- backend/app/api/v1/extract.py (full file)
- backend/tests/unit/test_extraction.py (existing — check overlap)
- backend/tests/integration/test_extraction_api.py (existing integration tests)
</read_first>

<action>
Create `backend/tests/unit/test_extract_api.py` with the following test classes:

**Class `TestMapProficiency`** (pure function at line ~43):
- `test_known_proficiencies` — "精通"→5, "熟悉"→3, "了解"→1 (or whatever the mapping is)
- `test_unknown_defaults` — unknown string returns default value
- `test_case_insensitive` — verify case handling

**Class `TestMapSkillItem`** (pure function at line ~58):
- `test_dict_input` — `{"name": "Python", "proficiency": "熟悉"}` maps correctly
- `test_string_input` — `"Python"` maps to default proficiency
- `test_missing_fields` — partial dict uses defaults

**Class `TestBuildResult`** (pure function at line ~72):
- `test_full_pipeline_result` — complete pipeline_result dict transforms correctly
- `test_empty_skills` — pipeline_result with no skills
- `test_missing_optional_fields` — pipeline_result without optional fields

**Class `TestExtractJDEndpoint`** (TestClient with mocked dependencies):
- `test_extract_jd_success` — mock `extract_from_jd` to return success, POST /extract/jd returns 200
- `test_extract_jd_empty_content_422` — POST with empty jd_content returns 422
- `test_extract_jd_llm_failure_502` — mock LLM to fail, returns 502
- `test_extract_jd_auth_required` — POST without auth returns 401

**Class `TestExtractResumeEndpoint`** (TestClient with mocked dependencies):
- `test_extract_resume_success` — mock `run_resume_extraction`, returns 200
- `test_extract_resume_no_file_422` — POST without file returns 422
- `test_extract_resume_auth_required` — POST without auth returns 401

Use `app.dependency_overrides` for `get_db_session` and `unittest.mock.patch` for service functions.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_extract_api.py -v` — all tests pass
- `cd backend && poetry run pytest --cov=app/api/v1/extract --cov-report=term-missing -q` shows coverage >= 60%
- At least 12 new test methods added
- Pure function tests have no external dependencies
- Endpoint tests use TestClient with proper dependency overrides
</acceptance_criteria>

---

### Task 2.3: Deep tests for Graph API (graph.py, 44%→65%+)

<read_first>
- backend/app/api/v1/graph.py (full file)
- backend/tests/unit/test_graph_service.py (existing — check overlap)
- backend/tests/unit/test_graph_services.py (existing — overview tests)
</read_first>

<action>
Create `backend/tests/unit/test_graph_api.py` with the following test classes:

**Class `TestGetPositionSkills`**:
- `test_position_found_200` — mock driver to return position+skills, GET /graph/position/{name} returns 200
- `test_position_not_found_404` — mock driver to return None, returns 404
- `test_driver_none_returns_503` — no Neo4j driver, returns 503

**Class `TestGetGraphOverview`**:
- `test_group_by_domain_200` — mock fetch_overview_by_tech_stack, GET /graph/overview?group_by=domain returns 200
- `test_group_by_tech_stack_200` — mock fetch_overview_by_tech_stack with tech_stack group
- `test_group_by_level_200` — mock fetch_overview_by_level
- `test_invalid_group_by_422` — group_by=invalid returns 422

**Class `TestGetGraphSync`**:
- `test_sync_success_200` — mock driver and session, POST /graph/sync returns 200
- `test_sync_no_driver_503` — no driver, returns 503

Use `FakeDriver`/`FakeSession` patterns from existing test files. Use `app.dependency_overrides` for `get_db_session` and `get_neo4j_driver`.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_graph_api.py -v` — all tests pass
- `cd backend && poetry run pytest --cov=app/api/v1/graph --cov-report=term-missing -q` shows coverage >= 65%
- At least 9 new test methods added
- All endpoint tests use TestClient with proper dependency overrides
- No real Neo4j or PostgreSQL connections required
</acceptance_criteria>

---

### Task 2.4: Expand Pipeline Orchestrator tests (orchestrator.py, 27%→60%+)

<read_first>
- backend/app/core/pipeline/orchestrator.py (full file)
- backend/tests/unit/test_pipeline_orchestrator.py (existing — check current coverage)
- backend/app/core/pipeline/orchestrator.py functions: _build_initial_stages, get_ready_stages, get_failed_stages, all_stages_done, get_run_history, _serialize_run, cancel_run, is_run_cancelled
</read_first>

<action>
Expand `backend/tests/unit/test_pipeline_orchestrator.py` with the following test classes:

**Class `TestBuildInitialStages`**:
- `test_all_stages_selected` — `selected=None` returns all 6 stages
- `test_subset_selected` — `selected=["CRAWL", "DEDUP"]` returns only those stages
- `test_optional_stages_included` — verify GRAPH_SYNC and TIMESERIES are optional
- `test_invalid_stage_ignored` — `selected=["INVALID"]` returns only valid stages

**Class `TestGetRunHistory`**:
- `test_returns_runs_returned_newest_first` — mock session with 3 runs, verify order
- `test_status_filter` — mock session, verify filter applied
- `test_pagination` — verify limit/offset passed to query
- `test_empty_history` — no runs returns empty list

**Class `TestSerializeRun`**:
- `test_full_run_serialized` — mock PipelineRun with all fields, verify dict output
- `test_none_returns_none` — `_serialize_run(None)` returns None
- `test_missing_optional_fields` — run without optional fields uses defaults

**Class `TestCancelRun`** (already partially tested, expand):
- `test_cancel_running_run_success` — mock session with running run, verify status set to "cancelled"
- `test_cancel_sets_redis_stop_flag` — verify `redis_client.setex` called with correct key
- `test_cancel_invalidates_status_cache` — verify `invalidate_status_cache` called

**Class `TestIsRunCancelled`**:
- `test_flag_set_returns_true` — mock redis with flag set
- `test_flag_not_set_returns_false` — mock redis with no flag
- `test_redis_none_returns_false` — no redis client returns false

Use `FakeSession`/`FakeResult` patterns. Mock `AsyncSession` with `AsyncMock` for SQLAlchemy queries.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_pipeline_orchestrator.py -v` — all tests pass
- `cd backend && poetry run pytest --cov=app/core/pipeline/orchestrator --cov-report=term-missing -q` shows coverage >= 60%
- At least 15 new test methods added (on top of existing)
- All async tests use proper AsyncMock patterns
- No real database connections required
</acceptance_criteria>

---

### Task 2.5: Auth guard tests for all API endpoints (TEST-02)

<read_first>
- backend/app/api/v1/auth.py
- backend/app/api/v1/pipeline/routes.py
- backend/app/api/v1/loop.py
- backend/app/api/v1/learning.py
- backend/app/api/v1/evolution_industry_report.py
- backend/app/api/v1/match.py
- backend/app/api/v1/extract.py
- backend/app/api/v1/admin_prompts.py
- backend/app/dependencies.py (get_current_user, require_admin)
</read_first>

<action>
Create `backend/tests/unit/test_auth_guard.py` with the following test classes:

**Class `TestPublicEndpoints`** (no auth required):
- `test_health_no_auth_200` — GET /health returns 200 without token
- `test_health_v1_no_auth_200` — GET /api/v1/health returns 200
- `test_login_no_auth_200` — POST /api/v1/auth/login returns 200 (or 401 for bad creds, not 401 for missing token)

**Class `TestAuthenticatedEndpoints`** (require Bearer token):
- `test_health_detail_no_token_401` — GET /health/detail without token returns 401
- `test_loop_run_no_token_401` — POST /loop/run without token returns 401
- `test_loop_history_no_token_401` — GET /loop/history without token returns 401
- `test_learning_plans_no_token_401` — GET /learning/plans without token returns 401
- `test_graph_overview_no_token_401` — GET /graph/overview without token returns 401 (if auth-protected)
- `test_extract_jd_no_token_401` — POST /extract/jd without token returns 401
- `test_match_position_no_token_401` — POST /match/position without token returns 401
- `test_pipeline_status_no_token_401` — GET /pipeline/status without token returns 401

**Class `TestAdminEndpoints`** (require admin role):
- `test_pipeline_trigger_non_admin_403` — POST /pipeline/trigger with non-admin token returns 403
- `test_pipeline_config_update_non_admin_403` — PUT /pipeline/config with non-admin token returns 403
- `test_schedule_create_non_admin_403` — POST /pipeline/schedules with non-admin token returns 403
- `test_schedule_delete_non_admin_403` — DELETE /pipeline/schedules/{id} with non-admin token returns 403

**Class `TestDevTokenAccepted`** (dev environment):
- `test_dev_token_accepted_in_dev` — Bearer "dev-token" returns 200 in non-production env
- `test_dev_token_rejected_in_prod` — Bearer "dev-token" returns 401 when `app_env=production` (mock settings)

Use `TestClient(app)` with `app.dependency_overrides` to control auth behavior. For admin tests, create a JWT with `role="user"` (non-admin). For dev token tests, mock `settings.app_env`.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_auth_guard.py -v` — all tests pass
- At least 15 new test methods covering auth guard for all major endpoint groups
- Public endpoints return 200 without token
- Authenticated endpoints return 401 without token
- Admin endpoints return 403 with non-admin token
- Dev token works in non-production environment
</acceptance_criteria>

---

### Task 2.6: Smoke tests for low-coverage modules (TEST-01 minimum bar)

<read_first>
- backend/app/core/pipeline/executor.py
- backend/app/core/extraction/resume_eval.py
- backend/app/tasks/celery_app.py
- backend/app/pipeline/steps.py
</read_first>

<action>
Add basic smoke tests (>=5 each) for the remaining low-coverage modules. These are NOT deep tests — just enough to verify basic functionality and raise coverage above the zero-test threshold:

1. **`backend/tests/unit/test_executor_smoke.py`** — 5 tests for `executor.py`:
   - `test_trigger_and_start_creates_run` — mock session, verify PipelineRun created
   - `test_retry_stage_resets_failed` — mock session with failed stage, verify reset
   - `test_resume_run_continues` — mock session with partial run
   - `test_check_stop_flag_true` — mock redis with flag
   - `test_check_stop_flag_false` — mock redis without flag

2. **`backend/tests/unit/test_resume_eval_smoke.py`** — 5 tests for `resume_eval.py`:
   - `test_parse_resume_text_basic` — basic text parsing
   - `test_empty_input_returns_empty` — empty string handling
   - `test_extract_skills_from_text` — skill extraction from resume text
   - `test_extract_education` — education section parsing
   - `test_extract_experience` — experience section parsing

3. **`backend/tests/unit/test_celery_app_smoke.py`** — 5 tests for `celery_app.py`:
   - `test_celery_app_config` — verify Celery config loaded
   - `test_task_registered` — verify key tasks are registered
   - `test_autodiscover_tasks` — verify autodiscover config
   - `test_broker_url_config` — verify broker URL from settings
   - `test_result_backend_config` — verify result backend config

4. **`backend/tests/unit/test_pipeline_steps_smoke.py`** — 5 tests for `steps.py`:
   - `test_step_name_defined` — each step has a name attribute
   - `test_step_dependencies` — step dependency graph is valid
   - `test_all_stages_enum_complete` — StageName enum has all expected values
   - `test_optional_stages_set` — OPTIONAL_STAGES contains correct values
   - `test_stage_order` — stages are in expected order

Use lightweight mocks — no real Celery workers, no real database connections.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_executor_smoke.py tests/unit/test_resume_eval_smoke.py tests/unit/test_celery_app_smoke.py tests/unit/test_pipeline_steps_smoke.py -v` — all tests pass
- Each file has >= 5 test methods
- No external service dependencies (all mocked)
- Coverage for each target module increases from near-zero to at least basic coverage
</acceptance_criteria>

---

### Task 2.7: Verify backend coverage improvement

<read_first>
- All test files created in Tasks 2.1-2.6
- backend/pyproject.toml
</read_first>

<action>
Run the full backend test suite with coverage to verify:
1. All new tests pass
2. No regressions in existing tests
3. Coverage targets are met for core modules

Commands:
```bash
cd backend && poetry run pytest -q 2>&1 | tail -5
cd backend && poetry run pytest --cov=app --cov-report=term-missing --tb=no -q 2>&1 | grep -E "executor|llm_client|extract|graph\.py|orchestrator|TOTAL"
```

Target coverage improvements:
- `app/core/pipeline/orchestrator.py`: 27% → 60%+
- `app/core/extraction/llm_client.py`: 14% → 50%+
- `app/api/v1/extract.py`: 24% → 60%+
- `app/api/v1/graph.py`: 44% → 65%+
- Overall backend: 78% → 80%+
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest -q` shows 0 failed
- Coverage for `orchestrator.py` >= 60%
- Coverage for `llm_client.py` >= 50%
- Coverage for `extract.py` >= 60%
- Coverage for `graph.py` >= 65%
- Overall backend coverage >= 80%
- No regressions in existing tests
</acceptance_criteria>

---

## Verification

1. Full backend test suite: `cd backend && poetry run pytest -q` — 0 failed
2. Per-module coverage:
   - `poetry run pytest --cov=app/core/pipeline/orchestrator --cov-report=term-missing -q`
   - `poetry run pytest --cov=app/core/extraction/llm_client --cov-report=term-missing -q`
   - `poetry run pytest --cov=app/api/v1/extract --cov-report=term-missing -q`
   - `poetry run pytest --cov=app/api/v1/graph --cov-report=term-missing -q`
3. Auth guard tests: `poetry run pytest tests/unit/test_auth_guard.py -v`
4. Smoke tests: `poetry run pytest tests/unit/test_executor_smoke.py tests/unit/test_resume_eval_smoke.py tests/unit/test_celery_app_smoke.py tests/unit/test_pipeline_steps_smoke.py -v`
5. No regressions: all previously-passing tests still pass

## Must-Haves

- [ ] LLM client coverage >= 50% with deep tests for fallback chain and JSON parsing
- [ ] Extract API coverage >= 60% with pure function tests and endpoint tests
- [ ] Graph API coverage >= 65% with endpoint tests for all major routes
- [ ] Pipeline orchestrator coverage >= 60% with expanded test suite
- [ ] Auth guard tests cover all major endpoint groups (public, authenticated, admin)
- [ ] Smoke tests (>=5 each) for executor, resume_eval, celery_app, pipeline_steps
- [ ] Overall backend coverage >= 80%
- [ ] No regressions in existing tests

## Artifacts This Phase Produces

- `backend/tests/unit/test_llm_client.py` — expanded with 15+ deep tests
- `backend/tests/unit/test_extract_api.py` — new file with 12+ tests
- `backend/tests/unit/test_graph_api.py` — new file with 9+ tests
- `backend/tests/unit/test_pipeline_orchestrator.py` — expanded with 15+ new tests
- `backend/tests/unit/test_auth_guard.py` — new file with 15+ auth guard tests
- `backend/tests/unit/test_executor_smoke.py` — new file with 5+ smoke tests
- `backend/tests/unit/test_resume_eval_smoke.py` — new file with 5+ smoke tests
- `backend/tests/unit/test_celery_app_smoke.py` — new file with 5+ smoke tests
- `backend/tests/unit/test_pipeline_steps_smoke.py` — new file with 5+ smoke tests
