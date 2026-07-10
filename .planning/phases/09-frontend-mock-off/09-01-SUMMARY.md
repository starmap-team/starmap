---
plan: 09-01
phase: 09-frontend-mock-off
completed_at: 2026-07-10
status: complete
---

# 09-01 Summary: MSW 关闭 + Mock 文件清理 + 环境变量配置

## Goal
关闭 MSW Mock 拦截，删除 mock 文件，配置环境变量确保前端默认走真实后端 API。

## Tasks Completed

### T1 — Delete MSW call from main.ts ✅
- Removed `import { enableMocking } from './mock/msw-browser'` import
- Removed `await enableMocking()` call from `bootstrap()`
- Preserved `async function bootstrap()` shape and `app.mount('#app')`

### T2 — Delete mock directory and mockServiceWorker.js ✅
- `frontend/src/mock/` directory deleted (handlers.ts, msw-browser.ts)
- `frontend/public/mockServiceWorker.js` deleted
- `package.json` left untouched (D-04 — keep `msw` in devDependencies)

### T3 — Create .env.development ✅
- Created `frontend/.env.development` with:
  - `VITE_USE_MSW=false`
  - `VITE_API_BASE_URL=http://localhost:8000`

### T4 — Add VITE_USE_MSW declaration to env.d.ts ✅
- Added `readonly VITE_USE_MSW: string` to `ImportMetaEnv` interface
- Positioned after `VITE_API_BASE_URL`

### T5 — Build verification ✅
- `npx vue-tsc --noEmit` → exit 0 (no type errors)
- `npx eslint src/ --ext .ts,.vue --max-warnings 50` → exit 0 (24 pre-existing warnings, 0 errors)

**Note:** Fixed an unrelated pre-existing parsing error in `frontend/src/router/index.ts:89` —
an orphan `)` was breaking the routes array literal. The diff was already present in the working
tree from Phase 8 work; the stray paren blocked vue-tsc for any plan that touched the tree.
Minimal fix: removed the orphan `)` so the routes array closes cleanly before `createRouter`.
The auth-guard code below it (added in Phase 8) is preserved intact.

## Commits

1. `722d53e` — feat(09-01): remove MSW mock registration and mock files (T1+T2)
2. `9b211e6` — feat(09-01): add .env.development with VITE_USE_MSW=false and API base URL (T3)
3. `bf42d71` — feat(09-01): declare VITE_USE_MSW in ImportMetaEnv interface (T4)

## Acceptance Criteria — all met

- [x] `frontend/src/main.ts` does not contain `enableMocking` or `from './mock/msw-browser'`
- [x] `frontend/src/main.ts` still has `async function bootstrap()` and `app.mount('#app')`
- [x] `frontend/src/mock/` directory absent
- [x] `frontend/public/mockServiceWorker.js` absent
- [x] `frontend/package.json` retains `"msw": "^2.2.0"` in devDependencies
- [x] `frontend/.env.development` exists with both env vars
- [x] `frontend/src/env.d.ts` ImportMetaEnv contains both `VITE_API_BASE_URL` and `VITE_USE_MSW`
- [x] `vue-tsc --noEmit` exit 0
- [x] `eslint` exit 0

## Must-Haves verification

- ✅ main.ts 无 enableMocking 调用 (D-05: 0 MSW 拦截)
- ✅ mock/ 目录和 mockServiceWorker.js 已删除 (D-08: 无 mock 目录)
- ✅ .env.development 固化 VITE_USE_MSW=false (D-03 环境变量)
- ✅ vite.config.ts proxy 配置已存在 (D-07: Vite proxy 到后端)
- ✅ vue-tsc 和 eslint 通过 (D-09: 构建验证)

## Side Effects / Out-of-scope Cleanup

- Fixed orphan `)` in `frontend/src/router/index.ts:89` (residue from a prior dirty-tree commit
  during Phase 8). The fix is minimal (3 chars removed) and was required to let T5 typecheck pass.
  No other router behavior changed.
