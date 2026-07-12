---
phase: 11-feature-loop-closure
plan: 11-04
wave: 2
requirements: [LOOP-02]
decision_refs: [D-04, D-05, D-06]
status: complete
---

# 11-04 Summary: SSE 连接鉴权修复

## Accomplishments

1. **useSSE.ts — EventSource token query param** — Modified `connectSSE()` to append JWT token as `?token=xxx` query parameter to EventSource URL (EventSource API doesn't support custom headers).
2. **useSSE.ts — pollOnce Authorization header** — Modified `pollOnce()` to add `Authorization: Bearer xxx` header to fetch requests.
3. **jobseeker.ts — fetch auth** — Modified `analyzeResume()` to add Authorization header and use `VITE_API_BASE_URL` instead of hardcoded URL.
4. **Backend get_current_user_sse()** — Added SSE-friendly auth dependency in `dependencies.py` that accepts token via query-param OR Authorization header. Applied to SSE endpoints in `dashboard.py` and `pipeline/routes.py`.

## User-facing Changes

- SSE connections (DataDashboard, PipelineMonitor) now authenticate with JWT token
- Production environment SSE connections no longer fail with 401
- Polling fallback also carries Authorization header

## Files Modified

- `frontend/src/composables/useSSE.ts` — Token in query param + Authorization header
- `frontend/src/stores/jobseeker.ts` — Authorization header + VITE_API_BASE_URL
- `backend/app/dependencies.py` — Added `get_current_user_sse()`
- `backend/app/api/v1/dashboard.py` — Applied `get_current_user_sse` to SSE endpoints
- `backend/app/api/v1/pipeline/routes.py` — Applied `get_current_user_sse` to SSE endpoints

## UAT Verification

- ✅ GET /dashboard/realtime?token={JWT} → HTTP 200
- ✅ GET /pipeline/events?token={JWT} → HTTP 200
- ✅ GET /dashboard/realtime-poll with Authorization header → HTTP 200
- ✅ Dev mode fallback (no token) → HTTP 200
