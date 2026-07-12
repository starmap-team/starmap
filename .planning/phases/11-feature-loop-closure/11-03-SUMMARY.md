---
phase: 11-feature-loop-closure
plan: 11-03
wave: 1
requirements: [LOOP-05]
decision_refs: [D-10]
status: complete
---

# 11-03 Summary: JD 抽取 → PositionRecord 自动创建

## Accomplishments

1. **_write_extraction_to_pg() function** — Added to `backend/app/api/v1/extract.py`: async function that upserts `PositionRecord` and `SkillRecord` in PostgreSQL after successful JD/resume extraction. Uses `ON CONFLICT DO UPDATE` for idempotency.
2. **AsyncSession dependency** — Added `session: AsyncSession = Depends(get_db_session)` to both `extract_jd()` and `extract_resume()` endpoints.
3. **Non-blocking PG writes** — PG write failure is caught with try/except and logged as warning; extraction result is still returned to client regardless.

## User-facing Changes

- After JD extraction, `/positions` endpoint now returns the extracted position
- SkillRecords are automatically created for extracted skills
- PG write failure does not block the extraction response

## Files Modified

- `backend/app/api/v1/extract.py` — Added `_write_extraction_to_pg()`, `AsyncSession` + `get_db_session` imports, session dependency on both endpoints, PG write calls

## UAT Verification

- ✅ Code verified: `_write_extraction_to_pg()` at extract.py:124 with proper upsert logic
- ✅ Called from `extract_jd()` (line 232) and `extract_resume()` (line 291)
- ✅ Non-blocking error handling with logger.warning
- ✅ GET /positions returns 36 positions from prior extractions
