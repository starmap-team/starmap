# StarMap 全代码文件索引与模块分析

> 生成时间: 2026-07-10
> 项目: StarMap 人才能力星云导航系统
> 用途: 全代码文件索引、模块理解、问题发现

---

## 一、项目概览

### 1.1 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11-3.12 / FastAPI 0.110+ / SQLAlchemy async / Neo4j / PostgreSQL / Redis / Celery |
| 前端 | Vue 3.4+ / TypeScript 5.4+ / Element Plus / Pinia / ECharts / @antv/G6 / Vite |
| LLM | 星火 API / MiMo / DeepSeek / Qwen (Ollama) |
| 测试 | pytest + vitest + Playwright |
| 代码质量 | Ruff + mypy + ESLint + vue-tsc |

### 1.2 文件统计

| 类型 | 数量 |
|------|------|
| Python 文件 (.py) | 319 |
| TypeScript 文件 (.ts) | 79 |
| Vue 文件 (.vue) | 55 |
| Markdown 文件 (.md) | 115 |
| JSON 文件 (.json) | 41 |
| 其他 | ... |

---

## 二、后端模块索引 (backend/)

### 2.1 API 路由层 (backend/app/api/v1/)

| 文件 | 模块 | 端点 | 前端 Store | 状态 |
|------|------|------|-----------|------|
| `router.py` | 路由聚合 | - | - | ✅ 正常 |
| `admin.py` | 管理后台 | `/admin/*` | `stores/admin.ts` | ✅ 正常 |
| `admin_graph_nodes.py` | 图谱节点管理 | `/admin/graph/nodes` | `stores/admin.ts` | ✅ 正常 |
| `admin_prompts.py` | 提示词管理 | `/admin/prompts` | `stores/admin.ts` | ✅ 正常 |
| `dashboard.py` | 数据大屏 | `/dashboard/*` | `stores/dashboard.ts` | ✅ 正常 |
| `datasource.py` | 数据源管理 | `/datasources/*` | `stores/datasource.ts` | ✅ 正常 |
| `evolution.py` | 演化分析 | `/evolution/*` | `stores/evolution.ts` | ⚠️ 字段不一致 |
| `evolution_career_path.py` | 职业路径 | `/evolution/career-path` | `stores/learning.ts` | ✅ 正常 |
| `evolution_emerging_alerts.py` | 新兴技能预警 | `/evolution/emerging-alerts` | `stores/evolution.ts` | ✅ 正常 |
| `evolution_industry_report.py` | 行业趋势报告 | `/evolution/industry-report` | `stores/learning.ts` | ✅ 正常 |
| `extract.py` | 信息提取 | `/extract/*` | `stores/jd.ts` | ⚠️ 字段不一致 |
| `graph.py` | 图谱查询 | `/graph/*` | `stores/graph.ts` | ⚠️ 字段不一致 |
| `judge.py` | Judge 评估 | `/judge/*` | - | ✅ 正常 |
| `learning.py` | 学习中心 | `/learning/*` | `stores/learning.ts` | ✅ 正常 |
| `loop.py` | 闭环验证 | `/loop/*` | `stores/loop.ts` | ✅ 正常 |
| `match.py` | 匹配诊断 | `/match/*` | `stores/match.ts` | ⚠️ 字段不一致 |
| `position.py` | 职位管理 | `/positions/*` | `stores/jd.ts` | ✅ 正常 |
| `quality.py` | 质量监控 | `/quality/*` | `stores/quality.ts` | ⚠️ 字段不一致 |
| `quality_trends_alerts.py` | 质量趋势预警 | `/quality/trends` | `stores/quality.ts` | ✅ 正常 |
| `resume.py` | 简历解析 | `/resume/*` | `stores/resume.ts` | ✅ 正常 |
| `pipeline/routes.py` | 流水线 | `/pipeline/*` | `stores/pipeline.ts` | ✅ 正常 |

### 2.2 业务核心层 (backend/app/core/)

| 目录 | 用途 | 关键文件 |
|------|------|---------|
| `core/extraction/` | 信息提取 | `jd_extract.py`, `resume_eval.py`, `normalize.py` |
| `core/evolution/` | 演化分析 | `emergence_finder.py`, `snapshot_manager.py`, `path_recommender.py` |
| `core/matching/` | 匹配诊断 | `scorer.py`, `path_builder.py`, `service.py` |
| `core/learning/` | 学习路径 | `path_engine.py`, `progress_tracker.py` |
| `core/pipeline/` | 流水线 | `orchestrator.py`, `executor.py`, `quality_monitor.py` |
| `core/dashboard/` | 数据大屏 | `dashboard_service.py`, `sse_broadcaster.py` |

### 2.3 服务层 (backend/app/services/)

| 文件 | 用途 |
|------|------|
| `graph_service.py` | Neo4j 图谱查询 |
| `match_service.py` | 匹配计算 |
| `resume_service.py` | 简历解析 |
| `learning_service.py` | 学习路径生成 |
| `judge_service.py` | Judge 评估 |
| `recommendation_service.py` | 推荐系统 |
| `neo4j_service.py` | Neo4j 连接管理 |
| `dedup_service.py` | 去重服务 |

### 2.4 模型层 (backend/app/models/)

| 文件 | 用途 |
|------|------|
| `extraction_models.py` | 提取模型 (PositionRecord, SkillRecord) |
| `evolution_models.py` | 演化模型 (EvolutionChangelog, EvolutionPath) |
| `learning_models.py` | 学习模型 (LearningPlan, SkillProgress) |
| `pipeline_models.py` | 流水线模型 (PipelineRun, PipelineStage) |

---

## 三、前端模块索引 (frontend/src/)

### 3.1 API 层 (frontend/src/api/)

| 文件 | 用途 | 状态 |
|------|------|------|
| `client.ts` | 类型化 API 客户端 | ✅ 正常 |
| `request.ts` | axios 实例封装 | ⚠️ 需要改进 |
| `request.improved.ts` | 改进版请求客户端 | ✅ 已提供 |
| `schema.ts` | OpenAPI 生成的 TypeScript 类型 | ⚠️ 可能过期 |

### 3.2 状态管理 (frontend/src/stores/)

| 文件 | 模块 | 后端路由 | 状态 |
|------|------|---------|------|
| `admin.ts` | 管理后台 | `/admin/*` | ✅ 正常 |
| `dashboard.ts` | 数据大屏 | `/dashboard/*` | ⚠️ 字段映射 |
| `datasource.ts` | 数据源 | `/datasources/*` | ✅ 正常 |
| `evolution.ts` | 演化分析 | `/evolution/*` | ⚠️ 字段不一致 |
| `graph.ts` | 图谱查询 | `/graph/*` | ⚠️ 字段不一致 |
| `jd.ts` | JD 提取 | `/extract/*`, `/positions/*` | ⚠️ 字段不一致 |
| `learning.ts` | 学习中心 | `/learning/*` | ✅ 正常 |
| `loop.ts` | 闭环验证 | `/loop/*` | ✅ 正常 |
| `match.ts` | 匹配诊断 | `/match/*` | ⚠️ 字段不一致 |
| `pipeline.ts` | 流水线 | `/pipeline/*` | ✅ 正常 |
| `quality.ts` | 质量监控 | `/quality/*` | ⚠️ 字段不一致 |
| `resume.ts` | 简历解析 | `/resume/*` | ✅ 正常 |
| `user.ts` | 用户管理 | - | ✅ 正常 |

### 3.3 页面组件 (frontend/src/pages/)

| 文件 | 路由 | 对应 Store | 后端路由 |
|------|------|-----------|---------|
| `Home.vue` | `/` | `graph.ts` | `/graph/*` |
| `MatchDiagnosis.vue` | `/match` | `match.ts` | `/match/*` |
| `ExtractJD.vue` | `/extract` | `jd.ts` | `/extract/*` |
| `EvolutionDashboard.vue` | `/evolution` | `evolution.ts` | `/evolution/*` |
| `LearningCenter.vue` | `/learning` | `learning.ts` | `/learning/*` |
| `DataDashboard.vue` | `/dashboard` | `dashboard.ts` | `/dashboard/*` |
| `QualityDashboard.vue` | `/quality` | `quality.ts` | `/quality/*` |
| `PipelineMonitor.vue` | `/pipeline` | `pipeline.ts` | `/pipeline/*` |
| `Admin.vue` | `/admin` | `admin.ts` | `/admin/*` |
| `DataSources.vue` | `/datasources` | `datasource.ts` | `/datasources/*` |
| `PositionList.vue` | `/positions` | `jd.ts` | `/positions/*` |
| `PositionDetail.vue` | `/positions/:id` | `jd.ts` | `/positions/:id` |

---

## 四、契约文件索引 (starmap-contracts/)

| 文件 | 用途 | 状态 |
|------|------|------|
| `openapi.yaml` | API 契约定义 | ⚠️ 与实现有偏差 |
| `graph_cypher/` | Cypher 查询模板 | ✅ 正常 |
| `models/` | 数据模型定义 | ✅ 正常 |

---

## 五、测试文件索引

### 5.1 后端测试 (backend/tests/)

| 目录 | 用途 |
|------|------|
| `unit/` | 单元测试 |
| `integration/` | 集成测试 |
| `fixtures/` | 测试数据 |

### 5.2 前端测试 (frontend/src/stores/__tests__/)

| 文件 | 测试对象 |
|------|---------|
| `admin.test.ts` | `stores/admin.ts` |
| `graph.test.ts` | `stores/graph.ts` |
| `match.test.ts` | `stores/match.ts` |
| `quality.test.ts` | `stores/quality.ts` |
| `resume.test.ts` | `stores/resume.ts` |

### 5.3 集成测试 (tests/integration/)

| 文件 | 用途 |
|------|------|
| `api-contract.test.ts` | API 契约测试 |
| `api-integration.test.ts` | 全模块联调测试 |

---

## 六、问题模块标记

### 6.1 严重问题 (Critical)

| 模块 | 问题 | 影响 |
|------|------|------|
| 后端编码 | 中文乱码 (GBK/UTF-8 混用) | 代码不可读，运行时错误 |
| API 路径 | Vite 代理配置不匹配 | 请求路由错误 |

### 6.2 中等问题 (Major)

| 模块 | 问题 | 影响 |
|------|------|------|
| `match.py` ↔ `match.ts` | `match_id` 和 `target_position` 字段 required/optional 不一致 | 类型不匹配 |
| `extract.py` ↔ `jd.ts` | `skills` 和 `position` 字段未在契约中定义 | 运行时错误 |
| `graph.py` ↔ `graph.ts` | `total_positions` 和 `total_skills` 未使用 | 数据不一致 |
| `request.ts` | Loading 状态管理问题 | 并发请求 UI 异常 |
| `request.ts` | 错误处理未使用后端 detail | 用户体验差 |

### 6.3 低等问题 (Minor)

| 模块 | 问题 | 影响 |
|------|------|------|
| 代码注释 | 乱码 | 可读性 |
| 未使用导入 | `match.py` 中 `get_match_result` 未使用 | 代码质量 |

---

## 七、模块依赖图

```
前端 (frontend/src/)
├── api/
│   ├── client.ts ────────→ 类型化 API 调用
│   ├── request.ts ────────→ axios 实例 (需要改进)
│   └── schema.ts ─────────→ OpenAPI 生成的类型
├── stores/
│   ├── match.ts ──────────→ POST /match/position
│   ├── jd.ts ─────────────→ POST /extract/jd, GET /positions
│   ├── graph.ts ──────────→ GET /graph/overview
│   ├── evolution.ts ──────→ GET /evolution/trends
│   ├── quality.ts ────────→ GET /quality/dashboard
│   ├── learning.ts ───────→ POST /learning/plan
│   ├── pipeline.ts ───────→ GET /pipeline/status
│   └── ...
├── pages/
│   ├── MatchDiagnosis.vue ──→ stores/match.ts
│   ├── ExtractJD.vue ──────→ stores/jd.ts
│   ├── Home.vue ───────────→ stores/graph.ts
│   └── ...
└── components/
    ├── SkillRadar.vue ─────→ stores/match.ts
    ├── Graph3D.vue ────────→ stores/graph.ts
    └── ...

后端 (backend/app/)
├── api/v1/
│   ├── match.py ───────────→ services/match_service.py
│   ├── extract.py ─────────→ core/extraction/jd_extract.py
│   ├── graph.py ───────────→ services/graph_service.py
│   ├── evolution.py ───────→ core/evolution/emergence_finder.py
│   ├── quality.py ─────────→ core/pipeline/quality_monitor.py
│   └── ...
├── core/
│   ├── extraction/ ────────→ LLM 提取逻辑
│   ├── evolution/ ─────────→ 演化分析算法
│   ├── matching/ ──────────→ 匹配计算
│   ├── learning/ ──────────→ 学习路径生成
│   └── pipeline/ ──────────→ 流水线编排
├── services/
│   ├── graph_service.py ───→ Neo4j 查询
│   ├── match_service.py ───→ 匹配计算
│   └── ...
├── models/
│   ├── extraction_models.py
│   ├── evolution_models.py
│   └── ...
└── tasks/
    └── celery_app.py ──────→ 异步任务
```

---

## 八、使用指南

### 8.1 快速定位文件

| 需求 | 文件路径 |
|------|---------|
| 查看 API 契约 | `starmap-contracts/openapi.yaml` |
| 查看后端路由 | `backend/app/api/v1/*.py` |
| 查看前端状态 | `frontend/src/stores/*.ts` |
| 查看页面组件 | `frontend/src/pages/*.vue` |
| 查看业务逻辑 | `backend/app/core/**/*.py` |
| 查看服务层 | `backend/app/services/*.py` |

### 8.2 问题排查流程

1. **契约不一致**: 检查 `openapi.yaml` ↔ 后端 Pydantic 模型 ↔ 前端 TypeScript 类型
2. **接口错误**: 检查后端路由 ↔ 前端请求路径
3. **字段错误**: 检查后端返回字段 ↔ 前端期望字段
4. **编码问题**: 检查文件编码是否为 UTF-8

---

## 九、附录

### 9.1 相关文档

| 文档 | 路径 |
|------|------|
| 联调规范 | `starmap-contracts/API_INTEGRATION_GUIDE.md` |
| 审计报告 | `starmap-contracts/CONTRACT_AUDIT.md` |
| 修复记录 | `docs/INTEGRATION_FIX_LOG.md` |
| 联调报告 | `docs/INTEGRATION_REPORT.md` |

### 9.2 自动化脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| 编码修复 | `scripts/fix-encoding.sh` | 修复后端编码乱码 |
| 契约验证 | `scripts/verify-contract.ts` | 验证契约一致性 |
| 同步检查 | `scripts/check-contract-sync.js` | 检查前后端同步 |
| 类型检查 | `scripts/check-type-sync.ts` | 检查类型同步 |

---

> 本索引由 StarMap 开发团队维护，如有问题请联系团队。
