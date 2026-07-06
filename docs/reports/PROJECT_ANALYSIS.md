# StarMap 项目完整模块解析报告

> **生成日期**: 2026-07-03
> **项目**: StarMap — IT 岗位人才能力图谱系统
> **技术栈**: Python (FastAPI) + Vue 3 + Neo4j + PostgreSQL + Redis + Celery

---

## 📋 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [后端模块详解 (Backend)](#3-后端模块详解-backend)
4. [前端模块详解 (Frontend)](#4-前端模块详解-frontend)
5. [爬虫模块详解 (Crawler)](#5-爬虫模块详解-crawler)
6. [契约模块详解 (Contracts)](#6-契约模块详解-contracts)
7. [基础设施 (Docker/CI)](#7-基础设施-dockerci)
8. [测试体系](#8-测试体系)
9. [数据流与业务闭环](#9-数据流与业务闭环)
10. [关键设计模式](#10-关键设计模式)
11. [模块依赖关系图](#11-模块依赖关系图)
12. [开发建议](#12-开发建议)

---

## 1. 项目概述

**StarMap** 是一个面向 IT 岗位的人才能力图谱系统，核心能力包括：

- **岗位-技能图谱**: 构建 IT 岗位与所需技能的知识图谱（Neo4j）
- **信息抽取**: 从 JD（职位描述）和简历中自动提取技能信息（LLM + NLP）
- **匹配诊断**: 将个人技能与目标岗位匹配，诊断差距
- **演化分析**: 追踪技能趋势、岗位演化路径、新兴技能检测
- **学习路径**: 基于差距生成个性化学习路径
- **质量监控**: 三层幻觉防御 + 信任评分 + 质量仪表盘
- **数据流水线**: 爬虫 → 清洗 → 去重 → 抽取 → 图谱构建 → 演化分析

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Vue 3)                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  图谱可视化 │ │ 匹配诊断  │ │ 学习路径  │ │ 数据大屏  │ │ 管理后台  │        │
│  │ Graph3D  │ │ Match    │ │ Learning │ │ Dashboard│ │ Admin    │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│  技术栈: Vue 3 + Vite + Pinia + Element Plus + ECharts + 3d-force-graph    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ REST API / SSE
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API 网关层 (FastAPI)                            │
│  14 个路由模块: graph, position, match, evolution, quality, learning,        │
│  admin, dashboard, datasource, extract, judge, loop, resume, pipeline       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌───────────────────┐  ┌──────────────┐  ┌──────────────────┐
│   业务服务层        │  │   核心引擎层   │  │   数据访问层      │
│  ┌─────────────┐  │  │ ┌──────────┐ │  │ ┌──────────────┐ │
│  │ match_service│  │  │ │ 演化分析   │ │  │ │ PositionRepo  │ │
│  │ graph_service│  │  │ │ 学习路径   │ │  │ │ (Neo4j)      │ │
│  │ resume_service│ │  │ │ 幻觉防御   │ │  │ ├──────────────┤ │
│  │ judge_service│  │  │ │ 信任评分   │ │  │ │ SQLAlchemy   │ │
│  │ quality_monitor│ │  │ │ 新兴检测   │ │  │ │ (PostgreSQL) │ │
│  └─────────────┘  │  │ └──────────┘ │  │ └──────────────┘ │
└───────────────────┘  └──────────────┘  └──────────────────┘
                    │               │               │
                    ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据存储层                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Neo4j      │  │  PostgreSQL  │  │    Redis     │  │   ChromaDB   │  │
│  │  (图数据库)   │  │  (关系数据)  │  │  (缓存/队列)  │  │  (向量检索)   │  │
│  │  岗位-技能图谱 │  │  岗位/技能/   │  │  SSE广播/    │  │  技能语义    │  │
│  │  演化路径    │  │  抽取记录/    │  │  去重/配置   │  │  相似度计算   │  │
│  │  前置条件    │  │  学习进度/    │  │  流水线状态   │  │              │  │
│  │              │  │  流水线运行    │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              异步任务层 (Celery)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 批量JD抽取   │  │ 图谱构建      │  │ 演化趋势分析  │  │ 流水线阶段执行 │  │
│  │ 简历解析     │  │ 数据去重      │  │ 定时任务     │  │ 孤儿任务清理   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据爬虫层 (Crawler)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │ 拉勾网爬虫   │  │ 51job爬虫    │  │ BOSS直聘爬虫  │                       │
│  │ (HTTP/Stealth)│  │ (HTTP/Stealth)│  │ (Stealth)    │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
│  技术栈: Scrapy + Playwright + SimHash + SQLAlchemy                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 后端模块详解 (Backend)

### 3.1 应用入口与配置

| 文件 | 职责 | 关键导出 |
|------|------|----------|
| `app/main.py` | FastAPI 应用工厂 + 生命周期管理 | `app`, `lifespan()`, `health()` |
| `app/config.py` | 集中式配置管理 (Pydantic Settings) | `Settings`, `get_settings()`, `settings` |
| `app/dependencies.py` | FastAPI 依赖注入 | `get_db_session()`, `get_neo4j_driver()`, `get_redis_client()` |
| `app/__init__.py` | 包标记 + 版本 | `__version__ = "0.1.0"` |

**配置域**:
- 应用环境 (dev/staging/prod)
- 4 个数据存储 (Neo4j, PostgreSQL, Redis, ChromaDB)
- 4 个 LLM 提供商 (Xunfei, DeepSeek, Qwen, MiMo)
- 抽取/幻觉/路径/信任/新兴检测/匹配/质量等阈值参数
- 流水线控制参数 (超时、并发、重试)

### 3.2 API 路由层 (14 个模块)

| 模块 | 端点数 | 核心功能 |
|------|--------|----------|
| `graph.py` | 3 | 图谱查询 (岗位技能子图、领域概览、知识域岗位) |
| `position.py` | 3 | 岗位 CRUD + 新兴岗位发现 (Z-score) |
| `match.py` | 5 | 技能匹配、差距诊断、批量匹配、历史记录 |
| `evolution.py` | 13 | 趋势分析、演化路径、新兴技能、职业路径、行业报告、可移植性分析 |
| `quality.py` | 7 | 质量评估、仪表盘、趋势、告警、综合报告 |
| `learning.py` | 6 | 学习计划 CRUD、进度跟踪、推荐 |
| `admin.py` | 20 | 统计、审核队列、Prompt A/B 测试、图谱节点 CRUD |
| `dashboard.py` | 5 | KPI 概览、趋势、分布、SSE 实时流 |
| `datasource.py` | 5 | 数据源 CRUD、统计、同步触发 |
| `extract.py` | 2 | JD/简历技能抽取 + 图谱写入 |
| `judge.py` | 3 | LLM-as-Judge 评估 (单样本/成对/批量) |
| `loop.py` | 3 | 5 步闭环流水线 (JD→抽取→图谱→匹配→学习) |
| `resume.py` | 1 | 简历上传兼容端点 |
| `pipeline/routes.py` | 20 | 流水线生命周期、调度、配置、SSE 分析 |

### 3.3 核心引擎层 (Core)

#### 演化分析引擎 (`app/core/evolution/`)

| 组件 | 职责 | 关键算法 |
|------|------|----------|
| `diff_engine.py` | 岗位快照差异计算 | 集合差分: 新增/移除/晋升/降级/保留 |
| `emergence_finder.py` | 新兴技能检测 | Z-score 统计异常检测 + 跨域分析 + 可移植性评分 |
| `hallucination_guard.py` | 三层幻觉防御 | 本体白名单 → 多源验证 → 置信度+LLM 判断 |
| `trust_integration.py` | 信任评分 | 加权复合 (源0.35/时间0.25/交叉0.25/人工0.15) + 指数衰减 |
| `path_recommender.py` | 演化路径发现 | Jaccard 相似度 > 0.6 |
| `snapshot_manager.py` | 快照 CRUD | PostgreSQL 存储 + ORM→dataclass 转换 |
| `orchestrator.py` | 8 步流水线协调器 | 快照→差异→信任→防御→新兴→路径→日志→图谱 |

#### 学习路径引擎 (`app/core/learning/`)

| 组件 | 职责 | 关键算法 |
|------|------|----------|
| `path_engine.py` | 个性化学习路径生成 | 3 层前置条件加载 → 拓扑排序 (Kahn) → 阶段分组 |
| `progress_tracker.py` | 学习进度跟踪 | 自动状态转换 + 重要性加权进度 |

#### 仪表盘服务 (`app/core/dashboard/`)

| 组件 | 职责 | 关键特性 |
|------|------|----------|
| `dashboard_service.py` | KPI 聚合 | 优雅降级 + Redis 60s TTL 缓存 |
| `sse_broadcaster.py` | SSE 实时广播 | Redis pub/sub + LPUSH/LTRIM 轮询降级 |

#### 抽取引擎 (`app/core/extraction/`)

| 组件 | 职责 | 关键特性 |
|------|------|----------|
| `jd_extract.py` | JD 技能抽取 | LLM 多提供商回退 + 技能规范化 |
| `normalize.py` | 技能名称规范化 | 别名查找 → 向量相似度 → 源数量验证 |
| `llm_client.py` | LLM 客户端 | MiMo→DeepSeek→Xunfei→Qwen 四级回退 + tenacity 重试 |
| `prompt.py` | 版本化 Prompt | A/B 测试 + 流量分配 |
| `graph_writer.py` | 图谱写入 | 批量 MERGE + 冲突更新 |

### 3.4 服务层 (Services)

| 服务 | 职责 | 存储 |
|------|------|------|
| `graph_service.py` | 图谱查询与序列化 | Neo4j |
| `match_service.py` | 匹配诊断 + 学习路径生成 | Neo4j + PostgreSQL |
| `resume_service.py` | 简历解析 (PDF/DOCX) | - |
| `judge_service.py` | LLM 评估 | - |
| `recommendation_service.py` | 岗位推荐 | Neo4j |
| `dedup_service.py` | 去重服务 | Redis |
| `resources.py` | 资源生命周期管理 | PG + Neo4j + Redis |

### 3.5 数据模型层 (16 个 SQLAlchemy 模型)

#### 抽取模型 (`extraction_models.py`)

| 模型 | 用途 |
|------|------|
| `JDExtractionRecord` | JD 抽取结果 |
| `RawJDRecord` | 原始 JD 数据 |
| `SkillAliasRecord` | 技能别名映射 |
| `ExtractionEvaluationRecord` | 抽取质量评估 |
| `PositionSkillRelation` | 岗位-技能多对多关系 |
| `SystemConfig` | 系统配置键值存储 |
| `SkillRecord` | 技能主数据 |
| `PositionRecord` | 岗位主数据 |
| `MatchResult` | 匹配结果 (含 CII 指数) |
| `ReviewQueue` | 人工审核队列 |

#### 流水线模型 (`pipeline_models.py`)

| 模型 | 用途 |
|------|------|
| `PipelineRun` | 流水线运行记录 |
| `PipelineSchedule` | 定时调度配置 |
| `DataSourceRecord` | 数据源注册 |
| `LoopResultRecord` | 闭环运行结果 (JSONB) |

#### 学习模型 (`learning_models.py`)

| 模型 | 用途 |
|------|------|
| `LearningPlan` | 学习计划 |
| `LearningProgress` | 单技能进度 |
| `SkillPrerequisite` | 技能前置条件 DAG 边 |

#### 演化模型 (`evolution_models.py`)

| 模型 | 用途 |
|------|------|
| `EvolutionSnapshot` | 岗位技能快照 |
| `EvolutionChangelog` | 变更日志 |
| `EvolutionPath` | 岗位演化路径 |
| `SkillTimeseries` | 技能频率时间序列 |

### 3.6 流水线与任务

| 组件 | 职责 |
|------|------|
| `app/pipeline/engine.py` | SSE 流式流水线引擎 (5 步) |
| `app/pipeline/steps.py` | 具体步骤: 简历解析→技能抽取→匹配→学习路径→推荐 |
| `app/pipeline/contracts.py` | 数据契约 + PipelineStep 协议 |
| `app/tasks/celery_app.py` | Celery 应用 + 6 个任务定义 |
| `app/tasks/stage3_services.py` | 抽取持久化 + 图谱写入 + 演化分析 |

---

## 4. 前端模块详解 (Frontend)

### 4.1 技术栈

- **框架**: Vue 3.4 + Composition API
- **构建**: Vite 5
- **状态管理**: Pinia 2 (Composition API 风格, ref/computed)
- **UI 库**: Element Plus 2.6 (zh-CN 本地化)
- **图表**: ECharts 5.5 + vue-echarts 6.6
- **HTTP**: Axios 1.6
- **3D 图谱**: 3d-force-graph 1.80 + Three.js 0.185
- **2D 图谱**: @antv/g6 5.0
- **Mock**: MSW 2.2

### 4.2 页面结构 (14 个路由)

| 页面 | 路径 | 功能 |
|------|------|------|
| Home | `/` | 3D/2D 图谱可视化 |
| MatchDiagnosis | `/match` | 5 步匹配向导 |
| LearningCenter | `/learning` | 学习计划管理 |
| DataDashboard | `/dashboard` | 数据大屏 KPI |
| PipelineMonitor | `/pipeline` | 流水线监控 |
| Admin | `/admin` | 管理后台 |
| DataSources | `/datasources` | 数据源管理 |
| PositionDetail | `/position/:id` | 岗位详情 |
| Evolution | `/evolution` | 演化分析 |
| Quality | `/quality` | 质量监控 |
| Judge | `/judge` | Judge 评估 |
| JobSeeker | `/jobseeker` | 求职者分析 |
| LoopDemo | `/loop` | 闭环演示 |
| Settings | `/settings` | 系统设置 |

### 4.3 状态管理 (Pinia Stores)

| Store | 职责 | 关键状态 |
|-------|------|----------|
| `graph.ts` | 三层图谱导航 | domain → position → detail |
| `match.ts` | 匹配诊断 | person_skills, target_position, result |
| `learning.ts` | 学习中心 | plans, progress, recommendations |
| `dashboard.ts` | 数据大屏 | overview, trends, distribution, events |
| `pipeline.ts` | 流水线监控 | runs, stages, schedules, SSE |
| `jobseeker.ts` | 求职者分析 | resume, extracted_skills, matches |
| `loop.ts` | 闭环执行 | run_id, steps, status |
| `admin.ts` | 管理后台 | stats, review_queue, prompts |
| `evolution.ts` | 演化分析 | trends, paths, emerging_skills |
| `quality.ts` | 质量监控 | report, alerts, trends |
| `datasource.ts` | 数据源 | sources, stats |

### 4.4 关键组件

| 组件 | 用途 | 技术 |
|------|------|------|
| `Graph3D.vue` | 3D 力导向图谱 | 3d-force-graph |
| `Graph2D.vue` | 2D 图谱 (G6 v5) | @antv/g6 |
| `SkillRadar.vue` | 双层雷达图 | ECharts |
| `PipelineDag.vue` | DAG 时间线可视化 | 自定义 SVG |
| `PipelineQualityPanel.vue` | 质量监控面板 | ECharts |
| `DataQualityGauge.vue` | 数据质量仪表盘 | ECharts |
| `MainLayout.vue` | 侧边栏布局 + 暗黑模式 | Element Plus |

### 4.5 可复用逻辑 (Composables)

| Composable | 职责 |
|------------|------|
| `useSSE.ts` | SSE 连接 + 指数退避重连 + 轮询降级 |
| `usePipelineMonitor.ts` | 流水线监控逻辑 |
| `useKPI.ts` | KPI 计算 |

---

## 5. 爬虫模块详解 (Crawler)

### 5.1 架构

```
CLI (run.py)
  ├── init          → 初始化数据库
  ├── <site>        → 爬取指定站点
  ├── stealth_all   → 全量 stealth 爬取
  ├── apify_*       → Apify Actor 集成
  └── stats         → 统计查询

Spider 层
  ├── lagou.py / lagou_stealth.py      → 拉勾网
  ├── job51.py / job51_stealth.py      → 51job
  └── boss.py                          → BOSS 直聘

Pipeline 层
  ├── clean.py        → HTML 清洗
  ├── dedup.py        → SimHash 64 位去重 (汉明距离 ≤3)
  ├── incremental.py   → 增量过滤
  ├── storage.py      → PostgreSQL 写入
  └── quality_report.py → 质量报告

数据层
  ├── models.py       → SQLAlchemy ORM (jd_raw, compliance_log)
  ├── database.py     → 引擎 + 连接池
  └── dao.py          → 增删改查
```

### 5.2 关键特性

- **双模式爬取**: HTTP (Scrapy) + Playwright Stealth (反 WAF)
- **合规优先**: robots.txt 缓存 + QPS 限流 (≤1) + 代理池 + 审计日志
- **SimHash 去重**: 64 位局部敏感哈希，汉明距离 ≤3 判定重复
- **Apify 集成**: 外部 Actor 抽象层，统一字段提取

---

## 6. 契约模块详解 (Contracts)

### 6.1 设计哲学

**契约优先 (Contract-First)**: `openapi.yaml` 先行编辑，后端路由和前端类型随后同步。

### 6.2 文件结构

| 文件 | 职责 |
|------|------|
| `openapi.yaml` | OpenAPI 3.0.3 规范 — API 权威定义 |
| `models/__init__.py` | Pydantic v2 共享模型，与 OpenAPI 同步 |
| `validate.py` | CI 验证脚本 (YAML + Python + 一致性检查) |
| `graph_cypher/query_templates.cypher` | Neo4j 查询模板 |
| `CHANGELOG.md` | 版本历史 (v1.0.0 → v1.2.0) |

### 6.3 验证流程

```
CI 触发
  → validate_openapi()      → 检查 YAML 结构
  → validate_models_py()    → 编译 Python 模型
  → validate_consistency()  → 交叉引用一致性
  → 退出码: 0=通过, 1=数据错误, 2=逻辑/模式不匹配
```

---

## 7. 基础设施 (Docker/CI)

### 7.1 Docker 服务 (开发)

| 服务 | 镜像 | 端口 | 用途 |
|------|------|------|------|
| backend | Python 3.11 + Poetry | 8000 | FastAPI 应用 |
| celery-worker | Python 3.11 + Poetry | - | 异步任务 |
| frontend | Node 20 + Vite | 5173 | Vue 3 开发服务器 |
| neo4j | Neo4j 5 Community | 7474/7687 | 图数据库 |
| postgres | PostgreSQL 16 | 5432 | 关系数据库 |
| redis | Redis 7 Alpine | 6379 | 缓存/消息队列 |
| chroma | ChromaDB | 8001 | 向量数据库 |
| ollama | Ollama | 11434 | 本地 LLM (Qwen2.5-7B) |

### 7.2 CI 流水线 (GitHub Actions)

```
PR/Push 触发
  ├── 契约验证      → validate.py
  ├── 后端流水线    → Ruff lint → Mypy typecheck → Pytest (60% 覆盖率门限) → OpenAPI 一致性
  ├── 前端流水线    → npm install → gen:api → ESLint → TypeScript typecheck → Build
  ├── 爬虫流水线    → 编译检查 → Pytest (跳过 DB 依赖测试)
  └── Docker 冒烟   → docker compose up → 健康检查 (手动/定时)
```

---

## 8. 测试体系

### 8.1 后端测试

| 类别 | 位置 | 框架 | 覆盖率 |
|------|------|------|--------|
| 单元测试 | `backend/tests/unit/` | pytest + AsyncMock | 目标 60%+ |
| 集成测试 | `backend/tests/integration/` | TestClient + pytest-asyncio | - |
| 配置测试 | `backend/tests/` | pytest | - |

**关键 fixture**:
- `TestClient` (FastAPI 测试客户端)
- Mock LLM 模式 (`AsyncMock` + `patch`)

### 8.2 前端测试

| 类别 | 框架 | 配置 |
|------|------|------|
| 单元测试 | Vitest | `vite.config.ts` |
| E2E 测试 | Playwright | `playwright.config.ts` |
| Mock | MSW | `src/mock/handlers.ts` |

### 8.3 E2E 测试

| 文件 | 框架 | 覆盖 |
|------|------|------|
| `tests/e2e/browser_qa_extended.py` | Playwright | 扩展浏览器 QA |
| `test_all_pages.py` | Playwright | 全页面导航 |
| `_e2e_test.py` | Playwright | 核心 E2E |

---

## 9. 数据流与业务闭环

### 9.1 主数据流水线

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  爬虫    │ → │  清洗    │ → │  去重    │ → │  抽取    │ → │  图谱    │
│ Crawler │    │ Clean   │    │ Dedup   │    │ Extract │    │ Graph   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
     │                                                    │
     ▼                                                    ▼
┌─────────┐                                         ┌─────────┐
│ PostgreSQL│                                         │  Neo4j  │
│ jd_raw   │                                         │ 岗位-技能 │
└─────────┘                                         └─────────┘
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              ▼                           ▼                           ▼
                        ┌─────────┐                 ┌─────────┐                 ┌─────────┐
                        │  演化分析 │                 │  匹配诊断 │                 │  学习路径 │
                        │Evolution│                 │  Match  │                 │ Learning│
                        └─────────┘                 └─────────┘                 └─────────┘
                              │                           │                           │
                              ▼                           ▼                           ▼
                        ┌─────────┐                 ┌─────────┐                 ┌─────────┐
                        │ 趋势/路径 │                 │ 差距分析  │                 │ 学习计划  │
                        │ 新兴检测  │                 │ CII 指数 │                 │ 进度跟踪  │
                        └─────────┘                 └─────────┘                 └─────────┘
```

### 9.2 用户业务闭环 (5 步)

```
1. 上传简历/输入 JD
        ↓
2. 技能抽取 (LLM)
        ↓
3. 图谱更新 (Neo4j)
        ↓
4. 匹配诊断 (岗位匹配 + 差距分析)
        ↓
5. 学习路径生成 (个性化学习计划)
```

### 9.3 演化分析闭环 (8 步)

```
1. 加载岗位快照 (PostgreSQL)
        ↓
2. 差异计算 (DiffEngine)
        ↓
3. 信任评分 (TrustScorer)
        ↓
4. 幻觉防御 (HallucinationGuard)
        ↓
5. 新兴检测 (EmergenceFinder)
        ↓
6. 路径发现 (PathRecommender)
        ↓
7. 保存变更日志 (PostgreSQL)
        ↓
8. 更新演化图谱 (Neo4j EVOLVES_TO)
```

---

## 10. 关键设计模式

| 模式 | 应用位置 | 说明 |
|------|----------|------|
| **契约优先** | `starmap-contracts/` | OpenAPI YAML 先行，前后端同步 |
| **依赖注入** | `app/dependencies.py` | FastAPI `Depends()` 提供 DB/Neo4j/Redis |
| **生命周期管理** | `app/main.py` | `@asynccontextmanager` 管理资源启停 |
| **优雅降级** | `dashboard_service.py` | 单源故障不导致 500，返回 stale 缓存 |
| **SSE + 轮询降级** | `sse_broadcaster.py` | Redis pub/sub 实时 + LPUSH 列表轮询 |
| **三层幻觉防御** | `hallucination_guard.py` | 本体白名单 → 多源验证 → 置信度+LLM |
| **指数衰减信任** | `trust_integration.py` | `score × exp(-0.15 × Δt_months)` |
| **Z-score 新兴检测** | `emergence_finder.py` | 统计异常 + 可移植性评分 |
| **拓扑排序路径** | `path_engine.py` | Kahn 算法 + 前置条件 DAG |
| **协议化流水线步骤** | `pipeline/contracts.py` | `PipelineStep` Protocol 结构化类型 |
| **自包含 DB 会话** | `tasks/celery_app.py` | 每个 Celery 任务独立创建/销毁引擎 |
| **STOP 标志取消** | `core/pipeline/orchestrator.py` | Redis 标志实现流水线优雅取消 |
| **SimHash 去重** | `crawler/dedup.py` | 64 位局部敏感哈希 |
| **双模式爬虫** | `crawler/spiders/` | HTTP + Playwright Stealth |
| **LRU 缓存** | `config.py`, `path_engine.py` | `@lru_cache` 配置单例，TTL 缓存 Neo4j 查询 |
| **加权数据融合** | `pipeline/data_fusion.py` | 权威加权 + 交叉验证 |

---

## 11. 模块依赖关系图

### 11.1 后端内部依赖

```
main.py
  ├── config.py (settings)
  ├── dependencies.py
  │     └── resources.py (AppResources)
  ├── api/v1/router.py
  │     ├── graph.py → graph_service + Neo4j
  │     ├── position.py → PositionRecord + EmergenceFinder
  │     ├── match.py → match_service + Neo4j + PG
  │     ├── evolution.py → EvolutionOrchestrator + EmergenceFinder
  │     ├── quality.py → quality_monitor + resume_eval
  │     ├── learning.py → path_engine + progress_tracker
  │     ├── admin.py → prompt + Neo4j + _build_quality_dashboard
  │     ├── dashboard.py → dashboard_service + sse_broadcaster
  │     ├── datasource.py → DataSourceRecord + PipelineRun
  │     ├── extract.py → jd_extract + graph_writer
  │     ├── judge.py → judge_service
  │     ├── loop.py → LoopOrchestrator
  │     ├── resume.py → resume_service
  │     └── pipeline/routes.py → PipelineEngine + orchestrator + executor
  └── core/pipeline/cron_scheduler (lazy import)

core/evolution/orchestrator.py
  ├── diff_engine.py
  ├── emergence_finder.py
  ├── hallucination_guard.py
  ├── trust_integration.py
  ├── path_recommender.py
  ├── snapshot_manager.py
  └── graph_writer (Neo4j)

core/learning/path_engine.py
  ├── services/resources (Neo4j driver)
  └── match_service (PROFICIENCY_SCORE)

tasks/celery_app.py
  ├── core/pipeline/orchestrator
  ├── core/pipeline/executor
  ├── tasks/stage3_services
  └── utils/async_helpers (run_async)
```

### 11.2 前后端交互

```
Frontend (Vue 3 + Pinia)
  ├── Axios → /api/v1/graph/*
  ├── Axios → /api/v1/positions/*
  ├── Axios → /api/v1/match/*
  ├── Axios → /api/v1/evolution/*
  ├── Axios → /api/v1/learning/*
  ├── SSE → /dashboard/realtime
  ├── SSE → /pipeline/events
  └── SSE → /pipeline/analyze (简历分析流)
```

### 11.3 爬虫与后端集成

```
Crawler
  ├── jd_raw (PostgreSQL) → Backend 读取
  ├── compliance_log (PostgreSQL) → 审计
  ├── jd_extraction_records (PostgreSQL) → R3 读取
  └── export_triples.py → Neo4j Cypher MERGE
```

---

## 12. 开发建议

### 12.1 新增功能时应遵循

1. **契约优先**: 先编辑 `starmap-contracts/openapi.yaml`，再实现后端路由和前端类型
2. **依赖注入**: 新路由使用 `Depends(get_db_session())` / `Depends(get_neo4j_driver())`
3. **配置集中**: 新阈值/参数加入 `app/config.py` Settings，禁止硬编码
4. **路由注册**: 新模块在 `app/api/v1/router.py` 中注册
5. **Alembic 迁移**: 模型变更必须通过 Alembic，禁止手动 DDL
6. **质量门限**: 新模块需通过 Ruff + Mypy + Pytest (60% 覆盖率)
7. **Mock 先行**: 前端开发时先在 `src/mock/handlers.ts` 添加 MSW 处理器

### 12.2 应复用的组件

- `PositionRepository` — 所有 Neo4j 岗位数据访问
- `HallucinationGuard` + `TrustScorer` — 新数据入管道必须经过
- `PipelineContext` + `PipelineStep` Protocol — 新用户流程添加步骤
- `useSSE` composable — 实时更新需求
- `dashboard_service.py` 模式 — 优雅降级 + 缓存
- `run_async()` — Celery 任务中的 async→sync 桥接

### 12.3 已知问题与改进点

| 问题 | 位置 | 建议 |
|------|------|------|
| 时序加载模式重复 | `evolution.py` (4 次), `position.py` | 提取为共享工具函数 |
| N+1 查询 | `position.py` 列表 | 单次 JOIN + group-by |
| 无认证 | `learning.py` (user_id="anonymous") | 添加身份验证 |
| 学习阶段未持久化 | `learning.py` GET /plan | 存储阶段结果 |
| 版本漂移 | `__init__.py`, `main.py`, `pyproject.toml` | 使用 `importlib.metadata` |
| CORS 硬编码 | `main.py` | 从 settings 读取 |
| Mypy 配置分散 | `mypy.ini` + `pyproject.toml` | 合并到 `pyproject.toml` |
| 逻辑外键无约束 | 多个模型 | 添加 `ForeignKey()` |
| 缺少复合唯一约束 | `SkillPrerequisite`, `PositionSkillRelation` 等 | 添加 `UniqueConstraint` |
| `MatchResult` 未导出 | `models/__init__.py` | 加入 `__all__` |
| `trend_detector.py` 缺失 | `core/evolution/` | 实现或移除引用 |

---

## 附录: 项目文件索引

### 后端核心文件 (按模块)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── dependencies.py      # DI 依赖
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py    # 路由聚合
│   │       ├── admin.py     # 20 端点
│   │       ├── dashboard.py # 5 端点
│   │       ├── datasource.py # 5 端点
│   │       ├── evolution.py # 13 端点
│   │       ├── extract.py   # 2 端点
│   │       ├── graph.py     # 3 端点
│   │       ├── judge.py     # 3 端点
│   │       ├── learning.py  # 6 端点
│   │       ├── loop.py      # 3 端点
│   │       ├── match.py     # 5 端点
│   │       ├── position.py  # 3 端点
│   │       ├── quality.py   # 7 端点
│   │       ├── resume.py    # 1 端点
│   │       └── pipeline/
│   │           └── routes.py # 20 端点
│   ├── core/
│   │   ├── evolution/        # 演化分析引擎
│   │   │   ├── __init__.py
│   │   │   ├── diff_engine.py
│   │   │   ├── emergence_finder.py
│   │   │   ├── hallucination_guard.py
│   │   │   ├── orchestrator.py
│   │   │   ├── path_recommender.py
│   │   │   ├── snapshot_manager.py
│   │   │   └── trust_integration.py
│   │   ├── learning/         # 学习路径引擎
│   │   │   ├── __init__.py
│   │   │   ├── path_engine.py
│   │   │   └── progress_tracker.py
│   │   ├── dashboard/        # 仪表盘服务
│   │   │   ├── __init__.py
│   │   │   ├── dashboard_service.py
│   │   │   └── sse_broadcaster.py
│   │   ├── extraction/       # 抽取引擎
│   │   │   ├── jd_extract.py
│   │   │   ├── llm_client.py
│   │   │   ├── normalize.py
│   │   │   ├── prompt.py
│   │   │   └── graph_writer.py
│   │   └── pipeline/         # 流水线核心
│   │       ├── orchestrator.py
│   │       ├── executor.py
│   │       ├── cron_scheduler.py
│   │       ├── data_fusion.py
│   │       ├── simhash.py
│   │       └── status_aggregator.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── extraction_models.py   # 10 模型
│   │   ├── pipeline_models.py     # 4 模型
│   │   ├── learning_models.py     # 3 模型
│   │   └── evolution_models.py    # 4 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── graph_service.py
│   │   ├── match_service.py
│   │   ├── resume_service.py
│   │   ├── judge_service.py
│   │   ├── recommendation_service.py
│   │   ├── dedup_service.py
│   │   └── resources.py
│   ├── repositories/
│   │   └── position_repository.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── contracts.py
│   │   ├── engine.py
│   │   └── steps.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   └── stage3_services.py
│   └── utils/
│       └── async_helpers.py
├── pyproject.toml
├── mypy.ini
├── alembic.ini
└── Dockerfile.dev
```

### 前端核心文件

```
frontend/
├── src/
│   ├── main.ts              # 应用启动
│   ├── App.vue              # 根组件
│   ├── router/
│   │   └── index.ts         # 14 路由定义
│   ├── api/
│   │   ├── request.ts       # Axios 实例
│   │   └── schema.ts        # OpenAPI 生成类型
│   ├── stores/
│   │   ├── graph.ts
│   │   ├── match.ts
│   │   ├── learning.ts
│   │   ├── dashboard.ts
│   │   ├── pipeline.ts
│   │   ├── jobseeker.ts
│   │   ├── loop.ts
│   │   ├── admin.ts
│   │   ├── evolution.ts
│   │   ├── quality.ts
│   │   └── datasource.ts
│   ├── composables/
│   │   ├── useSSE.ts
│   │   ├── usePipelineMonitor.ts
│   │   └── useKPI.ts
│   ├── components/
│   │   ├── Graph3D.vue
│   │   ├── Graph2D.vue
│   │   ├── SkillRadar.vue
│   │   ├── PipelineDag.vue
│   │   ├── PipelineQualityPanel.vue
│   │   └── DataQualityGauge.vue
│   ├── pages/
│   │   ├── Home.vue
│   │   ├── MatchDiagnosis.vue
│   │   ├── LearningCenter.vue
│   │   ├── DataDashboard.vue
│   │   ├── PipelineMonitor.vue
│   │   ├── Admin.vue
│   │   ├── DataSources.vue
│   │   ├── PositionDetail.vue
│   │   ├── Evolution.vue
│   │   ├── Quality.vue
│   │   ├── Judge.vue
│   │   ├── JobSeeker.vue
│   │   ├── LoopDemo.vue
│   │   └── Settings.vue
│   ├── layouts/
│   │   └── MainLayout.vue
│   ├── utils/
│   │   ├── graphColors.ts
│   │   └── chartTheme.ts
│   └── mock/
│       └── handlers.ts
├── package.json
├── vite.config.ts
└── tsconfig.json
```

### 爬虫核心文件

```
crawler/
├── run.py                   # CLI 入口
├── config.py                # 环境配置
├── compliance.py            # 合规层
├── dedup.py                 # SimHash 去重
├── stealth.py               # Playwright 隐身
├── spiders/
│   ├── lagou.py / lagou_stealth.py
│   ├── job51.py / job51_stealth.py
│   └── boss.py
├── pipelines/
│   ├── items.py
│   ├── clean.py
│   ├── dedup.py
│   ├── incremental.py
│   ├── storage.py
│   └── quality_report.py
├── persistence/
│   ├── models.py
│   ├── database.py
│   ├── dao.py
│   ├── extraction_models.py
│   └── extraction_dao.py
└── scripts/
    ├── apify_*.py
    ├── run_incremental.py
    └── export_triples.py
```

### 契约模块文件

```
starmap-contracts/
├── openapi.yaml             # OpenAPI 3.0.3 规范
├── models/
│   └── __init__.py          # Pydantic 共享模型
├── validate.py              # CI 验证脚本
├── graph_cypher/
│   └── query_templates.cypher
└── CHANGELOG.md
```

---

> **报告结束** — 本报告基于对 StarMap 项目全部源代码的系统化阅读和分析生成。
