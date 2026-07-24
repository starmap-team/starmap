# StarMap — 人才能力星云导航系统（全系统重构与质量加固）

**Last reviewed:** 2026-07-24
**Status:** Active development — 重构与质量加固

## What This Is

StarMap（星图）是一个面向 IT 岗位的技能图谱与匹配诊断平台。系统通过爬取和分析 JD（岗位描述），利用 LLM 抽取技能、构建知识图谱，为求职者提供技能匹配、差距分析、学习路径推荐和岗位演化趋势视图。

当前项目处于 v2.1～v3.0 过渡阶段，代码库存在大量技术债务：双 Pipeline 系统并存、200+ 处 `except Exception` 静默吞错误、密钥文件被 Git 追踪、模块边界模糊、测试覆盖率虚高、前端无页面级测试。本次重构使命是**以核心业务逻辑为优先，系统性消除技术债务，建立可维护、可测试、可演进的工程架构**。

## Core Value

技能匹配与图谱分析的核心链路必须准确、可追溯、可观测。一切重构围绕这条链路展开，确保每一步都有明确的契约、充分的测试和可观测的日志。

## Requirements

### Validated（已有能力，来自现有代码）

- ✓ **JD 文本 LLM 抽取** — 多供应商 LLM 客户端（MiMo → DeepSeek → 星火 → Qwen），带 PII 脱敏、JSON 校验、反幻觉检查
- ✓ **技能标准化** — 别名映射 + 向量相似度 + 来源数验证的三步管道
- ✓ **图数据库查询** — Neo4j 查询封装（position/skill/domain 可视化、匹配查询）
- ✓ **PG→Neo4j 投影** — canonical_id 贯通的同步投影服务（graph_projector.py）
- ✓ **多维度匹配评分** — 模块化匹配引擎（scorer + path_builder + cache）
- ✓ **演化管道** — 8 步快照→差异→信任评分→路径推荐
- ✓ **5 阶段 DAG 流水线** — crawl → dedup ∥ clean → import → graph_sync → timeseries
- ✓ **SSE 实时事件推送** — 基于 Redis pub/sub 的 SSE 广播
- ✓ **JWT 认证** — Bearer token + 匿名 dev bypass + admin 角色
- ✓ **统一错误码** — StarMapError 基类 + 全局异常处理器
- ✓ **24 张 PostgreSQL 表** — 已迁移、Alembic 管理
- ✓ **前端 14 页面** — Vue 3 + Element Plus + ECharts + G6 图谱
- ✓ **API 契约** — starmap-contracts/openapi.yaml 为单一真相源
- ✓ **pytest 1726 通过** — 后端 80.42% 覆盖率
- ✓ **vitest 226 通过** — 前端测试通过，但覆盖率计算有误

### Active（本次重构目标）

#### 核心架构

- [ ] **ARCH-01**: Pipeline 双系统合一 — 消除 `backend/app/core/pipeline/` 与 `backend/app/sse_pipeline/` 的重叠，建立统一的 Pipeline 抽象
- [ ] **ARCH-02**: 消除裸 `except Exception` — 将 200+ 处替换为具体异常类型，关键路径使用 `logger.exception()` 记录完整追踪
- [ ] **ARCH-03**: 模块边界清晰化 — 明确 core/ 与 services/ 的职责边界，消除职责重叠（如 match_service.py 是 core/matching/ 的包装器）
- [ ] **ARCH-04**: 密钥安全 — secrets/ 从 Git 移除，凭证轮换，迁移到 .env 或密钥管理器
- [ ] **ARCH-05**: 统一错误处理契约 — 所有业务异常统一使用 StarMapError 子类，API 层统一映射

#### 数据管道（Pipeline）

- [ ] **PIPE-01**: executor.py（1138 行）按阶段拆分为独立模块（crawl / dedup / import / graph_sync）
- [ ] **PIPE-02**: loop_orchestrator.py（924 行）步骤级错误处理从 `except Exception` 改为具体异常类型，引入结构化日志
- [ ] **PIPE-03**: 死爬虫清理 — 移除指向 v2ex_remote 的假平台注册，保留单一爬虫路径或修复 Playwright 爬虫
- [ ] **PIPE-04**: SSE Pipeline 步骤契约冻结 — 为 PipelineContext 定义不可变接口，添加单元测试后合并
- [ ] **PIPE-05**: Pipeline 端到端集成测试 — 覆盖 crawl→import→graph_sync 全链路

#### 演化引擎（Evolution）

- [ ] **EVOL-01**: orchestrator.py 错误处理升级 — 从 `except Exception` 改为 `EvolutionPipelineError` + 具体异常
- [ ] **EVOL-02**: 演化管道 E2E 集成测试 — 覆盖 snapshot→diff→trust→path 全链路
- [ ] **EVOL-03**: DiffEngine / TrustScorer / PathRecommender 接口契约化 — 明确定义输入输出类型
- [ ] **EVOL-04**: Snapshot 管理器增量快照支持 — 避免全量重建

#### 技能抽取（Extraction）

- [ ] **EXTR-01**: normalize.py 硬编码 SKILL_ALIAS 迁移到 YAML — 移除模块级可变状态，封装为类或工厂函数
- [ ] **EXTR-02**: LLM 客户端接口契约化 — 定义 Provider 协议，每个供应商为独立实现
- [ ] **EXTR-03**: 反幻觉检查器独立化 — 从 jd_extract.py 中提取为独立模块，可单独测试

#### 匹配推荐（Matching & Recommendation）

- [ ] **MAT-01**: match_service.py 去包装器 — 删除向后兼容层，直接使用 core/matching/ 组件
- [ ] **MAT-02**: 匹配缓存策略明确化 — 缓存键、TTL、失效策略文档化
- [ ] **MAT-03**: 推荐服务接口契约化 — recommendation_service.py 输入输出类型明确定义

#### 测试质量

- [ ] **TEST-01**: 前端覆盖率修复 — vitest 配置包含源码文件，而非仅测试文件自身
- [ ] **TEST-02**: 前端页面级测试 — 为 18 个页面添加至少冒烟测试（渲染 + 基本交互）
- [ ] **TEST-03**: SSE Pipeline 测试 — 为 engine.py + steps.py + contracts.py 添加单元测试
- [ ] **TEST-04**: Graph Projector 测试 — 为 graph_projector.py 添加集成测试（PG + Neo4j）
- [ ] **TEST-05**: mypy 类型严格度逐步提升 — 从 `strict=false` 向 `strict=true` 过渡
- [ ] **TEST-06**: 后端覆盖率目标 85%+ — 从当前 80.42% 提升

#### 基础设施

- [ ] **INFRA-01**: Git 安全 — secrets/ 加入 .gitignore，清除已追踪的密钥文件，轮换凭据
- [ ] **INFRA-02**: Docker Compose 安全 — 生产环境移除 `NO_PROXY=*`，Redis 添加默认密码
- [ ] **INFRA-03**: CORS 生产加固 — 生产环境 CORS 校验失败时明确报错而非仅警告
- [ ] **INFRA-04**: 文档更新 — 同步 AGENTS.md / 架构文档 / 部署文档，确保与实际代码一致

### Out of Scope

| 项目 | 原因 |
|------|------|
| 新功能开发 | 本次为重构与质量加固，不新增业务功能 |
| 前端 UI 重设计 | 仅做接口对齐和测试覆盖，不涉及视觉重设计 |
| 多爬虫平台实现 | 当前先简化清理，不新增爬虫平台 |
| 生产环境部署 | 仅确保开发环境可用，部署配置后续再做 |
| 用户认证系统重写 | 认证逻辑基本可用，仅修复审计和错误处理 |
| 大规模数据迁移 | 无数据迁移需求，仅清理密钥和配置 |

## Context

### 当前技术债务全景

基于代码库地图（2026-07-24）和实际代码检查：

1. **Pipeline 双重系统** — `backend/app/core/pipeline/`（Celery DAG 驱动）和 `backend/app/sse_pipeline/`（SSE 实时驱动）功能重叠，前者被删除的文件（git status 显示 D）表明正在迁移但未完成
2. **200+ bare `except Exception`** — 散布在 executor.py、loop_orchestrator.py、auth_service.py、所有 API 路由中，严重阻碍调试
3. **密钥泄露** — `secrets/` 目录包含 .pem/.key/.pfx 等敏感文件，已被 Git 追踪
4. **模块边界模糊** — `backend/app/services/` 中的 match_service.py 是 core/matching/ 的包装器，auth_service.py（872 行）混合密码/令牌/用户管理/管理员操作
5. **测试覆盖率虚高** — vitest 覆盖配置仅统计测试文件本身，源码覆盖率实际远低于报告值
6. **前端 0 页面级测试** — 18 个页面、47 个组件仅有 6 个组件测试
7. **SSE Pipeline 无测试** — 新模块 engine.py + steps.py 无任何测试覆盖
8. **Graph Projector 无测试** — 关键 PG→Neo4j 同步桥无测试
9. **模块级可变状态** — normalize.py 的 SKILL_ALIAS 在 import 时被修改
10. **同步 I/O 阻塞事件循环** — judge_service.py 在 async 路径中使用同步文件 I/O
11. **LLM 成本追踪器不准确** — 内存累加器，多 worker 下各自独立计数
12. **死爬虫代码** — 三个平台都指向 v2ex_remote，平台区分无意义
13. **CORS 默认过于宽松** — 多个 localhost 端口在默认配置中
14. **Docker Compose 安全配置** — 生产环境 `NO_PROXY=*` 绕过代理

### 代码规模

| 模块 | 文件数 | 关键文件 |
|------|--------|----------|
| API 路由 | 28 个 | `api/v1/` 路由模块 |
| 服务层 | 19 个 | `services/` 业务逻辑 |
| 核心引擎 | 30+ 个 | `core/` 领域逻辑 |
| SSE Pipeline | 4 个 | 新实时管道 |
| 前端页面 | 15 个 | `pages/` 页面组件 |
| 前端 Store | 24 个 | Pinia 状态管理 |
| 前端组件 | 40+ 个 | 共享 UI 组件 |
| 测试 | 数百个 | pytest 1726 / vitest 226 |

## Constraints

- **技术栈锁定**: Python 3.11-3.12 / FastAPI / Vue 3 / TypeScript 5.4 — 不改语言/框架
- **契约优先**: API 变更先改 `starmap-contracts/openapi.yaml`，再 `npm run gen:api` 同步前端
- **图/业务分离**: Neo4j 查询在 `services/`，抽取/演化在 `core/`，不引入框架耦合
- **向后兼容**: 重构过程中保持现有 API 签名不变（追加字段允许，不删不改类型）
- **增量重构**: 不一次性重写，每次提交保持可运行状态
- **测试先行**: 先写测试暴露问题，再重构，确保回归不降级

## Key Decisions

| 决策 | 理由 | 状态 |
|------|------|------|
| 核心业务逻辑优先重构 | Pipeline + Evolution + Extraction + Matching 是系统核心价值所在 | ✓ 已确定 |
| 先测试后重构 | 现有测试覆盖率不足以安全重构，先补测试再改代码 | ✓ 已确定 |
| Pipeline 整合为统一抽象 | 消除双系统维护成本，保留 SSE 实时能力 | — Pending |
| YAGNI 原则 | 不引入新抽象/新框架，仅修复现有问题 | ✓ 已确定 |
| 增量式模块拆分 | 大文件（executor.py 1138 行）先按阶段拆分，不一次重写 | ✓ 已确定 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-24 after full codebase inspection and real code analysis*