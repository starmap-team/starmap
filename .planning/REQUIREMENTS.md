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

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-24*
*Last updated: 2026-07-24 after codebase inspection and research*