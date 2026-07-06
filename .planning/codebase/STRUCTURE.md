# StarMap 项目目录结构文档

> 生成日期: 2026-07-05
> 项目路径: `C:\Users\LiShuai\Desktop\Agents\starmap`

---

## 一、顶层目录映射

| 目录 | 用途 | 技术栈 |
|------|------|--------|
| `backend/` | 后端服务主模块 | Python/FastAPI + Celery |
| `frontend/` | 前端应用主模块 | Vue 3 + TypeScript + Vite |
| `crawler/` | 数据采集爬虫模块 | Python (Scrapy-like) |
| `starmap/` | 根级测试/共享包 | Python |
| `starmap-contracts/` | API契约与图查询模板 | OpenAPI + Cypher |
| `docs/` | 项目文档与设计资料 | Markdown + CSV/YAML |
| `evaluation/` | 模型评估与质量报告 | Python + JSON |
| `scripts/` | 运维脚本与数据种子 | Python + Shell |
| `tests/` | 端到端测试与浏览器QA | Python + Playwright |
| `.planning/` | 开发计划与架构文档 | Markdown + JSON |
| `.github/` | GitHub Actions工作流 | YAML |

---

## 二、关键子目录说明

### 2.1 Backend (`backend/`)

```
backend/
├── app/
│   ├── api/v1/           # REST API 路由层 (FastAPI routers)
│   ├── core/             # 核心业务逻辑 (按领域子目录组织)
│   │   ├── dashboard/    # 仪表盘与SSE广播
│   │   ├── evolution/    # 技能演化分析 (diff, emergence, hallucination guard)
│   │   ├── extraction/   # JD/简历提取 (LLM client, graph writer)
│   │   ├── learning/     # 学习路径引擎
│   │   ├── matching/     # 技能匹配服务 (scorer, path builder)
│   │   └── pipeline/     # ETL流水线 (cron, data fusion, quality monitor)
│   ├── models/           # Pydantic/SQLAlchemy 数据模型
│   ├── pipeline/         # 旧版流水线抽象 (contracts, engine, steps)
│   ├── repositories/     # 数据访问层 (position repository)
│   ├── services/         # 服务层 (dedup, graph, judge, match, neo4j, resume)
│   ├── tasks/            # Celery 异步任务
│   └── utils/            # 工具函数
├── alembic/              # 数据库迁移脚本
├── tests/                # 后端测试
│   ├── fixtures/         # 测试数据样本
│   ├── integration/      # 集成测试
│   └── unit/             # 单元测试 (按领域模块组织)
├── crawler/              # 内嵌爬虫 (与根级 crawler/ 重复)
├── docs/                 # 后端专属文档
├── openapi/              # OpenAPI 规范文件
└── scripts/              # 后端运维脚本
```

**组织模式**: 按领域驱动设计 (DDD) 分层，`core/` 内按业务领域进一步细分。

### 2.2 Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── api/              # API 请求封装
│   ├── components/       # Vue 组件 (按功能命名)
│   ├── composables/      # Vue 组合式函数 (useSSE, usePipelineMonitor)
│   ├── layouts/          # 布局组件
│   ├── mock/             # MSW 模拟数据
│   ├── pages/            # 页面级组件 (路由对应)
│   ├── router/           # Vue Router 配置
│   ├── stores/           # Pinia 状态管理 (按领域模块)
│   │   └── __tests__/    # Store 单元测试
│   ├── styles/           # CSS 设计令牌与动画
│   └── utils/            # 工具函数 (chart theme, graph colors)
├── e2e/                  # Playwright E2E 测试
├── plugins/              # Vite 插件
├── public/               # 静态资源
└── dist/                 # 构建产物
```

**组织模式**: 功能分层 (Feature-based)，组件/页面/状态/路由严格分离。

### 2.3 Crawler (`crawler/`)

```
crawler/
├── persistence/          # 数据持久化 (DAO, models, migrations)
├── pipelines/            # 数据处理管道 (clean, incremental, storage)
├── scripts/              # Apify 采集脚本 (按平台: 51job, lagou, liepin, zhaopin)
├── spiders/              # 爬虫逻辑
├── output/               # 采集输出数据
└── tests/                # 爬虫单元测试
```

### 2.4 Contracts (`starmap-contracts/`)

```
starmap-contracts/
├── graph_cypher/         # Neo4j Cypher 查询模板
├── models/               # 共享数据模型定义
├── openapi.yaml          # 完整 OpenAPI 3.0 规范
└── validate.py           # 契约验证脚本
```

### 2.5 Evaluation (`evaluation/`)

```
evaluation/
├── baseline_report/      # 基线评估报告
├── demo_evidence/        # 演示证据 (JSON)
├── llm_real_report/      # 真实LLM评估报告
├── llm_sim_report/       # 模拟LLM评估报告
├── real_eval_report/     # 真实环境评估报告
├── *.py                  # 评估运行脚本
└── *.jsonl               # 黄金数据集
```

### 2.6 Tests (`tests/`)

```
tests/
├── contract/             # 契约测试 (OpenAPI diff)
└── e2e/                  # 端到端测试
    ├── browser-qa/         # 浏览器QA截图与测试
    ├── browser_qa_cycle/     # QA循环截图
    ├── browser_qa_match_extract/  # 匹配提取测试
    ├── browser_qa_screenshots/    # 截图存档
    └── playwright_smoke/        # Playwright 冒烟测试
```

### 2.7 Docs (`docs/`)

```
docs/
├── evidence/screenshots/  # 证据截图
├── evolution/             # 演化设计文档
├── ontology/              # 技能本体数据 (ESCO mapping, taxonomy)
├── progress/              # 项目进度跟踪
└── *.md                   # 各类设计/部署/规划文档
```

### 2.8 Planning (`.planning/`)

```
.planning/
├── codebase/              # 架构文档 (ARCHITECTURE.md, STACK.md)
├── phases/                # 分阶段开发计划
│   ├── 01-bugfix/
│   ├── 01-core-bugfix/
│   ├── 02-hardcode-elimination/
│   ├── 03-frontend-closure/
│   ├── 04-dataflow/
│   ├── 05-style-unify/
│   └── 06-arch-refactor/
├── PROJECT.md
├── REQUIREMENTS.md
├── ROADMAP.md
└── STATE.md
```

---

## 三、文件组织模式总结

### 3.1 当前采用的模式

| 层级 | 模式 | 说明 |
|------|------|------|
| **顶层** | 多仓库合一 (Monorepo) | 后端/前端/爬虫/契约/测试/文档全部在一个仓库 |
| **Backend** | 领域分层 (DDD-lite) | `api` → `services` → `core` → `repositories`，`core/` 内按领域细分 |
| **Frontend** | 功能分层 | 按 `components/pages/stores/router` 分离，组件按功能命名 |
| **Crawler** | 管道模式 | `spiders` → `pipelines` → `persistence` 数据流 |
| **Tests** | 分散式 | 各模块自带 `tests/`，根级 `tests/` 存 E2E 和契约测试 |
| **Docs** | 集中式 | 根级 `docs/` 集中存放，但各模块也有 `AGENTS.md` |

### 3.2 配置文件分布

| 类型 | 位置 | 文件 |
|------|------|------|
| 环境变量 | 根级 | `.env`, `.env.local`, `.env.docker`, `.env.example` |
| Docker | 根级 + 模块 | `docker-compose.{dev,prod}.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| Python | 根级 + backend | `pyproject.toml`, `poetry.lock`, `alembic.ini`, `mypy.ini` |
| Node | frontend | `package.json`, `vite.config.ts`, `tsconfig.json`, `.eslintrc.json` |
| CI/CD | `.github/workflows/` | GitHub Actions |

---

## 四、当前结构问题

### 4.1 🔴 严重问题

| 问题 | 位置 | 影响 |
|------|------|------|
| **根级测试文件污染** | `test_*.py` × 6 个文件在根级 | 根目录混乱，无法区分归属模块 |
| **爬虫双重存在** | `backend/crawler/` + `crawler/` | 代码重复，维护困难 |
| **截图目录分散** | `screenshots/`, `test-screenshots/`, `tests/e2e/browser-qa/screenshots/`, `frontend/test-results/` | 测试产物分散，难以清理 |
| **AGENTS.md 散布** | 几乎每个目录都有 `AGENTS.md` | 元数据噪音，应集中管理 |
| **错误目录** | `C:UsersLiShuaiDesktopAgentsstarmap/` | 路径解析错误产生的垃圾目录 |

### 4.2 🟡 中等问题

| 问题 | 位置 | 影响 |
|------|------|------|
| **缓存/产物未忽略** | `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `__pycache__/` 提交到仓库 | 仓库膨胀 |
| **文档文件根级堆积** | 20+ 个 `.md` 文件在根级 | 难以导航 |
| **评估数据与代码混合** | `evaluation/` 中 `.py` 和 `.jsonl` 混杂 | 数据应分离 |
| **backend/tests 与 tests 职责不清** | `backend/tests/` (单元/集成) vs `tests/` (E2E/契约) | 命名易混淆 |
| **starmap/ 目录空置** | 仅含 `tests/e2e/` | 目录用途不明 |

### 4.3 🟢 轻微问题

| 问题 | 位置 | 建议 |
|------|------|------|
| `nul` 空文件 | 根级 + backend/ + frontend/ | 删除 |
| `coverage.xml` 在根级 | 应由 CI 生成，不提交 | 加入 `.gitignore` |
| `progress.txt` / `prd.json` | 根级 | 移入 `.planning/` |
| 中文文件名 | `项目开发规划...`, `飞书知识库...` | 建议英文命名或移入 `docs/zh/` |

---

## 五、建议的优化结构

基于 **严格分离原则**：代码 / 配置 / 文档 / 测试 / 数据 / 产物 分离

```
starmap/
├── 📁 apps/                          # 【代码】应用模块
│   ├── backend/                      # 原 backend/app/ → 提升为独立模块
│   │   ├── src/                      # 源代码 (原 app/)
│   │   ├── tests/                    # 单元/集成测试 (原 backend/tests/)
│   │   ├── alembic/                  # 数据库迁移
│   │   ├── Dockerfile
│   │   └── pyproject.toml            # 独立依赖管理
│   ├── frontend/                     # 前端应用
│   │   ├── src/
│   │   ├── e2e/                      # E2E测试
│   │   ├── tests/                    # 单元测试 (原 src/stores/__tests__/)
│   │   ├── public/
│   │   ├── Dockerfile
│   │   └── package.json
│   └── crawler/                      # 爬虫 (合并 backend/crawler/ + crawler/)
│       ├── src/
│       ├── tests/
│       └── requirements.txt
│
├── 📁 packages/                      # 【代码】共享包
│   └── contracts/                    # 原 starmap-contracts/
│       ├── openapi/
│       ├── cypher/
│       └── models/
│
├── 📁 config/                        # 【配置】全局配置
│   ├── docker/
│   │   ├── docker-compose.dev.yml
│   │   └── docker-compose.prod.yml
│   ├── env/
│   │   ├── .env.example
│   │   └── .env.docker
│   ├── nginx/
│   │   └── nginx.conf
│   └── github/
│       └── workflows/
│
├── 📁 docs/                          # 【文档】所有文档
│   ├── design/                       # 设计文档 (原 docs/)
│   ├── planning/                     # 开发计划 (原 .planning/)
│   ├── guides/                       # 操作指南 (原 DEPLOY_GUIDE, STARTUP_GUIDE)
│   ├── reports/                      # 报告 (原 BUG_REPORT, QA_REPORT)
│   ├── adr/                          # 架构决策记录
│   └── zh/                           # 中文文档
│
├── 📁 tests/                         # 【测试】跨模块测试
│   ├── e2e/                          # 端到端测试
│   │   ├── browser-qa/
│   │   └── playwright/
│   └── contract/                     # 契约测试
│
├── 📁 scripts/                       # 【脚本】运维与工具
│   ├── seed/                         # 数据种子
│   ├── deploy/                       # 部署脚本
│   └── dev/                          # 开发工具
│
├── 📁 data/                          # 【数据】静态数据与评估
│   ├── ontology/                     # 技能本体 (原 docs/ontology/)
│   ├── evaluation/                   # 评估数据集
│   │   ├── golden/
│   │   └── reports/
│   └── fixtures/                     # 测试夹具 (合并各模块 fixtures)
│
├── 📁 artifacts/                     # 【产物】生成文件 (gitignored)
│   ├── screenshots/                    # 测试截图
│   ├── coverage/                       # 覆盖率报告
│   └── dist/                           # 构建产物
│
├── .gitignore                        # 强化忽略规则
├── README.md
└── Makefile                          # 统一命令入口
```

### 5.1 关键改进点

| 改进 | 原问题 | 收益 |
|------|--------|------|
| `apps/` 统一代码入口 | 模块散落根级 | 清晰的代码边界 |
| `packages/` 共享契约 | starmap-contracts 孤立 | 明确共享依赖 |
| `config/` 集中配置 | .env/docker 散落 | 配置统一管理 |
| `docs/` 合并所有文档 | 20+ MD 文件在根级 | 文档可导航 |
| `data/` 分离数据集 | evaluation/ 混杂代码 | 数据版本可控 |
| `artifacts/` 统一产物 | 截图/缓存分散 | 易于清理和忽略 |
| 各模块独立 `pyproject.toml` | 单一 poetry.lock | 独立发布能力 |
| 删除 `AGENTS.md` 散布 | 每个目录都有 | 元数据集中管理 |

### 5.2 迁移优先级

```
P0 (立即): 删除垃圾目录、加入 .gitignore、清理根级 test_*.py
P1 (本周): 合并 crawler/ 与 backend/crawler/、集中截图目录
P2 (本月): 文档归集到 docs/、建立 artifacts/ 目录
P3 (季度): 重构为 apps/packages/config 结构、模块独立发布
```

---

## 六、附录：当前完整目录树 (精简版)

```
starmap/
├── .codegraph/
├── .github/workflows/
├── .idea/
├── .omc/plans/  .omo/plans/
├── .planning/
│   ├── codebase/ (ARCHITECTURE.md, STACK.md)
│   └── phases/01-*/
├── backend/
│   ├── app/
│   │   ├── api/v1/ (admin, dashboard, extract, graph, match, ...)
│   │   ├── core/ (dashboard, evolution, extraction, learning, matching, pipeline)
│   │   ├── models/ (evolution, extraction, learning, pipeline)
│   │   ├── pipeline/ (contracts, engine, steps)
│   │   ├── repositories/
│   │   ├── services/ (dedup, graph, judge, match, neo4j, resume)
│   │   ├── tasks/ (celery)
│   │   └── utils/
│   ├── alembic/versions/
│   ├── crawler/          ← ⚠️ 与根级 crawler/ 重复
│   ├── docs/
│   ├── openapi/
│   ├── scripts/
│   └── tests/ (fixtures, integration, unit)
├── crawler/
│   ├── persistence/ (dao, migrations)
│   ├── pipelines/ (clean, incremental, storage)
│   ├── scripts/ (apify_*)
│   ├── spiders/
│   └── tests/
├── docs/
│   ├── evidence/screenshots/
│   ├── evolution/
│   ├── ontology/ (esco, taxonomy)
│   └── progress/
├── evaluation/
│   ├── *_report/
│   └── *.py, *.jsonl
├── frontend/
│   ├── src/ (api, components, composables, layouts, mock, pages, router, stores, styles, utils)
│   ├── e2e/
│   ├── plugins/
│   ├── public/
│   └── dist/
├── screenshots/            ← ⚠️ 应移入 artifacts/
├── scripts/
├── starmap/
│   └── tests/e2e/          ← ⚠️ 用途不明
├── starmap-contracts/
│   ├── graph_cypher/
│   ├── models/
│   └── openapi.yaml
├── test-screenshots/       ← ⚠️ 应合并
└── tests/
    ├── contract/
    └── e2e/ (browser-qa, playwright_smoke, ...)
```

---

*本文档由自动化工具生成，反映项目当前状态。建议每季度更新一次。*
