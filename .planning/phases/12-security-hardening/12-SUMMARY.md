# Phase 12 — 安全加固: Execution Summary

**Phase:** 12 — 安全加固
**Status:** ✅ Executed (3/3 waves, 4 commits, 39 new tests)
**Date:** 2026-07-13

## Wave 1: SEC-01~03 — PyJWT + bcrypt + JWT claims

**Commit:** `998743a` feat(sec-01~03): PyJWT + bcrypt + JWT claims hardening

| Task | Description | Status |
|------|-------------|--------|
| T1 | Add PyJWT>=2.8, bcrypt>=4.0 to pyproject.toml | ✅ |
| T2 | Replace _encode_jwt in auth.py with jwt.encode() | ✅ |
| T3 | Replace _decode_token in dependencies.py with jwt.decode() | ✅ |
| T4 | Add aud/iss/nbf/jti claims + Phase A enforcement | ✅ |
| T5 | Replace plaintext password comparison with _verify_password() | ✅ |
| T6 | Create hash_password.py CLI utility | ✅ |
| T7 | Write test_auth_security.py (11 tests) | ✅ |

**Key decisions:**
- Phase A: decode only requires `["exp", "iat", "sub"]`, `verify_aud=False`
- Phase B (follow-up): after `token_expire_hours`, enforce aud/iss/nbf on decode
- `jwt_leeway_seconds=30` passed as `timedelta` keyword arg (not in options dict)
- Old hand-rolled tokens still decode via PyJWT (format compatible)

## Wave 2: SEC-04 — loop IDOR fix

**Commit:** `cee34c9` feat(sec-04): loop IDOR fix — user_id column + ownership checks

| Task | Description | Status |
|------|-------------|--------|
| T1 | Add user_id column to LoopResultRecord model | ✅ |
| T2 | Create migration 009 with backfill | ✅ |
| T3 | Pass user_id through loop pipeline | ✅ |
| T4 | Add IDOR guard audit logging | ✅ |
| T5 | Write test_loop_idor.py (8 tests) | ✅ |

**Key decisions:**
- `user_id` column: nullable, `server_default="system"`, indexed
- Non-admin users only see own runs; admin sees all
- `AUTHZ_DENIED` audit event for unauthorized status checks
- HTTP 404 (not 403) to avoid information leakage

## Wave 3: SEC-05~06 — FK constraints + Settings guard

**Commit:** `de7fd0e` feat(sec-05~06): FK constraints + Settings runtime guard

| Task | Description | Status |
|------|-------------|--------|
| T1-2 | Create migration 010 with data cleanup + 6 FK constraints | ✅ |
| T3 | Add ForeignKey declarations to 4 ORM models | ✅ |
| T4 | Add safe_update() method to Settings | ✅ |
| T5 | Add Field constraints to PipelineConfigUpdateRequest | ✅ |
| T6 | Update PUT /pipeline/config (safe_update + _SCHEMA_TO_SETTINGS) | ✅ |
| T7 | Write test_settings_guard.py (20 tests) | ✅ |

**Key decisions:**
- CASCADE for strong ownership (PositionSkillRelation, LearningProgress)
- SET NULL for nullable references (ExtractionEvaluationRecord, EvolutionChangelog)
- `_mutable_config_keys` ClassVar prevents runtime mutation of sensitive fields
- `_SCHEMA_TO_SETTINGS` dict maps schema names to Settings attribute names
- `require_admin` injected as parameter (not just dependency) for audit identity

## Additional Fix

**Commit:** `53253c7` fix(test): update test_health_service.py for PyJWT migration
- Updated JWT helpers and assertions in existing tests to match PyJWT behavior

## Test Coverage

| Test File | Tests | All Pass |
|-----------|-------|----------|
| test_auth_security.py | 11 | ✅ |
| test_loop_idor.py | 8 | ✅ |
| test_settings_guard.py | 20 | ✅ |
| test_health_service.py (updated) | 22 | ✅ |
| **Total** | **61** | **✅** |

## Files Changed

### New files (6)
- `backend/app/utils/hash_password.py`
- `backend/alembic/versions/009_add_loop_results_user_id.py`
- `backend/alembic/versions/010_add_foreign_key_constraints.py`
- `backend/tests/unit/test_auth_security.py`
- `backend/tests/unit/test_loop_idor.py`
- `backend/tests/unit/test_settings_guard.py`

### Modified files (9)
- `backend/pyproject.toml` — added PyJWT, bcrypt
- `backend/app/api/v1/auth.py` — PyJWT encode, bcrypt verify, JWT claims
- `backend/app/dependencies.py` — PyJWT decode with leeway/verify_aud
- `backend/app/config.py` — JWT settings fields, plaintext rejection, safe_update()
- `backend/app/models/pipeline_models.py` — user_id column
- `backend/app/models/extraction_models.py` — ForeignKey declarations
- `backend/app/models/learning_models.py` — ForeignKey declarations
- `backend/app/models/evolution_models.py` — ForeignKey declarations
- `backend/app/api/v1/loop.py` — user_id passthrough, IDOR guard
- `backend/app/core/pipeline/loop_orchestrator.py` — user_id in run_loop/status/history
- `backend/app/api/v1/pipeline/schemas.py` — Field constraints
- `backend/app/api/v1/pipeline/routes.py` — safe_update + _SCHEMA_TO_SETTINGS
- `backend/tests/unit/test_health_service.py` — PyJWT migration

## Follow-up Tasks

1. **Phase B JWT enforcement**: After `token_expire_hours` (24h), update `_decode_token` to require `["exp", "iat", "sub", "nbf", "iss", "aud"]` and set `audience=settings.jwt_audience, issuer=settings.jwt_issuer`
2. **Migrate AUTH_USERS to bcrypt**: Use `python -m app.utils.hash_password` for all users, then set `app_env=production` to enforce bcrypt-only
3. **Apply migrations 009 and 010** on staging/production databases before deploying
