# StarMap 入职手册（Onboarding）

> 生成日期：2026-07-16 · 用途：新人/后续维护快速理解项目、定位问题、认领待办
> 信息来源：README、CLAUDE.md、AGENTS.md、CHECKPOINT_REPORT.md、audit/（49 项风险全 Open）、.planning/codebase（Docker vs Local 16 项不一致）、以及后端/前端/爬虫/评估的逐模块代码探查。

---

## 0. 一句话定位

**StarMap（星图）= 信息技术领域「人才能力星云导航系统」**：构建岗位能力知识图谱，支持新岗位发现、岗位能力动态演化、图谱可视化、人岗匹配诊断。本质是「LLM 抽取技能 → 归一化+反幻觉 → 写入 Neo4j 图谱 → 匹配/演化/学习路径」的一条数据智能流水线。

---

## 1. 技术栈速览

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11–3.12 / FastAPI 0.110+ / SQLAlchemy async / Neo4j / PostgreSQL / Redis / Celery |
| 前端 | Vue 3.4+ / TS 5.4+ / Element Plus / Pinia / ECharts / @antv/G6 / Vite / Playwright(重3D: three+gsap+3d-force-graph) |
| LLM | 小米 MiMo（主）/ DeepSeek / 讯飞星火 / 本地 Qwen(Ollama)，带降级链 |
| 数据栈 | PostgreSQL(关系+用户/审计) · Neo4j(图谱) · Redis(缓存+Celery broker+JWT黑名单) · Chroma(向量归一化) |
| 测试 | pytest(~1753 函数) · vitest · Playwright · evaluation/(baseline/mock-LLM/real-LLM) |
| 质量门 | Ruff + mypy + ESLint + vue-tsc · 契约优先(openapi.yaml) · Alembic 迁移 |
| 部署 | docker-compose.dev.yml（推荐） / docker-compose.prod.yml / 主机本地 Mode B |

> 数据流速查：`JD文本 → extract/jd(LLM抽取) → 归一化 → 反幻觉(信任度) → 写入Neo4j`；`简历 → match/diagnose → 技能对比 → 差距分析 → 学习路径`；`快照 → evolution/diff → 新兴技能 → 信任聚合`。

---

## 2. 系统架构与数据流向

```
                         ┌─────────────── 采集层 crawler/ ───────────────┐
  招聘站(BOSS/拉勾/51job) │ Scrapy+Playwright(stealth)+Apify │ compliance限速 │
  + ESCO 本体            │ dedup(SimHash) → jd_raw(Postgres)            │
                         └───────────────┬──────────────────────────────┘
                                         │ run-pipeline / W3 / HTTP
                         ┌───────────────▼─────────────── 后端 backend/ ──┐
                         │ api/v1 (131 端点, router→service→core)        │
                         │ core/extraction  (LLM抽取+归一化+反幻觉)        │
                         │ core/evolution   (diff/emergence/trust/路径)    │
                         │ core/pipeline    (executor/loop/cron/quality)  │
                         │ services/ (graph/match/judge/resume/admin/...) │
                         │ tasks/ (Celery: batch_extract/build_graph/...) │
                         └───┬──────────┬───────────┬───────────┬────────┘
            PostgreSQL    Neo4j       Redis      Chroma       (SSE/事件)
            users/审计/抽取 图谱节点边  缓存/JWT   向量归一化
                         └───────────────┬───────────────┐
                         ┌───────────────▼─────────────── 前端 frontend/ ─┐
                         │ pages(19) · stores(24) · components(62) · composables(63) │
                         │ api/request.ts(双token+401静默刷新) · schema.ts(契约生成)  │
                         └──────────────────────────────────────────────────────┘
                                            ▲
                          starmap-contracts/openapi.yaml (93 路径, 16 域, 单一事实源)
```

**关键分层约定**：图查询在 `services/`，抽取/演化在 `core/`；API 变更先改 `openapi.yaml` 再 `npm run gen:api` 同步前端。

---

## 3. 目录地图（关键路径）

| 路径 | 作用 | 探查要点 |
|------|------|---------|
| `backend/app/main.py` | FastAPI 入口，`/health` `/ready` `/health/detail`，内存令牌桶限流，cron 后台循环 | 限流注释自承「多进程不安全」 |
| `backend/app/api/v1/` | 28 个路由文件，**131 端点** | 逻辑下沉到 service/core，无 501 stub |
| `backend/app/core/extraction/` | llm_client(多供应商+降级)、jd_extract、normalize(Chroma+负缓存)、prompt(版本化)、graph_writer | 真实落地层 |
| `backend/app/core/evolution/` | diff_engine、emergence_finder、hallucination_guard(反幻觉/信任)、orchestrator、path_recommender | 反幻觉/信任的真实实现处 |
| `backend/app/core/pipeline/` | executor/loop_orchestrator/cron_scheduler/quality_monitor/data_fusion/simhash | 与 `app/pipeline/`(engine/steps) 疑似双实现 |
| `backend/app/services/` | graph*(4个) / match / judge / resume / auth / admin_* / recommendation / review / timeseries | 图谱服务偏多、职责重叠 |
| `backend/app/models/` + `alembic/versions/` | ORM 拆分文件，最新迁移 `014_extend_users_for_lifecycle` | 双 initial 迁移(20260616_01 与 001)语义混乱 |
| `backend/app/tasks/` | Celery：batch_extract_jd / build_graph_from_extractions / analyze_evolution_trends 等 7 个 | broker/backend 均 Redis |
| `frontend/src/` | pages(19)/stores(24)/components(62)/composables(63) | 结构成熟，但 auth 契约缺失 |
| `frontend/src/api/` | request.ts(双token) + client.ts(已生成 schema.ts 但仅覆盖~11端点) | MSW 死依赖；19 个 store 仍直调 request |
| `crawler/` | spiders(stealth+Apify)/compliance/dedup/persistence/pipelines/scripts | 功能较全，有 11 测试，默认密码硬编码 |
| `evaluation/` | golden_set.jsonl(110) / baseline / mock-LLM / real-LLM / judge_eval | eval **未接 CI**；LLM-as-judge 死代码 |
| `starmap-contracts/` | openapi.yaml(125KB,93路径,16域) · graph_cypher(空壳) · CONTRACT_AUDIT.md | /auth 路径缺失；Cypher 模板空白 |
| `audit/` | 00-summary / 99-risk-register(49 风险全 Open) / phase-01..11 / 98-ai-antipatterns | 安全金矿，全部未关闭 |
| `.planning/` | ROADMAP / STATE / TASK_CHECKLIST / codebase/(DOCKER-VS-LOCAL 16 项不一致) | 配置真相源混乱 |
| `docs/` | 设计文档 v2.0(117KB) / docx(1.8MB) / core / ontology / evolution / bugs / qa / onboarding | 很全，但部分与代码漂移 |

---

## 4. 各模块成熟度评估

| 模块 | 成熟度 | 核心结论 |
|------|--------|---------|
| **后端** | 高（~95% 端点真实） | 分层清晰、鉴权/审计/安全中间件齐备、测试密度高；风险在「模块冗余/死代码 + 部分服务缺测试」而非功能缺失 |
| **前端** | 中-高 | 结构强（62 组件/24 store/63 composable/严格 TS/双 token）；但 auth 契约缺失、MSW 死依赖、typed-client 仅覆盖 11 端点、`as any` 357 处、`useAuthBootstrap` 从未被启动调用 |
| **爬虫** | 中 | boss/lagou_stealth/job51_stealth/Apify 可用；HTTP 版(PoC)被 WAF 拦；BOSS 字段抽取全 None；robots 被禁止仍抓取；硬编码默认密码 |
| **评估/测试** | 中（但脱节） | Golden Set 真实存在(110 条)；baseline F1≈0.758、mock≈0.976、real 端到端有反幻觉；**eval/e2e 全未接 CI**；frontend 测试/Playwright 从未在 CI 跑；coverage.xml 0.37 与「60% 门禁」矛盾 |
| **契约/文档** | 中（domain 覆盖全，结构缺口大） | openapi 16 域覆盖完整；但 `/auth` 路径缺失却声明 BearerAuth、Cypher 模板空白、CONTRACT_AUDIT 已登记字段/编码/前缀冲突 |
| **审计/规划** | — | 49 风险全 Open + 16 配置不一致全 Open = **最高价值 backlog 起点** |

---

## 5. 已知问题清单（来自审计 + 规划，按优先级）

> 以下项**全部仍处于 Open 状态**，是后续发掘问题/认领待办的直接来源。优先级沿用 audit 的 P0/P1/P2/P3。

### 5.0 实测核验结论（2026-07-16，已用代码反射+运行时验证）

> **重要**：`audit/` 的 49 项风险与 `.planning` 的 16 项不一致，是在**更早代码状态**生成的，当前代码已大量修复。下面的 P0 项已逐条实证，**切勿把 49 项 Open 当作当前真相**——动手前必须像下面这样实测。

- **认证（AUTH-01）已实证**：用 FastAPI 路由依赖反射 + `get_current_user` 直接调用验证——
  - 全站 **122/137** 个 HTTP 路由挂了 `get_current_user`，其中 **42 个**额外挂 `require_admin`；仅 `/health`、`/ready`、Swagger、登录类端点公开。
  - **生产模式**（`APP_ENV=production`）：匿名请求 → 实测返回 **401**（强制鉴权）。
  - **默认模式**（`APP_ENV` 默认 `development`）：匿名请求 → 实测返回 `{'sub':'dev','role':'admin'}`（**无 token 即 admin**）。
  - **结论**：AUTH-01 的「生产级普遍缺失鉴权 / CVSS 9.8」**在代码中已解决**；审计把它误判为全局生产级漏洞。真正的残留风险是**开发旁路是默认行为**（见 P0-1）。
- **两条 P0 配置指控已实证为陈旧**：DOCKER 3.2（vite 8002）、DOCKER 3.5（Docker 前端 `starmap-backend:8000`）在当前代码中**均已修复**（见 P0-7/P0-8）。后端 uvicorn 实际绑定 `0.0.0.0:8000`，CHECKPOINT_REPORT 猜测的 127.0.0.1 不成立。

### 5.0b 配置根因：部署身份错配（头号待办，NEW-P0）

> 完整实证见 **`AUDIT_VERIFICATION.md`**。这是比单条审计 P0 更根本的问题。

- **发现**：`docker-compose.prod.yml` 经 `env_file: .env` 加载根 `.env`（含 `APP_ENV=development`），Dockerfile 的 `ENVIRONMENT=production` 构建参数未落地为运行时 `APP_ENV` → 生产部署中 `_is_prod=False`（`main.py:69`）。
- **后果**：所有 `if app_env=="production"` 守卫休眠——dev 旁路生效（匿名=admin，AUTHZ-01 修复失效）、Swagger 暴露（API-03 失效）、弱 `SECRET_KEY`/无密码 Redis 被接受（SEC-02/03/DATA-04 校验失效）、`BOOTSTRAP_SEED_ADMIN=true` 自动播种弱管理员。
- **连带缺陷**：`.env` 的 `REDIS_URI` 无密码但 Redis 容器强制 `--requirepass` → **生产 Redis 实际连不上**；compose `environment:` 注入的 `REDIS_URL`（带密码）变量名错误被忽略。Postgres/Neo4j 经 `.env` 正确变量名正常。
- **修法（不改动业务代码即可消除根因）**：新建 `.env.prod` 并让 prod compose `env_file` 指向它，设 `APP_ENV=production` / `APP_DEBUG=false` / 强 `SECRET_KEY` / `REDIS_URI=redis://:密码@redis:6379/0` / `BOOTSTRAP_SEED_ADMIN=false`；删除 compose 中错误的 `REDIS_URL`/`DATABASE_URL`。详见 `AUDIT_VERIFICATION.md` §1.4（C1–C7）。

### 5.1 P0 — 上线阻断（已实测核验）
1. **【已实证·残留风险】开发默认即匿名 admin**：`dependencies.py:100-102` 在 `app_env != "production"` 时，无 token 直接返回 `role: admin` 的 dev 用户；且 `APP_ENV` 默认 `development`（`config.py:19`）。因此**默认运行模式（含推荐的 docker-compose.dev.yml）下，全部端点含 42 个 admin 端点对匿名开放为 admin**。审计 AUTH-01 的暴露点是真的，但根因是「dev 旁路是默认」而非「没写鉴权」。**修法**：dev 旁路改为显式 opt-in（如额外 `DEV_ANON_ADMIN=true` 才允许），且 dev 用户应为低权限而非 admin；生产部署严格 `APP_ENV=production` 并加启动断言。
2. **Admin 21 端点无权限控制（AUTHZ-01, 9.1）**：任何人可删图节点/改配置/注入 prompt。
3. **`.env` 含真实 API 密钥 `sk-/tp-`（SEC-01, 9.3）**：立即轮换并移出仓库。
4. **生产无 HTTPS（API-01, 8.2）**：需 nginx + HSTS。
5. **简历姓名未脱敏直发第三方 LLM（DATA-01, 8.1）**：违反个保法，需 `mask_pii()`。
6. **Judge batch 路径遍历（INJ-01, 8.6）**：限制可读取文件路径范围。
7. **【已实证·陈旧/已修复】Docker 前端 URL**：实际 `docker-compose.dev.yml:92` 为 `VITE_API_BASE_URL=http://localhost:8000/api/v1`（浏览器侧可解析，注释明确说明走 CORS 到容器 :8000）。审计 DOCKER 3.5 描述已不成立——**无需修改**。
8. **【已实证·陈旧/已修复】vite 代理端口**：实际 `vite.config.ts:21` 代理目标为 `process.env.VITE_API_BASE_URL || 'http://localhost:8000'`，**无 8002**。审计 DOCKER 3.2 描述已不成立——**无需修改**。
9. **后端 `.py` GBK/UTF-8 乱码（P0）**：统一转 UTF-8，CI 加编码检查。
10. **API 路径前缀冲突（CONTRACT_AUDIT 1.2）**：vite `/api` 代理 + 后端 `/api/v1` 可能叠加成 `/api/api/v1`。

### 5.2 P1 — 上线前
11. 契约/实现字段不一致（CONTRACT_AUDIT 1.3）：`/match/position`、`/extract/jd`、`/graph/overview` schema 与前后端类型不符 → CI 加契约一致性校验。
12. `backend/.env` 缺 `AUTH_USERS`（DOCKER 3.1）：本地启动后无法登录。
13. 弱 `SECRET_KEY` / 弱 DB 密码 + fallback（SEC-02/03）：生成强密钥、移除 fallback。
14. IDOR：`match/learning` 无属主校验（AUTHZ-02, 6.5）。
15. 无速率限制 / Swagger 生产暴露 / 无安全响应头（API-02/03/04）。
16. Redis/Neo4j 无密码 + 端口暴露（INFRA-01/02）。
17. dev compose `depends_on` 缺 `condition: service_healthy`（首屏可能 502）。
18. 硬编码默认管理员密码 `starmap2024`（`config.py:64`）→ 强制环境变量。
19. 限流/安全头中间件改 Redis 支撑（多进程/分布式）。

### 5.3 P2/P3 — 首月 / backlog
20. 统一 Neo4j 驱动为异步（当前同步/异步混用）。
21. 收敛图谱服务模块（graph_service/graph_sync/graph_overview/graph_serializers/admin_graph_service）边界。
22. 合并双 pipeline 实现 `app/pipeline/` 与 `app/core/pipeline/`。
23. 清理空目录脚手架 `core/graph_engine/`、`core/hallucination/`、`core/trust/`（逻辑已移至 evolution/）。
24. 为无测试服务补测试：`neo4j_service`、`review_service`、`recommendation_service`、`admin_audit_service` 等。
25. Chroma 纳入资源管理与 `/ready` 健康检查（当前静默降级）。
26. `emergence_finder.py:97` TODO：阈值迁入 DB/配置表。
27. 配置项 `authority_scores` 字典硬编码（`config.py:69`）外置。
28. **【已纠正】prod compose 变量名概念错位**：`.env` 用正确名（`REDIS_URI`/`POSTGRES_*`/`NEO4J_URI`），compose `environment:` 却重复注入 `DATABASE_URL`/`REDIS_URL`（错误名，被忽略）；**仅 Redis 断连**（`.env` 的 `REDIS_URI` 无密码而容器强制密码），Postgres/Neo4j 经正确名正常。详见 `AUDIT_VERIFICATION.md` §1.2。
29. `graph_cypher/query_templates.cypher` 为空 → 补全 Cypher 模板。
30. `/match/batch` 缺 Pydantic schema（INJ-02）；无安全审计日志（LOG-05）。

### 5.4 爬虫专项
31. 硬编码 DB 密码默认值 `starmap123456`（`crawler/config.py:50`, `database.py:27`）。
32. `compliance.stealth_check_robots`(L278) 被 robots 禁止仍抓取；Apify 脚本 `robots_allowed=True`「已合规豁免」——法律姿态可疑。
33. 无 403/429 自动熔断，与 README 合规红线不符。
34. BOSS spider 缺字段抽取（company/salary/location 全 None，`boss.py:98-101`）。
35. `lagou.py:52` TODO：拉勾选择器随 2026 改版可能失效。
36. 抓取模式碎片化（Scrapy/Playwright/Apify 三套），入库逻辑重复；与 backend 强耦合（`pipeline_bridge.py` 直接 import `app.core.pipeline`）。

### 5.5 评估/测试专项
37. **eval 未接入 CI** → 加 baseline +（带 secret 的）real-eval 作业。
38. 文档漂移：`evaluation/README.md` 写「50 条」实际 `golden_set.jsonl` 110 条。
39. match/resume/pipeline Golden **无执行器**（只有 extraction 被评估）。
40. `judge_eval.py` 的 `use_llm_judge` 默认 False 且从未启用 → 接线或移除（死代码）。
41. `run_llm_eval.py` 设 `anti_hallucination_enabled=False` 却称「M2 真实评估」→ 与 `run_real_eval.py` 不一致。
42. frontend 测试/Playwright 缺 CI（`ci.yml` 未跑 `npm run test` / `playwright test`）。
43. 覆盖率门禁落空：`backend/coverage.xml` line-rate=0.3675，与「60%」矛盾 → 固化阈值并刷新。
44. `tests/e2e/` 被一次性脚本/截图/日志污染 → 清理并接 CI。
45. 前端 e2e 框架分裂（Playwright + Cypress）→ 统一 Playwright。

### 5.6 前端专项
46. `useAuthBootstrap()` 定义但**从未在启动调用** → server-truth 用户同步是死代码。
47. `openapi.yaml` 缺 `/auth/*` 与 `/admin/users*`（整个账户域无契约）→ 补并 regen `schema.ts`。
48. MSW 是死依赖（`VITE_USE_MSW` 标志 + Dockerfile 行，但无 handler）。
49. typed-client 仅覆盖 ~11/93 端点，19 个 store 仍直调 `request`；`unknown` fallback 削弱类型安全。
50. 消除 52 处 `as any`（违反 API_INTEGRATION_GUIDE §1.2）。
51. `/change-password` 路由把 `ProfileMenu.vue`（下拉组件）当整页挂 → 设计异味。
52. 前端错误仅用 status，未展示后端 `detail`（CONTRACT_AUDIT 2.2）。

---

## 6. 建议入职待办（Backlog 起点，按"先核实→再修"）

**第一周 · 核实与止血**
- [ ] **【NEW-P0·头号】部署身份错配修复**：新建 `.env.prod`，prod compose `env_file` 指向它；设 `APP_ENV=production`/`APP_DEBUG=false`/强 `SECRET_KEY`/`REDIS_URI` 带密码/`BOOTSTRAP_SEED_ADMIN=false`；删 compose 错误 `REDIS_URL`/`DATABASE_URL`。落地后 AUTHZ-01/SEC-02/03/API-03/DATA-04 的"修复"会自动生效（详见 `AUDIT_VERIFICATION.md` §1.4 C1–C7）。
- [x] **P0-1（已实证）**：认证已核实——生产强制 401（AUTH-01 在代码中已解决）；残留风险是**默认 dev 模式匿名即 admin**（dependencies.py:100-102 + config.py:19）。下一步修法：dev 旁路改为 opt-in、dev 用户降权、生产部署加 `APP_ENV=production` 断言。
- [x] **P0-7/8（已实证·陈旧）**：Docker 前端 URL（localhost:8000/api/v1）与 vite 代理端口（localhost:8000）**均已正确**，审计两条 P0 不实，无需修改。
- [ ] **P0-3**：轮换 `.env` 真实密钥并从仓库移除（确认是否被 git 历史记录）。
- [ ] **P0-10**：核查 API 前缀是否真冲突（`/api` 代理 + `/api/v1` 前缀），实测后决定。
- [ ] **P0-9**：扫描并转码 GBK `.py` 文件，加 CI 编码检查。
- [ ] **P0-5**：在简历抽取入口加 `mask_pii()`。

**第二周 · 契约与一致性**
- [ ] **P1-11/47**：补齐 `openapi.yaml` 的 `/auth`、`/admin/users` 路径并 regen `schema.ts`；加 CI 契约一致性校验。
- [ ] **P1-12/13/18**：补齐 `backend/.env` 的 `AUTH_USERS`、强密钥、移除默认密码 fallback。
- [ ] **P5.x**：前端调用 `useAuthBootstrap()`、清理 MSW 死依赖、推进 typed-client 迁移。

**第三周 · 质量与可持续**
- [ ] **P2-21~27**：收敛图谱服务/双 pipeline/空目录；补无测试服务测试；Chroma 进 `/ready`。
- [ ] **P5-37~45**：eval 接 CI、对齐 Golden 文档、启用/移除 LLM-as-judge、刷新覆盖率门禁、清理 `tests/e2e/`。

---

## 7. 本地运行与常用命令

```bash
# 全栈 Docker（推荐新手）
cp .env.example .env
docker compose -f docker-compose.dev.yml up        # 前端:5173 / API:8000/docs / Neo4j:7474

# 主机本地后端 + Docker 数据栈
docker compose -f docker-compose.dev.yml up -d neo4j postgres redis chroma
cd backend && poetry install && python -m scripts.bootstrap
poetry run uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev          # :5173

# 代码质量
cd backend && poetry run ruff check . && poetry run mypy app && poetry run pytest
cd frontend && npm run lint && npm run typecheck && npm run test
cd frontend && npm run gen:api                     # 契约 → schema.ts

# 评估
python evaluation/run_real_eval.py                 # MiMo 端到端(反幻觉)
python evaluation/run_baseline.py                  # 关键词基线 F1

# 冒烟
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

> 已知运行坑（CHECKPOINT_REPORT）：后端容器偶发 `unhealthy`（uvicorn reload 触发 healthcheck 抖动）；docker-compose.dev.yml 有未定义变量 `i` 的警告。

---

## 8. 关键文件索引（后续深挖入口）

- 安全真相：`audit/00-summary.md` · `audit/99-risk-register.md` · `audit/98-ai-antipatterns.md`
- 配置真相：`audit/` + `.planning/codebase/DOCKER-VS-LOCAL-INCONSISTENCIES.md` · `.planning/STATE.md` · `TASK_CHECKLIST.md`
- 契约：`starmap-contracts/openapi.yaml` · `CONTRACT_AUDIT.md` · `graph_cypher/query_templates.cypher`
- 设计：`docs/星图-项目设计文档v2.0.md` · `docs/INTEGRATION_REPORT.md` · `docs/CODE_INDEX.md`
- 入口：`backend/app/main.py` · `backend/app/config.py` · `frontend/src/api/request.ts` · `frontend/src/stores/user.ts`
- 评估：`evaluation/run_real_eval.py` · `evaluation/judge_eval.py` · `evaluation/golden_set.jsonl`
- CI：`.github/workflows/ci.yml`（当前不跑 eval/e2e/frontend-test）

---

## 9. 给后续"发掘问题"的提示

1. **先核实再信审计（已验证教训）**：审计 49 项 + .planning 16 项均生成于**更早代码态**，当前已大量修复。已实测：认证 AUTH-01 在生产代码中**已解决**（122/137 路由需鉴权、42 个需 admin、生产匿名→401）；但**开发模式是默认且匿名即 admin**才是真残留风险。另有 DOCKER 3.2/3.5 两条 P0 也已实证为陈旧。**正确做法：每条 Open 项都先像 §5.0 那样用代码反射/运行时实测，再决定要不要修。**
2. **配置真相源最乱**：Docker vs 本地 `.env*` 多份冲突、端口/URL 错位，是高频故障源。
3. **契约是抓手**：`openapi.yaml` 域覆盖全但缺 auth、缺 Cypher、字段漂移——以契约为锚做一致性校验能批量暴露问题。
4. **质量门禁名存实亡**：coverage 0.37、eval/e2e 不进 CI、frontend 测试不进 CI——"main 可运行"靠人工，不靠 CI。
5. **死代码/冗余较多**：双 pipeline、空 core 子目录、MSW 死依赖、LLM-as-judge 死代码——清理即减负。
