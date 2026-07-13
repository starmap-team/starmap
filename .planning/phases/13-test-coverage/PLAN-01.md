---
wave: 1
depends_on: []
files_modified:
  - backend/app/dependencies.py
  - backend/app/services/graph_overview.py
  - backend/app/api/v1/loop.py
  - backend/app/api/v1/match.py
  - backend/app/main.py
  - backend/app/exceptions.py
  - backend/tests/unit/test_auth_service.py
  - backend/tests/unit/test_admin_endpoints.py
  - backend/tests/unit/test_cancel_run.py
  - backend/tests/integration/test_extraction_api.py
  - backend/tests/unit/test_learning_api.py
  - backend/tests/unit/test_ap07_fe02.py
  - backend/tests/unit/test_datasource_service.py
  - backend/tests/unit/test_evolution_sub_api.py
  - backend/tests/unit/test_health.py
  - backend/tests/unit/test_pipeline_orchestrator.py
  - backend/tests/unit/test_match_coverage_gaps.py
  - backend/tests/unit/test_match_diagnosis_reliability.py
  - backend/tests/unit/test_run_match.py
autonomous: true
requirements: [TEST-01, TEST-02]
---

# PLAN-01: Bug Fixes for 41 Failing Tests

**Wave:** 1 (no dependencies)
**Goal:** Fix all 41 failing tests by fixing the underlying project code bugs and test infrastructure issues, per DEC-021 (test failures = project bugs) and DEC-022 (bug-fix first, then fill gaps).

## Tasks

### Task 1.1: Fix `_decode_token` in dependencies.py for PyJWT compatibility (Category A+F, 12 failures)

<read_first>
- backend/app/dependencies.py (lines 52-72)
- backend/tests/unit/test_auth_service.py
- backend/tests/unit/test_admin_endpoints.py
</read_first>

<action>
In `backend/app/dependencies.py`, modify the `_decode_token` function (lines 52-72) to:

1. Add pre-validation BEFORE calling `_jwt.decode()`: check that the token string has exactly 3 dot-separated parts. If not, raise `ValueError("Invalid JWT format")`.

2. Change `options["require"]` from `["exp", "iat", "sub"]` to `["iat", "sub"]` — `exp` should be optional (tokens without `exp` never expire, which is valid).

3. Reorder the except clauses to catch `_jwt.ExpiredSignatureError` FIRST (before the generic `_jwt.InvalidTokenError`), raising `ValueError("JWT expired")`.

4. Add a specific catch for `_jwt.InvalidSignatureError` (before `_jwt.InvalidTokenError`), raising `ValueError("Invalid JWT signature")`.

5. Keep the generic `_jwt.InvalidTokenError` catch as the last handler, raising `ValueError(f"Invalid JWT: {e}")`.

6. Ensure `settings.jwt_leeway_seconds` is accessed as `int(settings.jwt_leeway_seconds)` to prevent MagicMock passthrough in tests.

The resulting function structure should be:
```
def _decode_token(token: str) -> dict[str, Any]:
    import jwt as _jwt
    from datetime import timedelta

    # Pre-validation: JWT must have 3 dot-separated parts
    if token.count(".") != 2:
        raise ValueError("Invalid JWT format")

    try:
        payload = _jwt.decode(
            token, settings.secret_key, algorithms=["HS256"],
            leeway=timedelta(seconds=int(settings.jwt_leeway_seconds)),
            options={"require": ["iat", "sub"], "verify_aud": False},
        )
    except _jwt.ExpiredSignatureError as e:
        raise ValueError("JWT expired") from e
    except _jwt.InvalidSignatureError as e:
        raise ValueError("Invalid JWT signature") from e
    except _jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT: {e}") from e
    return payload
```
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_auth_service.py -v` — all tests pass (0 failed)
- `cd backend && poetry run pytest tests/unit/test_admin_endpoints.py -v` — all tests pass (0 failed)
- `_decode_token` raises `ValueError("Invalid JWT format")` for tokens without 3 dot-separated parts
- `_decode_token` raises `ValueError("JWT expired")` for expired tokens
- `_decode_token` raises `ValueError("Invalid JWT signature")` for tampered signatures
- `_decode_token` accepts tokens without `exp` claim (they never expire)
- `settings.jwt_leeway_seconds` is cast to `int()` to prevent MagicMock passthrough
</acceptance_criteria>

---

### Task 1.2: Fix UnboundLocalError in graph_overview.py (Category D, 4 failures)

<read_first>
- backend/app/services/graph_overview.py (lines 79-193 and 196-298)
- backend/tests/unit/test_graph_services.py
</read_first>

<action>
In `backend/app/services/graph_overview.py`, fix both `fetch_overview_by_tech_stack()` (line ~169) and `fetch_overview_by_level()` (line ~274):

In each function, initialize the `independent_pos`, `independent_skill`, and `independent_edge` variables BEFORE the second try block (the one that queries Neo4j for independent counts). Set them to their fallback values:

For `fetch_overview_by_tech_stack()` (before line 169):
```python
independent_pos = total_pos
independent_skill = total_skill
independent_edge = len(connections)
```

For `fetch_overview_by_level()` (before line 274):
```python
independent_pos = total_pos
independent_skill = total_skill
independent_edge = len(connections)
```

This ensures that if the `async for` loop yields zero records (e.g., mock returns empty list), the variables already have fallback values instead of being unbound.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_graph_services.py -v` — all tests pass (0 failed)
- No `UnboundLocalError` when Neo4j query returns zero records
- Both `fetch_overview_by_tech_stack` and `fetch_overview_by_level` return valid `independent_positions`, `independent_skills`, `independent_edges` keys
</acceptance_criteria>

---

### Task 1.3: Add domain exception handlers for cancel_run and match API (Category B+M, 6 failures)

<read_first>
- backend/app/main.py (lines 149-171)
- backend/app/exceptions.py
- backend/app/core/pipeline/orchestrator.py (lines 34-39, RunNotFoundError, RunAlreadyTerminalError)
- backend/tests/unit/test_cancel_run.py
- backend/tests/unit/test_match_coverage_gaps.py
- backend/tests/unit/test_match_diagnosis_reliability.py
- backend/tests/unit/test_run_match.py
</read_first>

<action>
1. In `backend/app/exceptions.py`, add two new domain exception classes after the existing ones:
   - `RunNotFoundError(StarMapError)` — with `__init__(self, run_id: str)` and message `f"Pipeline run {run_id} not found"`
   - `RunAlreadyTerminalError(StarMapError)` — with `__init__(self, status: str)` and message `f"Run already in terminal state: {status}"`

2. In `backend/app/core/pipeline/orchestrator.py`, change the existing `RunNotFoundError` and `RunAlreadyTerminalError` classes (lines 34-39) to import from `app.exceptions` instead of defining them locally. Remove the local class definitions and add:
   ```python
   from app.exceptions import RunNotFoundError, RunAlreadyTerminalError
   ```

3. In `backend/app/main.py`, add two new exception handlers after the existing `PositionNotFoundError` handler (after line 155):
   ```python
   from app.exceptions import RunNotFoundError, RunAlreadyTerminalError

   @app.exception_handler(RunNotFoundError)
   async def run_not_found_handler(request, exc):
       return JSONResponse(status_code=404, content={"detail": str(exc)})

   @app.exception_handler(RunAlreadyTerminalError)
   async def run_already_terminal_handler(request, exc):
       return JSONResponse(status_code=409, content={"detail": str(exc)})
   ```

4. The pipeline routes (`backend/app/api/v1/pipeline/routes.py`, lines 161-169) already catch `RunNotFoundError` and `RunAlreadyTerminalError` locally — these will continue to work. The global handlers provide a safety net for any other endpoints that might call these functions.

5. The `PositionNotFoundError` is already handled globally in `main.py` (line 153-155). The match API endpoints (`match_position`, `diagnose_match`, `get_competitiveness`, `batch_match`) call `run_match()` and `compute_competitiveness()` which raise `PositionNotFoundError`. The global handler in `main.py` already maps this to 404. The tests that call these functions directly (not via TestClient) need to be updated to expect `PositionNotFoundError` instead of `HTTPException`.

6. Update the following test files to expect domain exceptions instead of `HTTPException`:
   - `tests/unit/test_cancel_run.py` — change `HTTPException(status_code=404)` expectations to `RunNotFoundError`, and `HTTPException(status_code=409)` to `RunAlreadyTerminalError`
   - `tests/unit/test_match_coverage_gaps.py` — change `HTTPException(status_code=404)` expectations to `PositionNotFoundError`
   - `tests/unit/test_match_diagnosis_reliability.py` — same as above
   - `tests/unit/test_run_match.py` — same as above
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_cancel_run.py -v` — all tests pass
- `cd backend && poetry run pytest tests/unit/test_match_coverage_gaps.py tests/unit/test_match_diagnosis_reliability.py tests/unit/test_run_match.py -v` — all tests pass
- `RunNotFoundError` and `RunAlreadyTerminalError` are defined in `app/exceptions.py` and imported in `orchestrator.py`
- Global exception handlers in `main.py` map `RunNotFoundError` → 404 and `RunAlreadyTerminalError` → 409
- Tests that call core functions directly expect domain exceptions, not HTTPException
</acceptance_criteria>

---

### Task 1.4: Fix LoopRunRequest empty target validation (Category K, 2 failures)

<read_first>
- backend/app/api/v1/loop.py (lines 30-36, LoopRunRequest class)
- backend/tests/unit/test_loop_api.py
- backend/tests/unit/test_loop_service.py
</read_first>

<action>
In `backend/app/api/v1/loop.py`, add a `field_validator` to the `LoopRunRequest` class (line 30) that rejects empty/whitespace-only strings for `target_position` while still allowing `None`:

```python
from pydantic import BaseModel, Field, field_validator

class LoopRunRequest(BaseModel):
    jd_text: str = Field(..., min_length=1, description="Raw JD text to process")
    target_position: str | None = Field(
        default=None, description="Target position name for match diagnosis (optional, LOOP-09)"
    )

    @field_validator("target_position")
    @classmethod
    def reject_empty_string(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("target_position must be non-empty if provided")
        return v
```

This ensures that `target_position=""` returns 422 validation error, while `target_position=None` is accepted.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_loop_api.py tests/unit/test_loop_service.py -v` — all tests pass
- POST /loop/run with `target_position=""` returns 422 validation error
- POST /loop/run with `target_position=None` is accepted
- POST /loop/run with `target_position="Python"` is accepted
</acceptance_criteria>

---

### Task 1.5: Fix health endpoint demo_data key (Category J, 1 failure)

<read_first>
- backend/app/main.py (lines 206-239, `_detailed_health_payload`)
- backend/tests/unit/test_health.py
</read_first>

<action>
In `backend/app/main.py`, modify `_detailed_health_payload()` (line 239) to add a `demo_data` key for backward compatibility with the existing API contract. Map from the new `data_stats` structure:

Change the return statement (line 239) from:
```python
return {"services": services, "llm_keys": llm_keys, "data_stats": data_stats}
```
to:
```python
return {
    "services": services,
    "llm_keys": llm_keys,
    "data_stats": data_stats,
    "demo_data": {
        "review_queue_seeded": data_stats["positions"] > 0,
        "pipeline_runs_count": data_stats["pipeline_runs"],
    },
}
```

This preserves backward compatibility with tests that check `body["demo_data"]`.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/unit/test_health.py -v` — all tests pass
- `/health/detail` response contains both `data_stats` and `demo_data` keys
- `demo_data.review_queue_seeded` is a boolean
- `demo_data.pipeline_runs_count` is an integer
</acceptance_criteria>

---

### Task 1.6: Fix test infrastructure issues (Categories C, E, G, H, I, L — 16 failures)

<read_first>
- backend/tests/integration/test_extraction_api.py
- backend/tests/unit/test_learning_api.py
- backend/tests/unit/test_ap07_fe02.py
- backend/tests/unit/test_datasource_service.py
- backend/tests/unit/test_evolution_sub_api.py
- backend/tests/unit/test_pipeline_orchestrator.py
</read_first>

<action>
Fix each test infrastructure issue:

1. **Category C (7 failures)** — `tests/integration/test_extraction_api.py`: Add a `db_override` fixture that overrides the `get_db_session` dependency with a mock `AsyncSession`. Add at the top of the file:
   ```python
   from app.dependencies import get_db_session
   from unittest.mock import AsyncMock

   @pytest.fixture(autouse=True)
   def override_db():
       mock_session = AsyncMock()
       app.dependency_overrides[get_db_session] = lambda: mock_session
       yield
       app.dependency_overrides.pop(get_db_session, None)
   ```

2. **Category E (3 failures)** — `tests/unit/test_learning_api.py`: In the `TestUpdateProgress` test class, mock the plan lookup query. The `FakeAsyncSession` needs to return a plan with matching `user_id` for the `select(LearningPlan).where(LearningPlan.id == pid)` query. Add a plan to the mock session's return values, or patch the entire endpoint's DB interaction.

3. **Category G (2 failures)** — `tests/unit/test_ap07_fe02.py`: Replace the `Depends(get_redis)` argument with a mock Redis client when calling `record_ab_result()` directly. Create a mock with `lpush = AsyncMock()` and pass it instead of the `Depends` object.

4. **Category H (1 failure)** — `tests/unit/test_datasource_service.py`: Change `test_invalid_status_not_in_model` to use `pytest.raises(ValidationError)` from pydantic, since Pydantic V2 validates `Literal` types at model construction time. The service-level validation is now redundant.

5. **Category I (1 failure)** — `tests/unit/test_evolution_sub_api.py`: Fix the `FakeAsyncSession` to return properly shaped result rows for the `top_pos_stmt` query. The mock needs to return rows that unpack as `(name, count)` tuples, not single objects.

6. **Category L (2 failures)** — `tests/unit/test_pipeline_orchestrator.py`: Update assertions from `len(ALL_STAGES) == 5` to `len(ALL_STAGES) == 6` and `len(stages) == 5` to `len(stages) == 6`, since `TIMESERIES` was legitimately added as a 6th stage.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest tests/integration/test_extraction_api.py -v` — all 7 tests pass
- `cd backend && poetry run pytest tests/unit/test_learning_api.py -v` — all tests pass (including TestUpdateProgress)
- `cd backend && poetry run pytest tests/unit/test_ap07_fe02.py -v` — all tests pass
- `cd backend && poetry run pytest tests/unit/test_datasource_service.py -v` — all tests pass
- `cd backend && poetry run pytest tests/unit/test_evolution_sub_api.py -v` — all tests pass
- `cd backend && poetry run pytest tests/unit/test_pipeline_orchestrator.py -v` — all tests pass
- Total: 0 failed across all previously-failing test files
</acceptance_criteria>

---

### Task 1.7: Verify all 41 failures are fixed with full regression check

<read_first>
- All test files modified in Tasks 1.1-1.6
- backend/pyproject.toml (current --cov-fail-under value)
</read_first>

<action>
Run the full backend test suite to verify:
1. All 41 previously-failing tests now pass
2. No regressions in previously-passing tests
3. Coverage is still above the current gate (60%)

Commands:
```bash
cd backend && poetry run pytest -q 2>&1 | tail -5
cd backend && poetry run pytest --cov=app --cov-report=term-missing --tb=no -q 2>&1 | grep -E "TOTAL|failed"
```

If any regressions are found, investigate and fix them before proceeding.
</action>

<acceptance_criteria>
- `cd backend && poetry run pytest -q` shows 0 failed
- Total test count >= 1500 (1511 original + 41 now passing, minus any duplicates)
- Coverage >= 60% (current gate)
- No previously-passing tests are now broken
</acceptance_criteria>

---

## Verification

1. Full backend test suite: `cd backend && poetry run pytest -q` — 0 failed
2. Per-category verification:
   - Category A+F: `poetry run pytest tests/unit/test_auth_service.py tests/unit/test_admin_endpoints.py -v`
   - Category B+M: `poetry run pytest tests/unit/test_cancel_run.py tests/unit/test_match_coverage_gaps.py tests/unit/test_match_diagnosis_reliability.py tests/unit/test_run_match.py -v`
   - Category C: `poetry run pytest tests/integration/test_extraction_api.py -v`
   - Category D: `poetry run pytest tests/unit/test_graph_services.py -v`
   - Category E: `poetry run pytest tests/unit/test_learning_api.py -v`
   - Category G: `poetry run pytest tests/unit/test_ap07_fe02.py -v`
   - Category H: `poetry run pytest tests/unit/test_datasource_service.py -v`
   - Category I: `poetry run pytest tests/unit/test_evolution_sub_api.py -v`
   - Category J: `poetry run pytest tests/unit/test_health.py -v`
   - Category K: `poetry run pytest tests/unit/test_loop_api.py tests/unit/test_loop_service.py -v`
   - Category L: `poetry run pytest tests/unit/test_pipeline_orchestrator.py -v`
3. No regressions: all previously-passing tests still pass

## Must-Haves

- [ ] All 41 previously-failing tests now pass (0 failed in full suite)
- [ ] `_decode_token` has pre-validation, specific exception handling, and `exp` is optional
- [ ] `graph_overview.py` initializes `independent_pos/skill/edge` before try block
- [ ] `RunNotFoundError` and `RunAlreadyTerminalError` are in `app/exceptions.py` with global handlers
- [ ] `LoopRunRequest.target_position` rejects empty strings via field_validator
- [ ] `/health/detail` returns `demo_data` key for backward compatibility
- [ ] No regressions in previously-passing tests

## Artifacts This Phase Produces

- Fixed `backend/app/dependencies.py` — `_decode_token` with PyJWT-compatible error handling
- Fixed `backend/app/services/graph_overview.py` — no more UnboundLocalError
- Fixed `backend/app/api/v1/loop.py` — empty target validation
- Fixed `backend/app/main.py` — `demo_data` backward compat + new exception handlers
- Fixed `backend/app/exceptions.py` — `RunNotFoundError`, `RunAlreadyTerminalError` domain exceptions
- Fixed `backend/app/core/pipeline/orchestrator.py` — imports domain exceptions from `app.exceptions`
- Fixed test files (6+ files) — test infrastructure corrections per DEC-021
