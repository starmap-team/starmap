# StarMap 项目入职手册

> **版本**: v1.0 | **更新日期**: 2026-07-08
> **适用对象**: 新加入 StarMap 项目的开发者

---

## 目录

1. [项目概览](#1-项目概览)
2. [开发环境与 IDE 配置](#2-开发环境与-ide-配置)
3. [服务依赖全景](#3-服务依赖全景)
4. [启动服务](#4-启动服务)
5. [前后端一致性验证](#5-前后端一致性验证)
6. [项目架构与数据流](#6-项目架构与数据流)
7. [代码风格与约定](#7-代码风格与约定)
8. [测试体系](#8-测试体系)
9. [CI/CD 流水线](#9-cicd-流水线)
10. [常见任务速查](#10-常见任务速查)
11. [故障排查](#11-故障排查)

---

## 1. 项目概览

**StarMap（星图）** 是一个智能职业图谱系统，通过 LLM 从招聘 JD 中抽取技能，构建 Neo4j 知识图谱，提供岗位匹配诊断、技能演化追踪和学习路径推荐。

**核心数据流**：

```
JD文本 → extract/jd (LLM抽取) → 归一化 → 反幻觉 → 写入Neo4j
简历   → match/diagnose → 技能对比 → 差距分析 → 学习路径
快照   → evolution/diff → 差异引擎 → 新兴技能 → 信任度聚合
```

**技术栈总览**：

| 层 | 技术 | 版本 |
|----|------|------|
| 后端语言 | Python | 3.11–3.12 |
| 后端框架 | FastAPI | 0.110+ |
| 关系数据库 | PostgreSQL | 16 |
| 图数据库 | Neo4j | 5 Community |
| 向量数据库 | ChromaDB | 0.5+ |
| 缓存/队列 | Redis | 7 Alpine |
| 任务队列 | Celery | 5.3+ |
| ORM | SQLAlchemy async | 2.0+ |
| 前端语言 | TypeScript | 5.4+ |
| 前端框架 | Vue 3 | 3.4+ |
| UI 库 | Element Plus | 2.6+ |
| 图可视化 | @antv/G6 | 5.0+ |
| 图表 | ECharts | 5.5+ |
| 构建工具 | Vite | 5.2+ |
| LLM | 星火 API / DeepSeek / Qwen (Ollama) | — |
| API 契约 | OpenAPI 3.0.3 | — |

---

## 2. 开发环境与 IDE 配置

### 2.1 推荐 IDE

**VS Code**（项目首选，以下扩展推荐安装）：

| 扩展 | 用途 |
|------|------|
| Python (ms-python.python) | Python 语言支持、调试 |
| Pylance | 类型检查、自动补全 |
| Vue - Official (vue.volar) | Vue 3 SFC 支持 |
| TypeScript Vue Plugin | Vue TS 服务 |
| ESLint | 实时 lint 提示 |
| Ruff | Python 格式化 + lint（替代 black/flake8） |
| Docker | Docker Compose 管理 |
| REST Client | API 调试（替代 Postman） |
| GitLens | Git 历史查看 |
| Thunder Client | API 测试 |

**PyCharm Professional** 也可使用（支持 Python + Vue + Database 工具），但团队以 VS Code 为主。

### 2.2 前置软件安装

| 软件 | 版本 | 用途 | 安装方式 |
|------|------|------|----------|
| Python | 3.11–3.12 | 后端运行时 | [python.org](https://python.org) 或 `winget install Python.Python.3.12` |
| Node.js | 20 LTS | 前端运行时 | [nodejs.org](https://nodejs.org) 或 `winget install OpenJS.NodeJS.LTS` |
| Poetry | 2.4+ | Python 包管理 | `pip install poetry` |
| Docker Desktop | 最新 | 容器化服务 | [docker.com](https://docker.com) |
| Git | 2.40+ | 版本控制 | `winget install Git.Git` |

### 2.3 VS Code 工作区配置

在项目根目录创建 `.vscode/settings.json`：

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "ruff.lineLength": 120,
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "charliermarsh.ruff",
  "[vue]": { "editor.defaultFormatter": "esbenp.prettier-vscode" },
  "[typescript]": { "editor.defaultFormatter": "esbenp.prettier-vscode" },
  "typescript.tsdk": "frontend/node_modules/typescript/lib",
  "files.associations": { "*.py": "python", "*.vue": "vue" }
}
```

推荐调试配置 `.vscode/launch.json`：

```json
[
  {
    "name": "Backend: FastAPI",
    "type": "debugpy",
    "request": "launch",
    "module": "uvicorn",
    "args": ["app.main:app", "--reload", "--port", "8000"],
    "cwd": "${workspaceFolder}/backend",
    "envFile": "${workspaceFolder}/.env"
  },
  {
    "name": "Frontend: Vite",
    "type": "chrome",
    "request": "launch",
    "url": "http://localhost:5173",
    "webRoot": "${workspaceFolder}/frontend/src"
  }
]
```

---

## 3. 服务依赖全景

### 3.1 服务架构图

```
                    ┌─────────────┐
                    │   Browser   │
                    │  :5173/80   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Nginx /   │
                    │  Vite Dev   │
                    │   Server    │
                    └──────┬──────┘
                           │ /api/*
                    ┌──────▼──────┐
                    │   FastAPI   │
                    │  :8000      │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Neo4j    │ │PostgreSQL│ │  Redis   │
        │ :7687    │ │ :5433    │ │ :6379    │
        │ :7474 UI │ │          │ │          │
        └──────────┘ └──────────┘ └────┬─────┘
                                       │
                                ┌──────▼──────┐
                                │Celery Worker│
                                │ (4 queues)  │
                                └──────┬──────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
              ┌──────────┐      ┌──────────┐      ┌──────────┐
              │ ChromaDB │      │  Ollama  │      │ 星火 API │
              │ :8001    │      │ :11434   │      │ (云端)   │
              └──────────┘      └──────────┘      └──────────┘
```

### 3.2 服务清单

| 服务 | 端口 | 镜像 | 用途 | 健康检查 |
|------|------|------|------|----------|
| **backend** | 8000 | python:3.11-slim | FastAPI 应用 | `GET /health` |
| **celery-worker** | — | python:3.11-slim | 异步任务 (抽取/匹配/图/默认队列) | — |
| **frontend** | 5173 (dev) / 80 (prod) | node:20-alpine / nginx:alpine | Vue 3 SPA | `GET /` |
| **neo4j** | 7474 (HTTP) / 7687 (Bolt) | neo4j:5-community | 知识图谱存储 | `cypher: RETURN 1` |
| **postgres** | 5433→5432 | postgres:16 | 关系数据 (岗位/匹配/抽取/学习) | `pg_isready` |
| **redis** | 6379 | redis:7-alpine | Celery broker + 缓存 | `redis-cli ping` |
| **chroma** | 8001→8000 | chromadb/chroma | 向量检索 (技能归一化) | — |
| **ollama** | 11434 | ollama/ollama | 本地 LLM (Qwen2.5-7B) | — |

### 3.3 环境变量

复制 `.env.example` 为 `.env`，**必须修改**以下变量：

```bash
# 必须修改（生产环境）
NEO4J_PASSWORD=starmap123456     # 改为强密码
POSTGRES_PASSWORD=starmap123456  # 改为强密码
SECRET_KEY=<用 python -c "import secrets; print(secrets.token_urlsafe(32))" 生成>

# 必须配置（LLM 功能依赖）
XUNFEI_API_KEY=你的星火API密钥
XUNFEI_API_SECRET=你的星火API密钥
XUNFEI_APP_ID=你的星火AppID

# 可选（有默认值）
APP_ENV=development
APP_DEBUG=true
VITE_API_BASE_URL=http://localhost:8000
QWEN_MODEL_PATH=http://ollama:11434
```

---

## 4. 启动服务

### 4.1 方式一：Docker Compose 全栈启动（推荐）

```bash
# 1. 准备环境变量
cp .env.example .env
# 编辑 .env，填入必填项

# 2. 启动所有服务（开发模式，带热重载）
docker compose -f docker-compose.dev.yml up -d

# 3. 等待服务就绪（约 30-60 秒）
# 检查后端健康
curl http://localhost:8000/health
# 预期: {"status":"ok"}

# 检查前端
curl http://localhost:5173
# 预期: HTML 页面

# 4. 查看日志
docker compose -f docker-compose.dev.yml logs -f backend    # 后端日志
docker compose -f docker-compose.dev.yml logs -f frontend   # 前端日志
docker compose -f docker-compose.dev.yml logs -f celery-worker  # Celery 日志

# 5. 停止所有服务
docker compose -f docker-compose.dev.yml down

# 6. 停止并清除数据卷（重置数据库）
docker compose -f docker-compose.dev.yml down -v
```

**首次启动注意**：`ollama-pull` 容器会自动拉取 Qwen2.5-7B 模型（约 4.7GB），需等待下载完成。

### 4.2 方式二：本地开发（前后端分别启动）

**前提**：Docker 仅启动基础设施服务。

```bash
# 1. 启动基础设施（Neo4j + PG + Redis + Chroma + Ollama）
docker compose -f docker-compose.dev.yml up -d neo4j postgres redis chroma ollama

# 2. 后端
cd backend
poetry install                    # 安装依赖
poetry run uvicorn app.main:app --reload --port 8000

# 3. 前端（新终端）
cd frontend
npm install                       # 安装依赖
npm run dev                       # Vite 开发服务器，自动代理 /api → localhost:8000

# 4. Celery Worker（新终端，可选）
cd backend
poetry run celery -A app.tasks.celery_app worker --loglevel=info -Q default,extraction,matching,graph
```

### 4.3 方式三：生产模式：生产构建

```bash
docker compose -f docker-compose.prod.yml up -d
# 前端: http://localhost (Nginx 80 端口)
# 后端: http://localhost:8000/api/v1
```

### 4.4 填充演示数据

```bash
# 在后端容器内或本地 backend/ 目录
cd backend

# 基础演示数据
poetry run python scripts/seed_chroma.py
poetry run python scripts/seed_pipeline_runs_demo.py
poetry run python scripts/seed_datasources_demo.py
poetry run python scripts/seed_changelog.py

# 图谱数据
poetry run python scripts/expand_graph.py
```

---

## 5. 前后端一致性验证

这是 StarMap 质量保障的核心，**4 层防护机制**：

### 5.1 层 1：OpenAPI 代码生成（类型级一致性）

```bash
cd frontend
npm run gen:api
# 执行: openapi-typescript ../starmap-contracts/openapi.yaml -o src/api/schema.ts
```

- `schema.ts` 是自动生成的，**禁止手动修改**
- 前端所有 API 类型从 OpenAPI 契约推导
- API 字段统一使用 **snake_case**（项目约定，不做 camelCase 转换）

### 5.2 层 2：契约校验脚本

```bash
python starmap-contracts/validate.py
```

校验 3 项：
1. `openapi.yaml` 是合法 OpenAPI 3.0.3
2. `models/__init__.py` 是合法 Python
3. OpenAPI schema 与 Python model 类名一致性

### 5.3 层 3：CI 契约一致性比对

CI 后端 job 中自动运行，将 FastAPI `app.openapi()` 导出的 paths 与 `openapi.yaml` 比对：
- 契约有但 app 没有 → **FAIL**（阻断）
- app 有但契约没有 → **WARN**（允许新增）

### 5.4 层 4：E2E 冒烟测试

```bash
# 全栈启动后运行
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

| 场景 | 验证内容 |
|------|----------|
| E2E-0 | `/health` 返回 200 + status=ok |
| E2E-1 | 全景图谱有节点、岗位列表非空 |
| E2E-2 | 岗位详情可查、演化趋势接口可达 |
| E2E-3 | `/match/diagnose` 接口可达 |
| E2E-4 | 全服务健康 + 质量看板有种子数据 |

### 5.5 手动一致性验证完整流程

当你修改了 API 后，按此顺序验证：

```bash
# 1. 修改 starmap-contracts/openapi.yaml（契约优先！）

# 2. 运行契约校验
python starmap-contracts/validate.py

# 3. 重新生成前端类型
cd frontend && npm run gen:api

# 4. 前端类型检查
npm run typecheck    # vue-tsc --noEmit

# 5. 后端 lint + 类型检查
cd backend && poetry run ruff check . && poetry run mypy app

# 6. 后端测试
poetry run pytest

# 7. E2E 冒烟
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

### 5.6 前端手动验证清单

启动服务后，在浏览器中逐页验证：

| 页面 | URL | 验证要点 |
|------|-----|----------|
| 全景图 | `http://localhost:5173/` | G6 图谱渲染、节点可点击 |
| 岗位列表 | `/positions` | 列表非空、搜索可用 |
| 岗位详情 | `/position/前端工程师` | 技能标签、匹配度 |
| JD 抽取 | `/extract` | 粘贴 JD → 抽取结果含技能+置信度 |
| 匹配诊断 | `/match` | 上传简历 → 差距分析 |
| 演化仪表盘 | `/evolution` | 趋势图、新兴技能、演化路径 |
| 质量仪表盘 | `/quality` | 质量评分、趋势 |
| 管道监控 | `/pipeline` | 运行状态、阶段进度 |
| 数据大屏 | `/dashboard` | SSE 实时数据流 |
| 学习中心 | `/learning` | 学习路径推荐 |

---

## 6. 项目架构与数据流

### 6.1 目录结构

```
starmap/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # 14 个路由模块
│   │   ├── core/             # 业务核心
│   │   │   ├── dashboard/    # 仪表盘 + SSE 广播
│   │   │   ├── evolution/    # 演化引擎 (差异/涌现/信任)
│   │   │   ├── extraction/   # JD 抽取 + 提示模板
│   │   │   ├── graph_engine/ # 图引擎抽象
│   │   │   ├── hallucination/# 反幻觉防护
│   │   │   ├── learning/     # 路径引擎
│   │   │   ├── matching/     # 匹配 + 缓存
│   │   │   ├── pipeline/     # 管道编排 + cron
│   │   │   └── trust/        # 信任评分
│   │   ├── db/               # 数据库会话
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── repositories/     # 仓储层
│   │   ├── services/         # 服务层
│   │   ├── tasks/            # Celery 异步任务
│   │   ├── config.py         # Pydantic BaseSettings
│   │   ├── dependencies.py   # FastAPI 依赖 (认证/DB)
│   │   └── main.py           # 应用入口
│   ├── scripts/              # 种子/运维脚本
│   └── tests/                # pytest 测试
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # HTTP 请求层 (axios + OpenAPI 生成类型)
│   │   ├── components/       # 共享 UI 组件
│   │   ├── composables/      # Vue 可组合函数
│   │   ├── pages/            # 14 个页面 (懒加载)
│   │   ├── stores/           # Pinia 状态管理 (9 个 store)
│   │   ├── types/            # TypeScript 类型
│   │   └── router/           # Vue Router
│   └── nginx.conf            # 生产 Nginx 配置
├── starmap-contracts/        # API 契约 (跨团队真相源)
│   ├── openapi.yaml          # OpenAPI 3.0.3
│   ├── graph_cypher/         # Neo4j 查询契约
│   ├── models/               # 共享 Python 模型
│   └── validate.py           # 契约校验脚本
├── crawler/                  # Scrapy 爬虫 (ESCO/W3C)
├── evaluation/               # 评估套件
├── scripts/                  # 项目级脚本
├── tests/                    # E2E + 契约测试
└── docs/                     # 项目文档
```

### 6.2 API 路由映射

所有 API 前缀 `/api/v1`，需 `get_current_user` 认证：

| 路由模块 | 前缀 | 核心端点 |
|----------|------|----------|
| extract | `/extract` | `POST /jd`, `POST /resume` |
| position | `/positions` | `GET /`, `GET /{id}`, `POST /discover` |
| graph | `/graph` | `GET /overview`, `GET /position/{id}/skills` |
| match | `/match` | `POST /position`, `GET /result/{id}`, `POST /diagnose` |
| evolution | `/evolution` | `GET /trends`, `POST /analyze`, `GET /changelog/{pos}`, `GET /paths/{pos}` |
| quality | `/quality` | `POST /evaluate`, `GET /report`, `GET /dashboard` |
| pipeline | `/pipeline` | `GET /status`, `GET /runs`, `POST /trigger` |
| dashboard | `/dashboard` | `GET /overview`, `GET /realtime` (SSE) |
| learning | `/learning` | `GET /paths`, `GET /progress` |
| admin | `/admin` | `GET /stats`, `GET /review-queue`, `POST /audit/{id}/approve` |
| loop | `/loop` | `GET /status`, `POST /feedback` |
| datasource | `/datasources` | `GET /`, `PUT /{id}` |
| judge | `/judge` | `POST /evaluate`, `POST /pairwise` |
| resume | `/resume` | `POST /upload` |

### 6.3 JD 抽取完整数据流

```
[前端 ExtractJD.vue]
  │ POST /extract/jd { jd_content: "..." }
  ▼
[后端 extract.py → extract_jd()]
  │ 1. Pydantic 验证 ExtractRequest
  │ 2. mask_pii() — 脱敏 (手机/身份证/邮箱)
  │ 3. get_prompt("jd_extraction") — 填充提示模板
  │ 4. llm_client.extract_from_jd() — 调用星火/DeepSeek
  │ 5. parse_llm_json_response() — 解析 LLM JSON 输出
  │ 6. JDExtractionResult(**parsed) — Pydantic 验证
  │ 7. batch_normalize_skills() — 别名归一化 + 向量相似度 (≥0.85)
  │ 8. llm_client.validate_extraction() — 反幻觉校验
  │ 9. _write_extraction_to_graph() — MERGE Neo4j 节点/关系
  ▼
[响应] { position_name, required_skills, confidence, hallucination_score, ... }
  ▼
[前端 jd.ts store] → ExtractJD.vue 渲染技能标签 + 置信度
```

---

## 7. 代码风格与约定

### 7.1 命名约定

| 范围 | 约定 | 示例 |
|------|------|------|
| Python 文件/变量/函数 | snake_case | `jd_extract.py`, `match_score` |
| Python 类 | PascalCase | `ExtractionResult`, `EmergenceFinder` |
| Vue 组件/文件 | PascalCase | `MatchDiagnosis.vue`, `CareerPathGraph` |
| TS 变量/函数 | camelCase | `fetchPositions`, `matchScore` |
| **API 字段** | **snake_case** | `match_score`, `skill_name` (前后端一致，**不做 camelCase 转换**) |
| CSS 类 | kebab-case | `skill-tag`, `match-result` |

### 7.2 Python 风格

- 行宽 120，Ruff 格式化
- `from __future__ import annotations` + mypy
- 异步优先：`async def` + await`，SQLAlchemy async session
- 错误处理：显式 try/except，loguru 记录上下文

### 7.3 前端风格

- Vue 3 Composition API + `<script setup lang="ts">`
- Pinia store 管理状态，composable 封装逻辑
- ECharts 按需导入，G6 v5 图可视化
- MSW mock 开发环境 API

### 7.4 Git 约定

- 分支：`fix/*`, `feat/*`, `chore/*`, `docs/*`
- Commit：`type(scope): description`
- PR：squash merge
- 契约优先：API 变更先改 `openapi.yaml`

---

## 8. 测试体系

### 8.1 测试命令速查

```bash
# 后端
cd backend && poetry run pytest                          # 全部 (覆盖率 ≥ 60%)
cd backend && poetry run pytest tests/unit/              # 仅单元
cd backend && poetry run pytest tests/integration/       # 仅集成
cd backend && poetry run pytest -k "hallucination"       # 按关键词

# 前端
cd frontend && npm run test                              # vitest
cd frontend && npm run test:watch                        # vitest watch

# E2E
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all

# 评估
cd evaluation && python run_baseline.py                  # 基线 F1 (目标 ≥ 0.758)

# 契约
python starmap-contracts/validate.py

# Lint + 类型
cd backend && poetry run ruff check . && poetry run mypy app
cd frontend && npm run lint && npm run typecheck
```

### 8.2 测试覆盖范围

| 层级 | 位置 | 框架 | 文件数 | 覆盖 |
|------|------|------|--------|------|
| 后端单元 | `backend/tests/unit/` | pytest | 55+ | 核心/服务/管道 |
| 后端集成 | `backend/tests/integration/` | pytest | 1 | API 端点 |
| 前端单元 | `frontend/src/stores/__tests__/` | vitest | 5 | Pinia store |
| E2E 冒烟 | `tests/e2e/` | pytest + httpx | 1 | 全栈 5 场景 |
| 契约测试 | `starmap-contracts/validate.py` | Python | 1 | OpenAPI 合法性 |
| 爬虫测试 | `crawler/tests/` | pytest | 10 | 去重/合规/ESCO |

### 8.3 评估体系

| 层级 | 脚本 | 方法 | F1 基线 |
|------|------|------|---------|
| 基线 | `run_baseline.py` | 关键词子串匹配 | 0.758 |
| LLM 模拟 | `simulate_llm_eval.py` | Golden + 5% 噪声 | 0.976 |
| 真实 LLM | `run_real_eval.py` | 星火 API | 待测 |

质量门禁：F1 ≥ 0.90 绿色 / < 0.80 红色

---

## 9. CI/CD 流水线

**触发条件**：PR 到 main + push 到 main + 每日 UTC 02:00 + 手动

```
contracts → backend → frontend → crawler → docker-smoke (手动/定时)
```

| Job | 步骤 | 门禁 |
|-----|------|------|
| **contracts** | `validate.py` | 契约校验失败 → 阻断 |
| **backend** | ruff → mypy → pytest (cov≥60%) → 契约一致性 | 覆盖率 + 契约 |
| **frontend** | npm install → gen:api → eslint → vue-tsc → vite build | 类型 + 构建 |
| **crawler** | compileall → pytest | 编译通过 |
| **docker-smoke** | compose up → /health → :5173 | 仅手动/定时 |

---

## 10. 常见任务速查

| 我想... | 命令/位置 |
|---------|-----------|
| 启动全栈 | `docker compose -f docker-compose.dev.yml up -d` |
| 查看后端日志 | `docker compose -f docker-compose.dev.yml logs -f backend` |
| 添加 API 端点 | 1. 改 `starmap-contracts/openapi.yaml` → 2. `cd frontend && npm run gen:api` → 3. 实现后端路由 → 4. 实现前端调用 |
| 添加前端页面 | `frontend/src/pages/` 新建 Vue 文件 → `frontend/src/router/index.ts` 注册路由 |
| 添加数据库表 | `backend/app/models/` 新建模型 → `alembic revision --autogenerate` → `alembic upgrade head` |
| 运行数据库迁移 | `cd backend && poetry run alembic upgrade head` |
| 填充演示数据 | `cd backend && poetry run python scripts/seed_chroma.py` |
| 检查 Neo4j 数据 | 浏览器访问 `http://localhost:7474` (neo4j/starmap123456) |
| 检查 PostgreSQL | `docker exec -it starmap-dev-postgres-1 psql -U starmap -d starmap` |
| 检查 Redis | `docker exec -it starmap-dev-redis-1 redis-cli` |
| 重新生成前端 API 类型 | `cd frontend && npm run gen:api` |
| 验证前后端一致性 | `python starmap-contracts/validate.py && cd frontend && npm run typecheck` |
| 运行 E2E 测试 | `python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all` |
| 运行评估 | `cd evaluation && python run_baseline.py` |
| 构建生产镜像 | `docker compose -f docker-compose.prod.yml build` |

---

## 11. 故障排查

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 后端 500 错误 | 数据库未就绪 | 等待 neo4j/postgres 健康检查通过 |
| 前端 API 404 | Vite 代理未配置 | 确认 `VITE_API_BASE_URL=http://localhost:8000` |
| Neo4j 连接失败 | 密码不匹配 | 检查 `.env` 中 `NEO4J_PASSWORD` 与 docker-compose 一致 |
| Celery 任务不执行 | Redis 未启动 | `docker compose -f docker-compose.dev.yml restart redis` |
| LLM 抽取失败 | 星火 API Key 无效 | 检查 `XUNFEI_API_KEY/SECRET/APP_ID` |
| Ollama 模型未下载 | 首次启动需拉取 | `docker exec -it starmap-dev-ollama-1 ollama pull qwen2.5:7b` |
| 前端类型错误 | schema.ts 过期 | `cd frontend && npm run gen:api` |
| 端口冲突 | 其他服务占用 | 修改 docker-compose 端口映射 |
| Docker 构建慢 | 网络问题 | 配置 Docker 镜像加速器 |

### 健康检查命令

```bash
# 一键检查所有服务
curl -s http://localhost:8000/health          # 后端
curl -s http://localhost:5173 | head -5       # 前端
curl -s http://localhost:7474                  # Neo4j Browser
docker exec starmap-dev-postgres-1 pg_isready  # PostgreSQL
docker exec starmap-dev-redis-1 redis-cli ping # Redis
```

### 重置环境

```bash
# 完全重置（删除所有数据卷）
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d

# 重新填充数据
cd backend && poetry run python scripts/seed_chroma.py
```

---

> **下一步**：完成环境搭建后，建议按以下顺序熟悉项目：
> 1. 浏览 `http://localhost:5173` 体验各页面
> 2. 阅读 `starmap-contracts/openapi.yaml` 了解 API 全貌
> 3. 跟踪一次 JD 抽取流程（前端 → API → 服务 → Neo4j）
> 4. 运行 `poetry run pytest` 确认后端测试通过
> 5. 运行 E2E 冒烟测试确认全栈一致性
