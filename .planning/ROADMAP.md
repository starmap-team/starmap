# Roadmap: StarMap v2.1 真实数据切换

**Created:** 2026-07-09
**Milestone:** v2.1 — 真实数据切换
**Total phases:** 3
**Total requirements:** 16

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 8 | 后端清理与配置 | 4/4 | Complete   | 2026-07-09 |
| 9 | 前端关闭 Mock | 关闭 MSW、删除 placeholder、清理 mock 文件、配置 Vite 代理 | MSW-01~04 (4) | 0 MSW 拦截、0 placeholder 图表、Vite proxy 到后端、无 mock 目录 |
| 10 | Pipeline 端到端验证 | 确保 Playwright 可用、代理可配、Pipeline 可触发、数据端到端贯通 | PIPE-01~04 (4) | pipeline run 成功完成、Neo4j 有真实数据、前端展示真实数据 |

**Coverage:** 100% (16/16 requirements mapped across 3 phases)

---

## Phase 8: 后端清理与配置

**Goal:** 移除所有 demo/auto-seed 逻辑，配置 LLM/DB 启动校验，确保后端返回真实数据。

**Requirements:**
- DEMO-01 ~ DEMO-04 (4) — 后端清理 Demo
- CFG-01 ~ CFG-04 (4) — LLM + DB 配置校验


**Plans:** 4/4 plans complete

Plans:
- [x] 08-01-PLAN.md - 后端 demo 清理（auto-seed 移除、reset-demo 端点删除、seed 引用清理、脚本归档）
- [x] 08-02-PLAN.md - LLM/DB 配置校验（model_validator LLM key warning、.env.example 补全）
- [x] 08-03-PLAN.md - 健康检查增强（/health/detail 端点：4 服务 ping + 3 LLM key 布尔 + demo 指示）
- [x] 08-04-PLAN.md - 前端 demo 协调清理（删 useAdminReset.ts、datasource.ts resetToDemo、schema.ts resetDemoData、Admin.vue 按钮）

**Success criteria:**
1. `admin.py` 中无 `_DEMO_REVIEW_SEED` 常量和 auto-seed 逻辑
2. `/admin/seed/reset` 和 `/reset-demo` 端点已删除，`ResetDemoResponse` 模型已删除
3. `quality.py` 不再推荐运行 `seed_expansion_data_demo.py`
4. `seed_*_demo.py` 脚本移至 `scripts/archive/` 或有 `ARCHIVE` 注释
5. 后端启动时 LLM key 和 DB 密码未配置则输出 WARNING
6. `/health/detail` 返回 Neo4j/PG/Redis/LLM 连接状态
7. `.env.example` 包含所有 LLM/DB 字段及注释

**Key files:**
- `backend/app/api/v1/admin.py` — `_DEMO_REVIEW_SEED`, auto-seed, reset-demo
- `backend/app/api/v1/quality.py` — seed 引用
- `backend/app/config.py` — 启动校验
- `backend/app/api/v1/health.py` — /health/detail
- `.env.example` — 模板完善
- `backend/scripts/seed_*_demo.py` — 归档
- `scripts/seed_demo_data.py` — 归档

---

## Phase 9: 前端关闭 Mock

**Goal:** 关闭 MSW Mock，删除 placeholder 图表，配置 Vite 代理，确保前端走真实后端 API。

**Requirements:**
- MSW-01 ~ MSW-04 (4) — 前端关闭 Mock

**Success criteria:**
1. `main.ts` 中 `enableMocking()` 已注释或移除
2. `VITE_USE_MSW=false` 为默认行为（Docker Compose + 本地开发）
3. `useDashboardCharts.ts` 中无 `getPlaceholder*` 函数，后端无数据时显示空状态
4. `vite.config.ts` 有 `/api/v1` 代理到 `http://localhost:8000`
5. `frontend/src/mock/` 目录和 `frontend/public/mockServiceWorker.js` 已删除
6. `vue-tsc --noEmit` 和 `eslint` 通过

**Key files:**
- `frontend/src/main.ts` — enableMocking()
- `frontend/src/mock/msw-browser.ts` — MSW 初始化
- `frontend/src/mock/handlers.ts` — mock 数据
- `frontend/src/composables/useDashboardCharts.ts` — placeholder 函数
- `frontend/vite.config.ts` — proxy 配置
- `frontend/public/mockServiceWorker.js` — MSW worker

---

## Phase 10: Pipeline 端到端验证

**Goal:** 确保 Playwright 安装、代理可配、Pipeline 可触发，数据从爬取到前端展示端到端贯通。

**Requirements:**
- PIPE-01 ~ PIPE-04 (4) — 爬虫 Pipeline 可用

**Success criteria:**
1. `backend/Dockerfile.dev` 安装了 playwright + chromium
2. `PROXY_LIST` 环境变量可配置，boss 爬虫通过代理抓取
3. 一次 pipeline run 可成功完成（crawl → dedup → clean → import → graph_sync）
4. Neo4j 中有真实爬取的技能/岗位数据
5. 前端图谱页面展示真实数据节点（非 mock 硬编码的 5 个职位）
6. `pytest` 全部通过（无回归）

**Key files:**
- `backend/Dockerfile.dev` — Playwright 安装
- `crawler/spiders/boss.py` — 代理配置
- `crawler/config.py` — PROXY_LIST 支持
- `backend/app/core/pipeline/executor.py` — pipeline 触发
- `docker-compose.dev.yml` — 环境变量

---

## ▶ Next Up

**Phase 8: 后端清理与配置** — 移除 demo 数据逻辑、配置 LLM/DB 校验

执行命令: `/gsd-discuss-phase 8` 或 `/gsd-plan-phase 8`
