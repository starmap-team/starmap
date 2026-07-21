# 寻路 LANDING — StarMap 任务 → 文档 → 代码 三索引

> **生成日期**: 2026-07-20
> **用途**:新人 / 接手模块 / 修特定 bug 时,从"我要做什么"出发直接定位到正确文件。
> **关系**: `README.md`(项目根)→ `ONBOARDING.md`(1 天认知)→ `CLAUDE.md`(项目规则)
> → 本文件(任务寻路)→ `docs/standards/00-总纲/01-项目规范总纲.md`(强制规范)

---

## 0. 寻路速查(高频任务)

| 我想… | 先看 | 然后去 |
|---|---|---|
| 1 天内熟悉项目 | `ONBOARDING.md` | 本文件 + `standards/README.md` |
| 了解强制规范 | `CLAUDE.md` | `standards/00-总纲/01-项目规范总纲.md` |
| 跑起来 | `README.md §快速开始` | `scripts/` 或 docker compose |
| 修一个 API | `standards/04-contracts/01-API契约规范.md` | `starmap-contracts/openapi.yaml` → `backend/app/api/v1/` → `npm run gen:api` |
| 写一个新后端模块 | `standards/00-总纲/01` + `01-backend/02-API路由层` | `core/` (业务) 或 `services/` (图) |
| 写一个新前端页面 | `standards/02-frontend/01-入口与路由` + `05-页面组件规范` | `frontend/src/pages/` |
| 添加 Pinia store | `standards/02-frontend/03-Pinia状态管理` | `frontend/src/stores/` |
| 添加 Composables | `standards/02-frontend/04-Composables规范` | `frontend/src/composables/` |
| 看当前 P0 | `docs/standards/99-appendix/01-已知问题清单.md §0` | `docs/fix_plan_p0_2026-07-20.md` |
| 看关闭了的旧 P0 | `docs/standards/99-appendix/01 §9` | `docs/archive/2026-07-16-audit-49-items-closed.md` |
| 加 Alembic 迁移 | `standards/01-backend/10-数据模型-models` | `backend/alembic/versions/` |
| 加 Celery 任务 | `standards/01-backend/11-异步任务-tasks` | `backend/app/tasks/` |
| 加 Neo4j 图查询 | `standards/01-backend/09-服务层-services` | `backend/app/services/` + Cypher 模板 |
| 跑 baseline 评估 | `standards/05-evaluation/01-评估套件规范` | `python evaluation/run_baseline.py` |
| 跑真实 LLM 评估 | 同上 + `evaluation/AGENTS.md` | `python evaluation/run_real_eval.py` |
| 加 e2e 冒烟 | `standards/06-testing/01-E2E与集成测试规范` | `tests/e2e/` |
| 改 CI 流水线 | `standards/07-devops/01-CI-CD规范` | `.github/workflows/ci.yml` |
| 改 Docker 部署 | `standards/07-devops/02-Docker与部署规范` | `docker-compose.{dev,prod}.yml` |
| 改爬虫 | `standards/03-crawler/01-爬虫模块规范` | `crawler/spiders/` + `crawler/pipelines/` |
| 文档数字与代码不一致 | `standards/README.md §硬数字核对表` | `.github/workflows/doc-lint.yml` |

---

## 1. 按数据流定位

### 1.1 JD 抽取流
```
JD 文本
  └─► [POST /extract/jd]   backend/app/api/v1/extract.py
        └─► extract/jd     backend/app/core/extraction/jd_extract.py
              ├─► llm_client      backend/app/core/extraction/llm_client.py (MiMo/星火/DeepSeek/Qwen)
              ├─► prompt          backend/app/core/extraction/prompt.py (版本化)
              ├─► normalize       backend/app/core/extraction/normalize.py (Chroma 去重)
              └─► graph_writer    backend/app/core/extraction/graph_writer.py (反幻觉/信任度)
                    └─► Neo4j     services/graph*.py
```
规范: `standards/01-backend/03-业务核心-extraction.md`

### 1.2 简历匹配流
```
简历文件
  └─► [POST /match/diagnose]    backend/app/api/v1/match.py
        └─► services/match.py  (技能对比 / 差距 / 学习路径)
              ├─► core/matching/ (评分算法)
              └─► core/learning/ (路径生成)
```
规范: `standards/01-backend/06-业务核心-matching.md` + `05-业务核心-learning.md`

### 1.3 演化流
```
Neo4j 快照
  └─► [POST /evolution/diff]   backend/app/api/v1/evolution.py
        └─► core/evolution/ (当前正在重构,旧文件陆续删除)
              ├─► diff_engine (D)
              ├─► emergence_finder
              ├─► orchestrator (D)
              ├─► trust_integration (D)
              └─► path_recommender (D)
```
规范: `standards/01-backend/04-业务核心-evolution.md`(旧) /
`standards/01-backend/04-业务核心-evolution-v2.md`(新版,本次 PR-6 新增)

### 1.4 数据流水线(三套并行)
```
ETL DAG  : core/pipeline/orchestrator.py + executor.py     (Celery)
Loop     : core/pipeline/loop_orchestrator.py             (同步 5 步)
求职者   : app/pipeline/engine.py + steps.py              (SSE 流)
```
规范: `standards/01-backend/07-业务核心-pipeline.md` /
深度分析: `docs/pipeline_deep_analysis.md`(2026-07-19)

---

## 2. 按"层"定位

| 层 | 文件夹 | 规范 | 入口 |
|---|---|---|---|
| 路由 | `backend/app/api/v1/` | `01-backend/02-API路由层` | `router.py` 汇总 |
| 业务核心 | `backend/app/core/{extraction,evolution,matching,learning,pipeline,dashboard}/` | 各自规范 | 各自 `__init__.py` |
| 服务层(图谱优先) | `backend/app/services/` | `01-backend/09-服务层-services` | graph_*.py / match.py / resume.py |
| ORM | `backend/app/models/` | `01-backend/10-数据模型-models` | `app.db` session |
| 迁移 | `backend/alembic/versions/` | 同上 | `001_initial_migration.py` 起始 |
| 任务 | `backend/app/tasks/` | `01-backend/11-异步任务-tasks` | `celery_app.py` |
| 契约 | `starmap-contracts/` | `04-contracts/01-API契约规范` | `openapi.yaml` 唯一事实源 |
| 前端路由 | `frontend/src/router/` | `02-frontend/01-入口与路由` | `index.ts` |
| 前端 API | `frontend/src/api/` | `02-frontend/02-API调用层` | `request.ts` + `schema.ts`(gen 出来) |
| 前端 store | `frontend/src/stores/` | `02-frontend/03-Pinia状态管理` | `*.ts` |
| 前端页面 | `frontend/src/pages/` | `02-frontend/05-页面组件规范` | `*.vue` |
| 前端组件 | `frontend/src/components/` | `02-frontend/06-通用组件规范` | `*.vue` |
| 前端组合函数 | `frontend/src/composables/` | `02-frontend/04-Composables规范` | `*.ts` |
| 评估 | `evaluation/` | `05-evaluation/01-评估套件规范` | `run_real_eval.py`(需凭据)/ `run_baseline.py` |
| 爬虫 | `crawler/spiders/` | `03-crawler/01-爬虫模块规范` | `boss.py` / `lagou*.py` / `job51*.py` |
| 文档索引 | `docs/standards/` | 本文件 | `standards/README.md` |

---

## 3. 按"诊断"定位

### 3.1 "我的测试挂了"
1. 看 `pytest` 报错的文件路径
2. 路径前缀 → 用 §2 表 → 找到规范
3. 错误信息 → 搜索规范中对应章节
4. 如果是新引入的功能 → `standards/README.md §硬数字核对表` 可能已经登记过类似漂移

### 3.2 "前端 lint / typecheck 挂了"
1. 看错误是 ESLint 还是 vue-tsc
2. ESLint 0 警告是目标(自 `ea107e2` 起),3D-force-graph 相关豁免
3. vue-tsc 0 错误是目标

### 3.3 "openapi.yaml 与代码不一致"
- 直接跑:`python starmap-contracts/validate.py`
- 详细分析:`backend` CI 任务末尾的"契约一致性校验"步骤

### 3.4 "Neo4j 没数据"
1. 是否跑过数据流水线?看 `docs/standards/99-appendix/01 §0 PIPE-P0-3`(当前 Open)
2. 是否爬虫数据落库?看 `PIPE-P0-2`
3. 临时调试:`docker exec starmap-neo4j cypher-shell -u neo4j -p starmap123456 "MATCH (n) RETURN count(n)"`

### 3.5 "覆盖率掉了"
- 跑:`cd backend && poetry run pytest --cov`
- 门禁:≥60%(README 写的);实际历史 80.42% 远超
- 如果掉了:可能不是测试缺失,而是新增未测代码 → `standards/01-backend/13-后端测试规范`

### 3.6 "我不知道为什么这块代码这样写"
1. `git log --follow <file>` 看历史
2. `git blame <file>` 看行级作者
3. 找 commit message 中的 `fix(XXX)`,其中 `XXX` 通常映射到 ONBOARDING/99-appendix 的 ID

---

## 4. 按"团队角色"定位

### 后端开发
- 入口: `backend/app/main.py` + `config.py`
- 规范: `standards/01-backend/*`(13 篇)
- 测试: `backend/tests/` (pytest) + `tests/integration/api-integration.test.ts`
- e2e: `tests/e2e/smoke_test.py`

### 前端开发
- 入口: `frontend/src/main.ts` + `App.vue` + `router/index.ts`
- 规范: `standards/02-frontend/*`(8 篇)
- 测试: `frontend/src/**/__tests__/`
- e2e: `frontend/e2e/*.spec.ts` + `tests/e2e/browser_*`

### 算法 / LLM
- 入口: `backend/app/core/extraction/` + `evolution/`
- 规范: `standards/01-backend/03` + `04`
- 评估: `evaluation/` + `golden_set*.jsonl`
- LLM 客户端: `extraction/llm_client.py`(多供应商 + 降级链)

### 爬虫 / 数据采集
- 入口: `crawler/spiders/boss.py`
- 规范: `standards/03-crawler/01-爬虫模块规范`
- 合规: `crawler/compliance.py`(rate limit + robots)

### QA / 评估
- 入口: `evaluation/run_baseline.py`(关键词基线)
- 入口: `evaluation/run_real_eval.py`(真实 LLM 端到端)
- 入口: `evaluation/judge_eval.py`(LLM-as-judge,默认关)
- 规范: `standards/05-evaluation/01-评估套件规范` + `06-testing/01-E2E与集成测试规范`

### DevOps / 部署
- 入口: `docker-compose.dev.yml` / `prod.yml`
- 规范: `standards/07-devops/02-Docker与部署规范` + `01-CI-CD规范`
- CI: `.github/workflows/ci.yml` + `doc-lint.yml`(本次 PR-2 新增)

---

## 5. 注意事项(读这份索引前请知)

1. **硬数字以代码为准**:`standards/README.md` 顶部核对表 + `.github/workflows/doc-lint.yml`
   在每次 PR 自动跑漂移检查。
2. **本文件持续被更新**:因为新增模块会扩寻路表,所以请用 git history 查"何时加的"。
3. **不要把本文件当规范**:它只指引"去哪查";规范原文在 `standards/<layer>/`。
4. **遇到 404 / 文件已删**:把 `git log --diff-filter=D --summary | grep delete`
   输出贴到 ISSUE;多数是正在重构中,不是真缺。

---

## 6. 与其它索引的关系

| 文件 | 用途 | 是否覆盖本文 |
|---|---|---|
| `README.md` | 项目根入口,部署 + 工作流 | 不覆盖(只引出 standards/) |
| `ONBOARDING.md` | 1 天认知 + 52 项风险历史 | 部分覆盖(但 ONBOARDING §5 已陈旧,见本文 §1.3) |
| `CLAUDE.md` | 项目规则/契约/约定 | 不覆盖 |
| `docs/standards/README.md` | standards 树总索引 + 硬数字核对表 | 部分覆盖(任务寻路表重复,见 PR-1 备注) |
| `docs/standards/99-appendix/01-已知问题清单.md` | 已知问题 + 已关闭 | 不覆盖 |
| `.planning/STATE.md` | 项目状态(过时,见 `STATE.md.v4-active-sprint.md`) | 不覆盖 |