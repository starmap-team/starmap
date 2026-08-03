# Requirements: StarMap 全系统重构与质量加固

**Defined:** 2026-07-24
**Core Value:** 技能匹配与图谱分析的核心链路必须准确、可追溯、可观测

## v1 Requirements

### 核心架构

- [ ] **ARCH-01**: Pipeline 双系统合一 — 消除 `backend/app/core/pipeline/` 与 `backend/app/sse_pipeline/` 的重叠，建立统一的 Pipeline 抽象
- [ ] **ARCH-02**: 消除裸 `except Exception` — 将 200+ 处替换为具体异常类型，关键路径使用 `logger.exception()` 记录完整追踪
- [ ] **ARCH-03**: 模块边界清晰化 — 明确 core/ 与 services/ 的职责边界，消除职责重叠
- [ ] **ARCH-04**: 密钥安全 — secrets/ 从 Git 移除，凭证轮换，迁移到 .env 或密钥管理器
- [ ] **ARCH-05**: 统一错误处理契约 — 所有业务异常统一使用 StarMapError 子类，API 层统一映射

### 数据管道（Pipeline）

- [ ] **PIPE-01**: executor.py（1138 行）按阶段拆分为独立模块（crawl / dedup / import / graph_sync）
- [ ] **PIPE-02**: loop_orchestrator.py（924 行）步骤级错误处理从 `except Exception` 改为具体异常类型，引入结构化日志
- [ ] **PIPE-03**: 死爬虫清理 — 移除指向 v2ex_remote 的假平台注册，保留单一爬虫路径或修复 Playwright 爬虫
- [ ] **PIPE-04**: SSE Pipeline 步骤契约冻结 — 为 PipelineContext 定义不可变接口，添加单元测试后合并
- [ ] **PIPE-05**: Pipeline 端到端集成测试 — 覆盖 crawl→import→graph_sync 全链路

### 演化引擎（Evolution）

- [ ] **EVOL-01**: orchestrator.py 错误处理升级 — 从 `except Exception` 改为 `EvolutionPipelineError` + 具体异常
- [ ] **EVOL-02**: 演化管道 E2E 集成测试 — 覆盖 snapshot→diff→trust→path 全链路
- [ ] **EVOL-03**: DiffEngine / TrustScorer / PathRecommender 接口契约化 — 明确定义输入输出类型
- [ ] **EVOL-04**: Snapshot 管理器增量快照支持 — 避免全量重建

### 技能抽取（Extraction）

- [ ] **EXTR-01**: normalize.py 硬编码 SKILL_ALIAS 迁移到 YAML — 移除模块级可变状态，封装为类或工厂函数
- [ ] **EXTR-02**: LLM 客户端接口契约化 — 定义 Provider 协议，每个供应商为独立实现
- [ ] **EXTR-03**: 反幻觉检查器独立化 — 从 jd_extract.py 中提取为独立模块，可单独测试

### 匹配推荐（Matching & Recommendation）

- [ ] **MAT-01**: match_service.py 去包装器 — 删除向后兼容层，直接使用 core/matching/ 组件
- [ ] **MAT-02**: 匹配缓存策略明确化 — 缓存键、TTL、失效策略文档化
- [ ] **MAT-03**: 推荐服务接口契约化 — recommendation_service.py 输入输出类型明确定义

### 测试质量

- [ ] **TEST-01**: 前端覆盖率修复 — vitest 配置包含源码文件，而非仅测试文件自身
- [ ] **TEST-02**: 前端页面级测试 — 为 18 个页面添加至少冒烟测试（渲染 + 基本交互）
- [ ] **TEST-03**: SSE Pipeline 测试 — 为 engine.py + steps.py + contracts.py 添加单元测试
- [ ] **TEST-04**: Graph Projector 测试 — 为 graph_projector.py 添加集成测试（PG + Neo4j）
- [ ] **TEST-05**: mypy 类型严格度逐步提升 — 从 `strict=false` 向 `strict=true` 过渡
- [ ] **TEST-06**: 后端覆盖率目标 85%+ — 从当前 80.42% 提升

### 基础设施

- [ ] **INFRA-01**: Git 安全 — secrets/ 加入 .gitignore，清除已追踪的密钥文件，轮换凭据
- [ ] **INFRA-02**: Docker Compose 安全 — 生产环境移除 `NO_PROXY=*`，Redis 添加默认密码
- [ ] **INFRA-03**: CORS 生产加固 — 生产环境 CORS 校验失败时明确报错而非仅警告
- [ ] **INFRA-04**: 文档更新 — 同步 AGENTS.md / 架构文档 / 部署文档，确保与实际代码一致

## Out of Scope

| 项目 | 原因 |
|------|------|
| 新功能开发 | 本次为重构与质量加固，不新增业务功能 |
| 前端 UI 重设计 | 仅做接口对齐和测试覆盖，不涉及视觉重设计 |
| 多爬虫平台实现 | 当前先简化清理，不新增爬虫平台 |
| 生产环境部署 | 仅确保开发环境可用，部署配置后续再做 |
| 用户认证系统重写 | 认证逻辑基本可用，仅修复审计和错误处理 |
| 大规模数据迁移 | 无数据迁移需求，仅清理密钥和配置 |

## v5 Requirements (12 模块联调审核开发)

### 全景图谱模块

- [ ] **HOME-01**: 全景图谱 API 数据流联调 — 验证 graph/* 端点返回正确结构的图谱数据
- [ ] **HOME-02**: 图谱渲染功能验证 — 2D/3D 图谱渲染正常，节点和边数据正确
- [ ] **HOME-03**: 搜索功能前后端联调 — 搜索 API 返回正确结果，前端展示正常
- [ ] **HOME-04**: 前端冒烟测试覆盖 — Home.vue 有渲染测试 + 交互测试

### 岗位列表模块

- [ ] **POS-01**: 岗位列表 API 联调 — 分页/排序/筛选正确
- [ ] **POS-02**: 岗位详情页联调 — 岗位详情数据加载 + 技能图谱渲染
- [ ] **POS-03**: 前端冒烟测试覆盖 — PositionList.vue + PositionDetail.vue

### 数据流水线模块

- [ ] **PIPE-MON-01**: 流水线状态 API 联调 — 运行状态/步骤进度/历史记录
- [ ] **PIPE-MON-02**: SSE 实时事件验证 — 前端接收并展示 SSE 事件
- [ ] **PIPE-MON-03**: 前端冒烟测试覆盖 — PipelineMonitor.vue

### 数据源管理模块

- [ ] **DS-01**: 数据源列表 API 联调 — CRUD 操作正确
- [ ] **DS-02**: 数据源刷新/同步功能验证
- [ ] **DS-03**: 前端冒烟测试覆盖 — DataSources.vue

### 匹配诊断模块

- [ ] **MATCH-01**: 匹配 API 联调 — 匹配评分/技能对比/差距分析正确
- [ ] **MATCH-02**: 前端冒烟测试覆盖 — MatchDiagnosis.vue

### JD 抽取模块

- [ ] **EXTRACT-01**: JD 提交/抽取 API 联调 — 提交→抽取→展示全流程
- [ ] **EXTRACT-02**: 反幻觉检查在前端可见
- [ ] **EXTRACT-03**: 前端冒烟测试覆盖 — ExtractJD.vue

### 闭环演示模块

- [ ] **LOOP-01**: 闭环演示流程联调 — 每个步骤状态更新正确
- [ ] **LOOP-02**: 前端冒烟测试覆盖 — LoopDemo.vue

### 学习中心模块

- [ ] **LEARN-01**: 学习路径 API 联调 — 学习路径/资源推荐正确
- [ ] **LEARN-02**: 前端冒烟测试覆盖 — LearningCenter.vue

### 数据大屏模块

- [ ] **DASH-01**: 大屏数据 API 联调 — 统计数据/图表数据正确
- [ ] **DASH-02**: 前端冒烟测试覆盖 — DataDashboard.vue

### 演化看板模块

- [ ] **EVOL-DASH-01**: 演化数据 API 联调 — 趋势数据/快照数据正确
- [ ] **EVOL-DASH-02**: 前端冒烟测试覆盖 — EvolutionDashboard.vue

### 图谱质量模块

- [ ] **QUAL-01**: 质量数据 API 联调 — 质量指标/评分正确
- [ ] **QUAL-02**: 前端冒烟测试覆盖 — QualityDashboard.vue

### 管理后台模块

- [ ] **ADMIN-01**: 用户管理 API 联调 — CRUD + 权限控制
- [ ] **ADMIN-02**: 审计日志 API 联调 — 日志查询/过滤
- [ ] **ADMIN-03**: 前端冒烟测试覆盖 — Admin.vue + AuditLog.vue + UserManagement.vue

### 跨端一致性强制规范（CONFORM — 必修，Phase 13）

> 来源：多端真实实现 vs `/docs` 规范/契约比对审计。**LOW 级“口径/跨端不一致/契约歧义”默认升级为必修**（见 CONFORM-05），不再仅归档。
> 权威规范文本见 `docs/standards/04-contracts/01-API契约规范.md` **M1–M7**；本表 CONFORM-* 为其在 GSD 需求/追溯层的映射，**单一真相源为 standards M-rules**，本表状态须与之同步，避免双源漂移。

- [x] **CONFORM-01**: 跨后端路径（PostgreSQL / Neo4j）对同一查询参数语义必须一致 — `search` 同时匹配 name+industry；`industry` 过滤统一为包含匹配（ilike/CONTAINS）。*Position 已修并验证（search=互联网→38, industry 部分匹配→33）*
- [x] **CONFORM-02**: 聚合统计字段不得与去重字段同名歧义 — 按域累加等重复计数口径须重命名或显式标注，前端不得裸呈现歧义值。*已由 M6 闭环：`graph_service.total_*`→`independent_*`(395→257)；Home KPI 第 4 卡经 M5 改名 `domainConnections` 并加口径 tooltip，与大屏 edges 去歧义*
- [x] **CONFORM-03**: 公开（非 admin）列表/详情仅返回 `review_status=approved`，且与全景图谱“已发布”口径及 `/positions` 默认契约一致；admin 才可见全状态并带徽标。*Position 已修并验证（非 admin→39 approved）*
- [x] **CONFORM-04**: 无评估基线/无数据时，质量/统计指标须返回“未评估/无数据”语义（`baseline_available`+`explanation`+降级 `warning_level`），禁止红/失败态误导。*Quality 已修并验证（red→gray+解释）*
- [x] **CONFORM-05**: 一致性审计中 LOW 级“口径/跨端不一致/契约歧义”默认升级为必修项，须在对应模块 plan 显式排期或以规范条款固化（本条款即政策落地）。*政策生效*

### 实时中文数据采集与真实呈现（Phase 15 种子 — explore 2026-07-27）

> 取证结论：当前 34/56 岗位为 `system:fixture`，仅一次性英文抓取(remotive/v2ex)，Boss/拉勾/ESCO=0 从未爬，`name_cn` 全空无翻译。设计文档预期中文源(BOSS/拉勾/猎聘)≥500 条且“批+定时”非流式。用户选定路径=**定时+按需 + 英文源翻译**。种子详情 `.planning/phases/15-realtime-cn-datasource/CONTEXT.md`。

- [ ] **DATA-SRC-01**: 中文招聘爬虫可运行并产出数据 — Boss/拉勾/猎聘 至少 1 源端到端跑通（Apify/本地 spider + WAF 降级），`data_sources.total_records>0` 且 `last_crawl_at` 更新。
- [ ] **DATA-SRC-02**: 调度+按需 — `pipeline_schedules` 支持 cron 定期 + 页面按需触发，crawl→extract→import→graph_sync 全链路自动。
- [ ] **DATA-SRC-03**: 抽取实时入库 — 新爬 JD 经抽取自动产生 position/skill 并投影图谱，前端可见新增。
- [ ] **DATA-SRC-04**: 前端真实呈现 — 列表/详情/数据源页可见 `source`/`last_crawl_at`/采集运行状态；空/旧数据诚实提示。
- [ ] **I18N-01**: 英文源自主转中文 — 抽取时对英文 `title`/`industry` 生成 `name_cn`(LLM)，中文源直接映射；前端优先 `name_cn`，无中文打“英文原文”标签。

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| ARCH-02 | Phase 2 | Pending |
| ARCH-05 | Phase 2 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 3 | Pending |
| TEST-05 | Phase 3 | Pending |
| TEST-06 | Phase 3 | Pending |
| ARCH-01 | Phase 4 | Pending |
| PIPE-01 | Phase 4 | Pending |
| PIPE-02 | Phase 4 | Pending |
| PIPE-03 | Phase 4 | Pending |
| PIPE-04 | Phase 5 | Pending |
| PIPE-05 | Phase 5 | Pending |
| ARCH-03 | Phase 5 | Pending |
| MAT-01 | Phase 5 | Pending |
| MAT-02 | Phase 5 | Pending |
| MAT-03 | Phase 5 | Pending |
| EVOL-01 | Phase 6 | Pending |
| EVOL-02 | Phase 6 | Pending |
| EVOL-03 | Phase 6 | Pending |
| EVOL-04 | Phase 6 | Pending |
| EXTR-01 | Phase 7 | Pending |
| EXTR-02 | Phase 7 | Pending |
| EXTR-03 | Phase 7 | Pending |
| ARCH-04 | Phase 8 | Pending |
| TEST-01 | Phase 8 | Pending |
| TEST-02 | Phase 8 | Pending |
| INFRA-04 | Phase 9 | Pending |
| CONFORM-01 | Phase 13 | Fixed (Position) |
| CONFORM-02 | Phase 13 | Fixed (Home, M6+M5) |
| CONFORM-03 | Phase 13 | Fixed (Position) |
| CONFORM-04 | Phase 13 | Fixed (Quality) |
| CONFORM-05 | Phase 13 | Active (policy) |
| DATA-SRC-01 | Phase 15 | Pending (seed) |
| DATA-SRC-02 | Phase 15 | Pending (seed) |
| DATA-SRC-03 | Phase 15 | Pending (seed) |
| DATA-SRC-04 | Phase 15 | Pending (seed) |
| I18N-01 | Phase 15 | Pending (seed) |

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓
- v5 追加需求（CONFORM-01..05 → Phase 13；DATA-SRC-01..04 + I18N-01 → Phase 15 种子）见上表。

---
*Requirements defined: 2026-07-24*
*Last updated: 2026-07-24 after codebase inspection and research*