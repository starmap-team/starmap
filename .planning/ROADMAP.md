# Roadmap: StarMap 全系统重构与质量加固（9 阶段）

**Defined:** 2026-07-24
**Core Value:** 技能匹配与图谱分析的核心链路必须准确、可追溯、可观测

## Phase 1: 基础设施安全加固
**Goal:** 消除直接安全风险，建立安全的开发环境基线
**Mode:** mvp

**Success Criteria:**
1. `secrets/` 已加入 `.gitignore`，已追踪的密钥文件已用 `git rm --cached` 清除
2. 所有暴露的凭证和证书已轮换
3. Docker Compose 生产环境已移除 `NO_PROXY=*`
4. CORS 生产校验失败时明确报错
5. Redis 开发配置添加默认密码

**Requirements:** INFRA-01, INFRA-02, INFRA-03

**Plans:** 2 plans

Plans:
- [ ] 01-01-PLAN.md — Git 安全：secrets/ 加入 .gitignore，清除追踪，轮换证书，更新文档
- [ ] 01-02-PLAN.md — Docker Compose 安全 + CORS 加固：移除 NO_PROXY=*，Redis 密码，严格 CORS 校验

## Phase 2: 异常处理系统重构
**Goal:** 消除 200+ 处裸 `except Exception`，建立结构化异常处理体系
**Mode:** mvp

**Success Criteria:**
1. 所有 `except Exception` 已替换为具体异常类型
2. 关键路径使用 `logger.exception()` 记录完整 traceback
3. 所有业务异常统一使用 StarMapError 子类
4. API 层全局异常处理器统一映射
5. 审计日志覆盖认证和敏感操作路径

**Requirements:** ARCH-02, ARCH-05

## Phase 3: 测试基础设施加固
**Goal:** 补全关键模块的测试覆盖，确保重构安全
**Mode:** mvp

**Success Criteria:**
1. SSE Pipeline（engine.py + steps.py + contracts.py）有单元测试
2. Graph Projector（graph_projector.py）有 PG + Neo4j 集成测试
3. mypy 类型严格度从 `strict=false` 提升到 `disallow_untyped_defs=true`
4. 后端覆盖率从 80.42% 提升到 85%+
5. 所有新增测试在 CI 中通过

**Requirements:** TEST-03, TEST-04, TEST-05, TEST-06

## Phase 4: Pipeline 统一重构
**Goal:** 合并两个 Pipeline 系统，建立统一的可配置 Pipeline 抽象
**Mode:** mvp

**Success Criteria:**
1. `executor.py` 按阶段拆分为独立模块（crawl / dedup / import / graph_sync）
2. `loop_orchestrator.py` 步骤级错误处理升级为具体异常类型 + 结构化日志
3. 死爬虫代码已清理（移除指向 v2ex_remote 的假平台注册）
4. 两个 Pipeline 系统合并为统一抽象，保留 SSE 实时能力
5. 所有现有测试通过，新增端到端 Pipeline 集成测试

**Requirements:** ARCH-01, PIPE-01, PIPE-02, PIPE-03

## Phase 5: 模块边界清晰化
**Goal:** 消除模块职责重叠，明确 core/ 与 services/ 的边界
**Mode:** mvp

**Success Criteria:**
1. SSE Pipeline 步骤契约冻结（PipelineContext 不可变接口 + 单元测试）
2. `match_service.py` 去包装器，直接使用 `core/matching/` 组件
3. 匹配缓存策略文档化（缓存键、TTL、失效策略）
4. `recommendation_service.py` 输入输出类型明确定义
5. Pipeline 端到端集成测试覆盖 crawl→import→graph_sync 全链路

**Requirements:** PIPE-04, PIPE-05, ARCH-03, MAT-01, MAT-02, MAT-03

## Phase 6: 演化引擎重构
**Goal:** 升级演化管道的错误处理、测试覆盖和接口契约
**Mode:** mvp

**Success Criteria:**
1. `orchestrator.py` 错误处理从 `except Exception` 改为 `EvolutionPipelineError` + 具体异常
2. 演化管道 E2E 集成测试覆盖 snapshot→diff→trust→path 全链路
3. DiffEngine / TrustScorer / PathRecommender 接口契约化（明确定义输入输出类型）
4. Snapshot 管理器支持增量快照（避免全量重建）
5. 所有现有测试通过

**Requirements:** EVOL-01, EVOL-02, EVOL-03, EVOL-04

## Phase 7: 技能抽取重构
**Goal:** 重构 LLM 抽取核心模块，消除模块级可变状态，契约化接口
**Mode:** mvp

**Success Criteria:**
1. `normalize.py` 硬编码 SKILL_ALIAS 迁移到 YAML 配置文件
2. 模块级可变状态（SKILL_ALIAS / _REVERSE_INDEX）封装为类或工厂函数
3. LLM 客户端接口契约化（定义 Provider 协议，每个供应商为独立实现）
4. 反幻觉检查器从 `jd_extract.py` 提取为独立模块，可单独测试
5. 所有现有测试通过

**Requirements:** EXTR-01, EXTR-02, EXTR-03

## Phase 8: 前端测试覆盖
**Goal:** 修复 vitest 覆盖率配置，补全前端页面级测试
**Mode:** mvp

**Success Criteria:**
1. Vitest 覆盖率配置包含源码文件（而非仅测试文件自身）
2. 18 个页面各有至少一个冒烟测试（渲染 + 基本交互）
3. 密钥安全 — secrets/ 从 Git 移除，凭证轮换完成
4. 前端 CI 中 vue-tsc 0 errors + vitest 通过

**Requirements:** ARCH-04, TEST-01, TEST-02

## Phase 9: 文档与最终验证
**Goal:** 同步所有文档，全链路验证重构质量
**Mode:** mvp

**Success Criteria:**
1. AGENTS.md / 架构文档 / 部署文档与实际代码一致
2. 全链路验证：pipeline → 抽取 → 图谱 → 匹配 → 演化 均通过
3. pytest 全部通过，覆盖率 ≥ 85%
4. vitest 全部通过，覆盖率 ≥ 60%（含源码）
5. 所有 CRITICAL/HIGH 安全发现已修复

**Requirements:** INFRA-04

---

## Dependency Graph

```
Phase 1 (安全)     → 独立，无依赖
Phase 2 (异常处理)  → 独立，可并行于 Phase 1
Phase 3 (测试)      → 依赖 Phase 1（安全环境）
Phase 4 (Pipeline)  → 依赖 Phase 2（异常处理）+ Phase 3（测试）
Phase 5 (模块边界)  → 依赖 Phase 4（Pipeline 统一）
Phase 6 (演化)      → 依赖 Phase 3（测试）
Phase 7 (抽取)      → 依赖 Phase 3（测试）
Phase 8 (前端测试)  → 独立，可并行于 Phase 3-7
Phase 9 (验证)      → 依赖以上所有
```

**并行执行策略:**
- Phase 1 + Phase 2 + Phase 8 可并行启动
- Phase 3 在 Phase 1 完成后启动
- Phase 4 + Phase 6 + Phase 7 在 Phase 3 完成后并行启动
- Phase 5 在 Phase 4 完成后启动
- Phase 9 在所有阶段完成后启动

---

**Coverage:**
- Total phases: 9
- Total requirements: 30
- All requirements mapped: ✓

---
*Last updated: 2026-07-24 after codebase inspection and research*

---

# Roadmap: StarMap v5.0 — 12 模块联调审核开发

**Defined:** 2026-07-25
**Core Value:** 每个前端导航模块都可独立验证、前后端数据一致、无功能回归

**背景:** v4.0 完成了全系统重构与质量加固，本里程碑对每个导航模块进行全链路联调验证。

## Phase 1: 全景图谱模块 (Home)
**Goal:** 对全景图谱模块进行全链路分析→设计→联调→闭环
**Mode:** mvp
**Success Criteria:**
1. 前端源码缺陷分析完成（图谱渲染、搜索、交互逻辑）
2. 后端 API 缺陷分析完成（graph/* 端点、数据查询性能）
3. 用户优化点调研（图谱交互体验、搜索响应、加载性能）
4. 需求优化方案设计（基于分析结果产出改进设计）
5. 后端 API（/api/v1/graph/*）返回正确结构的数据
6. 前端图谱渲染（2D/3D）正常，节点和边数据正确
7. 搜索功能前后端联调通过
8. 所有现有测试通过
9. 业务闭环确认：图谱数据从 DB → API → 前端渲染 → 用户交互 全链路可追溯
**Plans:** 1 plan

## Phase 2: 岗位列表模块 (PositionList + PositionDetail)
**Goal:** 验证岗位列表和详情页的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 岗位列表 API 返回正确的分页数据
2. 岗位详情页数据加载正常
3. 技能图谱在岗位详情中正确渲染
4. 所有现有测试通过
**Plans:** 1 plan

Plans:
- [ ] 02-01-PLAN.md — 源码缺陷分析 + 优化设计 + 联调修复 + 测试增强

## Phase 3: 数据流水线模块 (PipelineMonitor)
**Goal:** 验证数据流水线监控页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 流水线状态 API 返回正确的运行状态
2. SSE 实时事件推送正常工作
3. 流水线历史记录显示正常
4. 所有现有测试通过
**Plans:** 1 plan

Plans:
- [ ] 03-01-PLAN.md — 源码缺陷分析 + 优化设计 + 联调修复 + 测试增强

**Requirements:** PIPE-MON-01, PIPE-MON-02, PIPE-MON-03

## Phase 4: 数据源管理模块 (DataSources)
**Goal:** 验证数据源管理页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 数据源列表 API 返回正确数据
2. 数据源刷新/同步功能正常
3. 所有现有测试通过
**Plans:** 1 plan

## Phase 5: 匹配诊断模块 (MatchDiagnosis)
**Goal:** 验证匹配诊断页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 匹配 API 返回正确的匹配评分
2. 技能对比可视化正常
3. 差距分析数据显示正常
4. 所有现有测试通过
**Plans:** 1 plan

## Phase 6: JD 抽取模块 (ExtractJD)
**Goal:** 验证 JD 抽取页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. JD 提交 API 正常处理
2. 抽取结果在前端正确展示
3. 反幻觉检查在前端可见
4. 所有现有测试通过
**Plans:** 1 plan

## Phase 7: 闭环演示模块 (LoopDemo)
**Goal:** 验证闭环演示页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 闭环演示流程完整走通
2. 每个步骤的状态更新正确
3. 所有现有测试通过
**Plans:** 1 plan

## Phase 8: 学习中心模块 (LearningCenter)
**Goal:** 验证学习中心页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 学习路径 API 返回正确数据
2. 学习资源推荐显示正常
3. 所有现有测试通过
**Plans:** 1 plan

## Phase 9: 数据大屏模块 (DataDashboard)
**Goal:** 验证数据大屏页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 大屏数据 API 返回正确统计数据
2. 图表渲染正常
3. 所有现有测试通过
**Plans:** 1 plan

## Phase 10: 演化看板模块 (EvolutionDashboard)
**Goal:** 验证演化看板页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 演化数据 API 返回正确趋势数据
2. 演化趋势图渲染正常
3. 所有现有测试通过
**Plans:** 1 plan

## Phase 11: 图谱质量模块 (QualityDashboard)
**Goal:** 验证图谱质量页面的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 质量数据 API 返回正确指标
2. 质量评分和统计图表正常
3. 所有现有测试通过
**Plans:** 1 plan

## Phase 12: 管理后台模块 (Admin + AuditLog + UserManagement)
**Goal:** 验证管理后台的前后端联调
**Mode:** mvp
**Success Criteria:**
1. 用户管理 API 正常
2. 审计日志 API 返回正确数据
3. 管理员权限控制正确
4. 所有现有测试通过
**Plans:** 1 plan

## Dependency Graph

```
Wave 1 (数据组): Phase 1-4 — 独立，可并行或顺序执行
Wave 2 (工具组): Phase 5-8 — 独立，可并行或顺序执行
Wave 3 (洞察组): Phase 9-11 — 独立，可并行或顺序执行
Wave 4 (系统组): Phase 12 — 独立执行
```

**并行执行策略:**
- 每个 Wave 内的模块可并行执行
- 各 Wave 之间无依赖，可全部并行
- 建议按 Wave 顺序执行以减少上下文切换

---

**Coverage:**
- Total phases: 12
- Total requirements: 24 (12 modules × 2 requirements: 联调测试 + 代码审核)
- All requirements mapped: ✓

---
*Last updated: 2026-07-25 after v5.0 milestone initialization*