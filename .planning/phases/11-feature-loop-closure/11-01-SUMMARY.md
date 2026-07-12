---
phase: 11-feature-loop-closure
plan: 11-01
wave: 1
requirements: [LOOP-01]
decision_refs: [D-01, D-02, D-03]
status: complete
---

# 11-01 Summary: 认证登录端点 + 登录页面

## Accomplishments

1. **Backend auth config** — Added `auth_users: str` and `token_expire_hours: int` fields to `Settings` in `config.py`, plus `parsed_users` property that parses `username:password:role` comma-delimited format.
2. **POST /auth/login endpoint** — Created `backend/app/api/v1/auth.py` with `_encode_jwt()` (HMAC-SHA256 signing compatible with `_decode_token()`) and `login()` endpoint that validates credentials against `settings.parsed_users`, returns JWT token + user info.
3. **Auth router registration** — Added `auth_router` (without auth dependency) to `router.py` and mounted at `/api/v1` in `main.py`. Login endpoint itself doesn't require authentication.
4. **Login.vue page** — Created `frontend/src/pages/Login.vue` with Element Plus form (username/password inputs, show-password toggle, "登 录" button). On success stores JWT in localStorage and redirects to `/` (or `?redirect` path).
5. **Router update** — Changed `/login` route to lazy-load `Login.vue` with `meta: { requiresAuth: false }`.

## User-facing Changes

- New `/login` page with centered card layout, "⭐ StarMap 星图" branding
- Unauthenticated access to protected routes redirects to `/login?redirect=...`
- Login stores JWT in `localStorage.starmap_token`
- Token expiry checked client-side in `decodeToken()`

## Files Modified

- `backend/app/config.py` — Added `auth_users`, `token_expire_hours`, `parsed_users`
- `backend/app/api/v1/auth.py` — NEW: Login endpoint + JWT signing
- `backend/app/api/v1/router.py` — Added `auth_router`
- `backend/app/main.py` — Mounted `auth_router` at `/api/v1`
- `frontend/src/pages/Login.vue` — NEW: Login page
- `frontend/src/router/index.ts` — Updated `/login` route
- `frontend/src/stores/user.ts` — Added `decodeToken()` expiry check, `clearUser()` clears localStorage, `logout()`
- `.env.example` — Added `AUTH_USERS` and `TOKEN_EXPIRE_HOURS`

## UAT Verification

- ✅ POST /auth/login with valid credentials → 200 + JWT + user info
- ✅ POST /auth/login with invalid credentials → 401
- ✅ Token decodable by `_decode_token()`, works on protected endpoints
- ✅ Login page renders correctly, login redirects to /
- ✅ Unauthenticated redirect to /login?redirect=... works
