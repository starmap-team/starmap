# StarMap 前后端联调测试计划

> **版本**: v2.0 — 真实后端联调（非 MSW mock）
> **制定日期**: 2026-07-08
> **目标**: 端到端联调覆盖率在前端组件和后端数据功能上 ≥ 90%
> **策略**: 视觉观测 + 后端数据比对 + 用户交互验证 + 问题记录 → 统一修复
> **环境**: Docker Compose dev（8 服务），Chrome，Vite dev server 直连 FastAPI

---

## 0. 联调测试矩阵总览

### 前端页面 × 后端 API × Store 映射

| # | 页面 | 路由 | Store | 后端 API 端点数 | 优先级 |
|---|------|------|-------|----------------|--------|
| 1 | 全景图谱 | `/` | graph | 4 | P0 |
| 2 | 岗位列表 | `/positions` | jd | 3 | P0 |
| 3 | 岗位详情 | `/position/:name` | jd | 2 | P0 |
| 4 | 匹配诊断 | `/match` | user+resume+match | 5 | P0 |
| 5 | JD 抽取 | `/extract` | jd | 1 | P0 |
| 6 | 演化看板 | `/evolution` | evolution | 3 | P1 |
| 7 | 图谱质量 | `/quality` | quality | 3 | P1 |
| 8 | 数据流水线 | `/pipeline` | pipeline | 16 | P1 |
| 9 | 数据源管理 | `/datasources` | datasource | 5 | P1 |
| 10 | 管理后台 | `/admin` | datasource(审核) | 16 | P2 |
| 11 | 学习中心 | `/learning` | learning | 9 | P1 |
| 12 | 求职者分析 | `/analysis` | jobseeker | 1(SSE) | P2 |
| 13 | 闭环演示 | `/loop` | loop | 3 | P2 |
| 14 | 数据大屏 | `/dashboard` | dashboard | 6 | P2 |

**合计**: 14 页面, 77 个 API 端点调用

### 覆盖率计算

- **前端组件覆盖**: 14 页面 + 38 业务组件 = 52 项
- **后端数据功能覆盖**: 77 个 API 调用 + 数据字段比对
- **目标**: 各维度 ≥ 90%

---

## Phase 1: 服务健康 & 基础设施（前置条件）

### TC-1.1 服务启动验证

| 用例 ID | 检查项 | 预期结果 | 验证方式 |
|---------|--------|---------|---------|
| TC-1.1.1 | Docker 8 容器全部 Up | backend/celery/frontend/postgres/neo4j/redis/chroma/ollama | `docker compose ps` |
| TC-1.1.2 | `GET /health` | `{postgres:ok, neo4j:ok, redis:ok}` | HTTP 请求 |
| TC-1.1.3 | 前端 5173 可访问 | HTTP 200 | 浏览器导航 |
| TC-1.1.4 | Neo4j 有数据 | 非空图数据 | `GET /graph/overview` |
| TC-1.1.5 | PostgreSQL 有数据 | positions 表有记录 | `GET /positions` |
| TC-1.1.6 | Alembic 迁移最新 | `alembic current` = head | 命令行 |

### TC-1.2 跨域 & 认证

| 用例 ID | 检查项 | 预期结果 | 验证方式 |
|---------|--------|---------|---------|
| TC-1.2.1 | Vite proxy 转发 | 前端请求 `/api/v1/*` 到后端无 CORS 错误 | 浏览器 Network |
| TC-1.2.2 | 认证依赖 | `get_current_user` 要求 token；未认证返回 401 | HTTP 请求 |
| TC-1.2.3 | 安全响应头 | X-Content-Type-Options, X-Frame-Options 存在 | HTTP 响应头 |

---

## Phase 2: 核心页面联调（P0 — 100% 必须通过）

### TC-2.1 全景图谱页 `/`

**前端组件**: Home.vue, Graph2D/3D.vue, HomeKpiStrip.vue, HomeGraphControls.vue, HomeEvolutionDrawer.vue, GraphSearchBar.vue, GraphToolbar.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-2.1.1 | 页面加载 | 访问 `/` | 首页渲染，KPI 条显示节点/边/岗位/技能数量 | `GET /graph/overview` 返回 domains+connections；KPI 值与 `GET /dashboard/overview` 一致 |
| TC-2.1.2 | 领域概览层 | 默认 domain 层 | 显示 KnowledgeArea 岛屿节点，颜色区分 | domains 数组与后端返回一致；position_count/skill_count 字段正确 |
| TC-2.1.3 | 展开岗位层 | 点击某 KA 节点 | 展开该 KA 下 Position 节点 | `GET /graph/ka/{id}/positions` 返回正确 positions；visibleNodes 包含 KA+Positions |
| TC-2.1.4 | 展开技能层 | 点击某 Position 节点 | 展开该 Position 下 Skill 节点 + REQUIRES 边 | `GET /graph/position/{name}/skills` 返回 skills+edges；雷达图渲染 |
| TC-2.1.5 | 概览模式切换 | 切换 domain/tech_stack/level | 节点重新分组渲染 | `GET /graph/overview?group_by={mode}` 返回对应分组数据 |
| TC-2.1.6 | 演化路径叠加 | 开启演化路径开关 | EVOLVES_TO 边显示 | `GET /evolution/paths/all` 返回路径数据；trend/similarity 正确 |
| TC-2.1.7 | 岗位聚焦演化 | 点击某岗位查看演化 | 上下游演化路径高亮 | `GET /evolution/paths/{name}` 返回聚焦路径 |
| TC-2.1.8 | 节点搜索 | 搜索框输入 "Python" | 匹配节点高亮/居中 | 搜索结果与后端节点名称一致 |
| TC-2.1.9 | 3D 视图切换 | 切换 2D/3D | 3D 球体渲染，可旋转缩放 | 节点数据源相同，仅渲染引擎不同 |

**数据比对要点**:
- `domains[].position_count` 与 Neo4j 实际 Position 数量一致
- `domains[].skill_count` 与 Neo4j 实际 Skill 数量一致
- `connections[].weight` 与 Neo4j 关系属性一致
- 演化边 `similarity` ∈ [0,1], `trend` ∈ {rising,stable,declining}

### TC-2.2 岗位列表页 `/positions`

**前端组件**: PositionList.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-2.2.1 | 列表加载 | 访问 `/positions` | 表格渲染，列含岗位名/行业/描述等 | `GET /positions?page=1&page_size=100` 返回 items 分页结构 |
| TC-2.2.2 | 搜索过滤 | 搜索框输入 "Python" | 表格过滤显示匹配岗位 | `GET /positions?search=Python` 返回过滤结果 |
| TC-2.2.3 | 分页 | 切换页码 | 表格数据更新 | `GET /positions?page=2` 返回第二页数据 |
| TC-2.2.4 | 点击岗位 | 点击某行 | 跳转到 `/position/{name}` | 路由参数 name 与后端 position_id/name 一致 |

**数据比对要点**:
- 前端显示的岗位总数与后端 `items.length` 一致
- 分页 total 与后端返回的 total 一致
- 搜索结果与后端 `search` 参数过滤一致

### TC-2.3 岗位详情页 `/position/:name`

**前端组件**: PositionDetail.vue, SkillRadar.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-2.3.1 | 详情加载 | 从列表点击进入 | 岗位名称+技能雷达图+技能表格 | `GET /graph/position/{name}/skills` 返回 skills+edges；或 fallback `GET /positions/{name}` |
| TC-2.3.2 | 雷达图渲染 | 查看雷达图 | 各技能维度按 proficiency 绘制 | required_skills 和 bonus_skills 数量与后端一致 |
| TC-2.3.3 | 技能表格 | 查看技能列表 | 每行含技能名/类别/熟练度/置信度/热度 | 每个字段的值与后端返回的 SkillNode 一致 |
| TC-2.3.4 | 无效岗位名 | 访问 `/position/nonexist` | 错误提示或空状态 | 后端返回 404，前端显示友好提示 |

**数据比对要点**:
- 雷达图维度数量 = `skills.length`
- 每个技能的 `proficiency` 映射正确（了解=1, 熟悉=2, 精通=3）
- `importance` 字段正确区分 required/bonus

### TC-2.4 匹配诊断页 `/match`

**前端组件**: MatchDiagnosis.vue, ResumeUpload.vue, PositionSearch.vue, SkillRadar.vue, GapAnalysisReport.vue, SkillMatchAnimation.vue, MatchBatchMode.vue, CompetitivenessChart.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-2.4.1 | 上传简历 | 拖拽 PDF 到上传区 | 文件名显示 | 文件发送到 `POST /resume/upload` |
| TC-2.4.2 | 简历解析 | 点击"开始上传解析" | loading → 解析成功 → 技能 tag 列表 | `POST /resume/upload` 返回 required_skills + normalized_skills |
| TC-2.4.3 | 手动输入技能 | 点"跳过上传，手动输入" | 输入框出现，输入"Python"+回车 → tag 出现 | 技能名记录在 store 中 |
| TC-2.4.4 | 确认技能 | 输入 ≥1 技能后点确认 | 进入 Step 1 岗位选择 | N ≥ 1 时按钮可用 |
| TC-2.4.5 | 搜索岗位 | 下拉框搜索 | 远程搜索结果加载 | `GET /positions?search=xxx` 返回匹配岗位 |
| TC-2.4.6 | 选择岗位 | 选择某岗位 | 进入 Step 2，雷达图渲染 | `GET /graph/position/{name}/skills` 返回岗位技能 |
| TC-2.4.7 | 雷达图对比 | Step 2 查看 | 两个多边形叠加(个人 vs 岗位) | 个人技能 proficiency 映射正确 |
| TC-2.4.8 | 执行匹配 | 点"开始智能诊断" | loading → 进入 Step 3 | `POST /match/position` 发送 person_skills + target_position |
| TC-2.4.9 | 差距报告 | Step 3 查看 | match_score 仪表盘 + 三列技能卡 + 技能表 | match_score ∈ [0,100]；matched_skills/gap_skills 与后端一致 |
| TC-2.4.10 | 学习路径 | 点"查看学习路径规划" | Step 4 时间线/DAG 渲染 | learning_path 内容与后端返回一致 |
| TC-2.4.11 | 重新诊断 | 点"重新诊断" | 回到 Step 0，状态重置 | store 清空 |
| TC-2.4.12 | 返回上一步 | 各步骤点"返回" | 回退到上一步 | 之前数据保留 |
| TC-2.4.13 | 匹配历史 | 查看历史列表 | 显示过去匹配记录 | `GET /match/history?limit=10` 返回 items |
| TC-2.4.14 | 批量匹配 | 切换到批量模式 | 多条匹配结果表格 | `POST /match/batch` 返回 results |

**数据比对要点**:
- `match_score` 前端显示值 = 后端返回值（精度一致）
- `matched_skills` 前端高亮技能 = 后端返回数组
- `gap_skills` 前端缺失技能 = 后端返回数组
- `skill_gap_detail` 每项 gap_level ∈ {完全缺失,部分掌握,已掌握}
- `recommendations` 内容与后端一致
- `radar_data` 各技能 required/matched 数值匹配

### TC-2.5 JD 抽取页 `/extract`

**前端组件**: ExtractJD.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-2.5.1 | 标准抽取 | 输入 JD 文本，点"抽取" | loading → 结果表显示 | `POST /extract/jd` 返回 position_name + skills |
| TC-2.5.2 | 技能分类 | 查看抽取结果 | hard_skill/soft_skill 分类正确 | 后端 category 字段正确 |
| TC-2.5.3 | 归一化 | 查看归一化结果 | original → normalized 映射 | normalized_skills 含 method/confidence |
| TC-2.5.4 | 信任度 | 查看置信度 | confidence 值显示 | confidence ∈ [0,1] |
| TC-2.5.5 | 幻觉评分 | 查看幻觉评分 | hallucination_score 显示 | hallucination_score ∈ [0,1] |
| TC-2.5.6 | 空输入 | 不输入文本点抽取 | 422 错误提示 | 后端返回 422 |
| TC-2.5.7 | 复杂 JD | 输入多技能长 JD | 7+ 技能抽取，含分类 | 后端返回完整 skills 数组 |

---

## Phase 3: 重要页面联调（P1 — ≥90% 通过）

### TC-3.1 演化看板页 `/evolution`

**前端组件**: EvolutionDashboard.vue, EvolutionChangelogDrawer.vue, CareerPathGraph.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-3.1.1 | 趋势加载 | 访问 `/evolution` | CII 时序曲线 + 趋势表格 | `GET /evolution/trends` 返回 items[] |
| TC-3.1.2 | 快照列表 | 查看快照区 | 快照时间线渲染 | `GET /evolution/snapshots` 返回 SnapshotEntry[] |
| TC-3.1.3 | 变更记录 | 点击某技能查看变更 | 抽屉打开，变更列表 | `GET /evolution/changelog/{name}` 返回 ChangelogEntry[] |
| TC-3.1.4 | 新兴技能 | 查看新兴技能区 | 上升技能卡片/列表 | `GET /evolution/emerging-skills` 或 trends 中 trend=rising |
| TC-3.1.5 | CII 仪表盘 | 查看 CII 指标 | 仪表盘渲染 | CII 值 ∈ [0,1] |

**数据比对要点**:
- `trendItems[].confidence` ∈ [0,1]
- `snapshots[].snapshot_date` 日期格式一致
- `changelog[].change_type` ∈ {added,modified,removed}

### TC-3.2 图谱质量页 `/quality`

**前端组件**: QualityDashboard.vue, QualityTrendChart.vue, AlertList.vue, ReviewQueuePanel.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-3.2.1 | KPI 加载 | 访问 `/quality` | 4 个 KPI 卡渲染 | `GET /quality/dashboard` 返回 total_nodes/avg_trust_score/hallucination_rate/pending_review |
| TC-3.2.2 | 信任度分布 | 查看直方图 | 分布柱状图渲染 | trust_distribution 数据完整 |
| TC-3.2.3 | 幻觉率趋势 | 查看趋势图 | 趋势折线图 | `GET /quality/trends` 返回 data_points[] |
| TC-3.2.4 | 数据源饼图 | 查看饼图 | 各数据源占比 | source_distribution 数据完整 |
| TC-3.2.5 | 质量告警 | 查看告警 Tab | 告警列表 | `GET /quality/alerts` 返回 alerts[] |
| TC-3.2.6 | 审核队列 | 查看审核 Tab | 待审核项列表 | `GET /admin/review-queue` 返回 items[] |
| TC-3.2.7 | 审核操作 | 点"通过"/"拒绝" | 行消失 | `POST /admin/audit/{id}/approve` 或 reject 成功 |
| TC-3.2.8 | 周期切换 | 切换 7d/30d/90d | 趋势图更新 | `GET /quality/trends?period=30d` |

**数据比对要点**:
- KPI 卡片值 = 后端返回字段值（精确匹配）
- trust_distribution 各 range 的 count 合计 = total_nodes
- hallucination_trend 的 rate ∈ [0,1]
- alerts 的 severity 正确映射

### TC-3.3 数据流水线页 `/pipeline`

**前端组件**: PipelineMonitor.vue, PipelineDag.vue, PipelineStageCard.vue, PipelineSourcePanel.vue, PipelineQualityPanel.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-3.3.1 | 状态加载 | 访问 `/pipeline` | DAG 时间线 + 状态面板 | `GET /pipeline/status` 返回 PipelineStatus |
| TC-3.3.2 | 运行记录 | 查看运行列表 | 历史运行表格 | `GET /pipeline/runs` 返回 PipelineRun[] |
| TC-3.3.3 | 触发全量 | 点"全量运行" | 触发成功，SSE 进度 | `POST /pipeline/trigger` 返回成功 |
| TC-3.3.4 | SSE 实时 | 观察进度 | 阶段进度实时更新 | SSE 事件推送 stage/status/progress |
| TC-3.3.5 | 阶段重试 | 点某失败阶段"重试" | 阶段重新运行 | `POST /pipeline/runs/{id}/retry` |
| TC-3.3.6 | 断点续跑 | 点"续跑" | 从断点继续 | `POST /pipeline/runs/{id}/resume` |
| TC-3.3.7 | 取消运行 | 点"取消" | 运行中断 | `POST /pipeline/runs/{id}/cancel` |
| TC-3.3.8 | 数据质量 | 查看质量面板 | 评分+告警 | `GET /pipeline/data-quality` |
| TC-3.3.9 | 调度管理 | 查看/创建/启停调度 | 调度列表 CRUD | `GET/POST/PUT/DELETE /pipeline/schedules` |
| TC-3.3.10 | 配置管理 | 查看配置弹窗 | 超时/并发/重试参数 | `GET/PUT /pipeline/config` |

**数据比对要点**:
- `PipelineStatus.is_running` 与 UI 运行状态一致
- `PipelineRun.stages[].status` ∈ {pending,running,completed,failed,skipped,cancelled}
- `DataQualityMetrics.overall_score` ∈ [0,100]
- SSE 事件的 progress ∈ [0,100]

### TC-3.4 数据源管理页 `/datasources`

**前端组件**: DataSources.vue, DataSourceCard.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-3.4.1 | 数据源列表 | 访问 `/datasources` | 5 个数据源卡片(BOSS/拉勾/51Job/GitHub/ESCO) | `GET /datasources` 返回 5 条 |
| TC-3.4.2 | 数据源详情 | 点击某数据源 | 详情面板 | `GET /datasources/{id}` |
| TC-3.4.3 | 配置更新 | 修改配置保存 | 更新成功 | `PUT /datasources/{id}` |
| TC-3.4.4 | 触发同步 | 点"同步" | 同步进度 | `POST /datasources/{id}/sync` |
| TC-3.4.5 | 统计数据 | 查看统计图 | 日/周/月采集量 | `GET /datasources/{id}/stats` |

### TC-3.5 学习中心页 `/learning`

**前端组件**: LearningCenter.vue, LearningPathPlan.vue, LearningPathFlow.vue, SkillProgressCard.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-3.5.1 | 计划加载 | 访问 `/learning` | 从 localStorage 恢复计划 或空状态 | `GET /learning/plan/{id}` 或 无 |
| TC-3.5.2 | 创建计划 | 从匹配结果创建 | 学习计划 DAG 渲染 | `POST /learning/plan` 返回 plan_id + skills + path |
| TC-3.5.3 | 技能进度 | 点某技能更新状态 | 进度条更新 | `PUT /learning/plan/{id}/progress` |
| TC-3.5.4 | 添加技能 | 添加额外技能到计划 | DAG 更新 | `POST /learning/plan/{id}/skills` |
| TC-3.5.5 | 推荐列表 | 查看推荐 | 推荐技能卡片 | `GET /learning/recommendations` |
| TC-3.5.6 | 竞争力图表 | 查看竞争力 | 雷达图/柱状图 | `GET /match/competitiveness/{position}` |
| TC-3.5.7 | 职业路径 | 查看路径 | 路径图渲染 | `GET /evolution/career-path/{position}` |
| TC-3.5.8 | 行业趋势 | 查看趋势 | 趋势图 | `GET /evolution/industry-report` |

---

## Phase 4: 辅助页面联调（P2 — ≥80% 通过）

### TC-4.1 管理后台页 `/admin`

**前端组件**: Admin.vue, ReviewQueuePanel.vue, GraphNodeEditor.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-4.1.1 | 审核队列 | 访问 admin 审核Tab | 审核项列表 | `GET /admin/review-queue` |
| TC-4.1.2 | 通过审核 | 点"通过" | 行消失 | `POST /admin/audit/{id}/approve` |
| TC-4.1.3 | 拒绝审核 | 点"拒绝" | 行消失 | `POST /admin/audit/{id}/reject` |
| TC-4.1.4 | 图谱节点列表 | 切换到节点Tab | 节点表格 | `GET /admin/graph/nodes` |
| TC-4.1.5 | 创建节点 | 点"新建"，填表提交 | 节点出现 | `POST /admin/graph/nodes` |
| TC-4.1.6 | 编辑节点 | 点编辑，修改提交 | 节点更新 | `PUT /admin/graph/nodes/{id}` |
| TC-4.1.7 | 删除节点 | 点删除，确认 | 节点消失 | `DELETE /admin/graph/nodes/{id}` |
| TC-4.1.8 | 节点审批 | 点 approve/reject | 状态变更 | `POST /admin/graph/nodes/{id}/approve` |
| TC-4.1.9 | 数据源配置 | 切换到数据源Tab | 数据源配置表 | `GET /datasources` |
| TC-4.1.10 | 重置演示 | 点"重置演示数据" | 确认弹窗 → 重置 | `POST /admin/seed/reset` |

### TC-4.2 求职者分析页 `/analysis`

**前端组件**: PipelineAnalysis.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-4.2.1 | 上传分析 | 上传简历，选择岗位 | SSE 进度流 | `POST /pipeline/analyze` SSE stream |
| TC-4.2.2 | 进度事件 | 观察 SSE 进度 | 步骤进度更新 | progress 事件 step/status 字段 |
| TC-4.2.3 | 分析结果 | 分析完成 | 4 问题卡片 + 推荐 | result 事件含 extracted_skills/top_matches/skill_gaps |

### TC-4.3 闭环演示页 `/loop`

**前端组件**: LoopDemo.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-4.3.1 | 闭环运行 | 输入 JD 文本，点"运行" | 5 步进度动画 | `POST /loop/run` 返回 steps[] |
| TC-4.3.2 | 步骤结果 | 逐步查看 | 技能/图谱/匹配/路径结果 | 每步 data 字段完整 |
| TC-4.3.3 | 运行状态 | 查看运行状态 | status 显示 | `GET /loop/status/{runId}` |
| TC-4.3.4 | 历史记录 | 查看历史 | 历史列表 | `GET /loop/history?limit=20` |

### TC-4.4 数据大屏页 `/dashboard`

**前端组件**: DataDashboard.vue

| 用例 ID | 测试项 | 操作步骤 | 视觉预期 | 后端数据验证 |
|---------|--------|---------|---------|-------------|
| TC-4.4.1 | 大屏加载 | 访问 `/dashboard` | 暗色全屏大屏，6 个 KPI | `GET /dashboard/overview` |
| TC-4.4.2 | 来源分布 | 查看饼图 | 各数据源占比 | `GET /dashboard/distribution` |
| TC-4.4.3 | 技能域 Treemap | 查看 Treemap | 技能域分布 | domain_distribution 数据 |
| TC-4.4.4 | 质量趋势 | 查看趋势图 | 质量曲线 | `GET /dashboard/trends` |
| TC-4.4.5 | 流水线状态 | 查看流水线区域 | 阶段状态 | `GET /pipeline/stages` |
| TC-4.4.6 | 新兴技能 | 查看雷达 | 新兴技能雷达图 | `GET /evolution/emerging-skills` |

---

## Phase 5: 交互 & 视觉回归测试

### TC-5.1 响应式布局

| 用例 ID | 视口 | 检查项 | 预期 |
|---------|------|--------|------|
| TC-5.1.1 | 375px | 移动端汉堡菜单 | 出现并可用 |
| TC-5.1.2 | 375px | 图谱页可操作 | 触控缩放/拖拽 |
| TC-5.1.3 | 768px | 平板布局 | 无溢出，表格可滚动 |
| TC-5.1.4 | 1440px | 桌面完整布局 | 所有面板可见 |
| TC-5.1.5 | 1920px | 大屏 | 无拉伸变形 |

### TC-5.2 导航一致性

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-5.2.1 | 14 个路由全部可访问 | HTTP 200，无白屏 |
| TC-5.2.2 | 导航高亮与当前路由一致 | active 样式正确 |
| TC-5.2.3 | 浏览器后退/前进 | 路由正确切换 |
| TC-5.2.4 | 直接输入 URL | 页面正确加载（非 404） |

### TC-5.3 加载 & 错误状态

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-5.3.1 | 全局 loading 条 | API 请求期间显示 |
| TC-5.3.2 | 网络断开 | ElNotification 提示 |
| TC-5.3.3 | 后端 500 | ElMessage 错误提示 |
| TC-5.3.4 | 后端 401 | "登录已过期" 提示 |
| TC-5.3.5 | 后端 422 | "数据验证失败" 提示 |
| TC-5.3.6 | 超时（30s） | ElMessage 超时提示 |

### TC-5.4 浏览器控制台

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-5.4.1 | 14 页面逐页检查 | 0 个 JS error |
| TC-5.4.2 | 核心流程后检查 | 0 个 API 未捕获异常 |
| TC-5.4.3 | Vue warnings | ≤ 5 个非关键 warning |

---

## Phase 6: 前后端数据一致性深度验证

### TC-6.1 关键数据流端到端验证

| 用例 ID | 数据流 | 验证方式 | 预期 |
|---------|--------|---------|------|
| TC-6.1.1 | JD 文本 → extract/jd → 前端抽取结果表 | 对比后端 JSON 响应与前端渲染值 | 字段值完全一致 |
| TC-6.1.2 | 简历 → resume/upload → 前端技能 tag | 对比 skills 列表 | 数量+名称一致 |
| TC-6.1.3 | 技能+岗位 → match/position → 差距报告 | 对比 match_score/gap_skills | 精确匹配 |
| TC-6.1.4 | graph/overview → 首页节点数 | 对比 KPI 数字 | 一致 |
| TC-6.1.5 | quality/dashboard → KPI 卡片值 | 对比 4 个指标 | 一致 |
| TC-6.1.6 | evolution/trends → 趋势图数据点 | 对比 items.length | 一致 |
| TC-6.1.7 | positions → 岗位列表行数 | 对比 items.length | 一致 |
| TC-6.1.8 | learning/plan → 学习路径 DAG | 对比 skills + path | 一致 |

### TC-6.2 字段映射完整性

验证每个后端 API 响应中前端用到的字段都存在且类型正确：

| 模块 | 后端响应字段 | 前端期望字段 | 验证 |
|------|-------------|-------------|------|
| extract/jd | position_name, required_skills, normalized_skills, confidence, hallucination_score | 同左 | □ |
| match/position | match_score, matched_skills, gap_skills, skill_gap_detail, recommendations | 同左 | □ |
| quality/dashboard | total_nodes, avg_trust_score, hallucination_rate, pending_review, source_distribution, hallucination_trend, trust_distribution | 同左 + KPI 映射 | □ |
| graph/overview | domains[], connections[] | 同左 | □ |
| evolution/trends | items[] | 同左 | □ |
| learning/plan | plan_id, position, skills, phases | 同左 + 映射转换 | □ |
| dashboard/overview | total_nodes, total_edges, trust_score, active_data_sources | 映射到 DashboardOverview | □ |
| pipeline/status | is_running, current_run, last_run | 同左 | □ |

### TC-6.3 字段类型/格式一致性

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-6.3.1 | 数值字段不是字符串 | match_score 是 number 非 string |
| TC-6.3.2 | 日期字段格式统一 | ISO 8601 格式 |
| TC-6.3.3 | 枚举值合法 | category ∈ {hard_skill,soft_skill,tool,certificate} |
| TC-6.3.4 | 空值处理 | null/undefined → 前端默认值不崩溃 |
| TC-6.3.5 | 分页结构一致 | {items:[], total:number, page:number, page_size:number} |

---

## Phase 7: 问题记录与修复

### 问题记录模板

```
| # | 页面 | 用例ID | 严重级别 | 问题描述 | 前端表现 | 后端返回 | 根因 | 修复方案 | 状态 |
```

**严重级别定义**:
- **BLOCKER**: 数据完全不一致，功能不可用
- **CRITICAL**: 核心数据偏差，影响业务判断
- **HIGH**: 非核心数据不一致，有 workaround
- **MEDIUM**: UI 显示与后端微小偏差
- **LOW**: 纯视觉/体验问题

### 统一修复流程

1. Phase 1-6 执行完毕，汇总所有问题到问题清单
2. 按 BLOCKER → CRITICAL → HIGH → MEDIUM → LOW 排序
3. 逐条修复，每条修复后重新执行对应用例验证
4. 修复后回归测试（重新执行受影响用例）
5. 最终统计覆盖率

---

## 覆盖率计算

### 前端组件覆盖率

```
前端组件覆盖率 = (已验证通过组件数 / 总组件数) × 100%

总组件数 = 14 页面 + 38 业务组件 = 52
目标 ≥ 90% → 至少 47 项通过
```

### 后端数据功能覆盖率

```
后端数据功能覆盖率 = (已验证 API 数据一致性数 / 总 API 调用数) × 100%

总 API 调用数 = 77
目标 ≥ 90% → 至少 70 项通过
```

### 通过标准

| 级别 | 要求 |
|------|------|
| P0 用例 | 100% 通过 |
| P1 用例 | ≥ 95% 通过 |
| P2 用例 | ≥ 85% 通过 |
| 前端组件覆盖率 | ≥ 90% |
| 后端数据功能覆盖率 | ≥ 90% |
| 阻塞性 JS 错误 | 0 |
| BLOCKER/CRITICAL 问题 | 0 未修复 |

---

## 测试执行清单

### 执行顺序

1. **Phase 1**: 服务健康（5 分钟）
2. **Phase 2**: 核心页面 P0（30 分钟）— 使用 Playwright MCP 逐页截图 + 数据抓取
3. **Phase 3**: 重要页面 P1（20 分钟）
4. **Phase 4**: 辅助页面 P2（15 分钟）
5. **Phase 5**: 交互回归（10 分钟）
6. **Phase 6**: 数据一致性深度验证（20 分钟）
7. **Phase 7**: 问题汇总 + 统一修复（视问题数而定）

### 每页测试流程

```
1. 导航到页面
2. 截图（桌面 + 移动视口）
3. 等待数据加载完成
4. 打开 DevTools Network，记录 API 请求
5. 比对 API 响应与前端渲染数据
6. 执行交互操作（点击/输入/拖拽）
7. 验证操作结果与后端一致
8. 检查控制台错误
9. 记录问题
```

### 交付物

| 文件 | 说明 |
|------|------|
| `tests/e2e/INTEGRATION_TEST_PLAN.md` | 本文档 |
| `tests/e2e/integration-results/` | 每页截图 + API 响应 JSON |
| `tests/e2e/integration-issues.md` | 问题清单 |
| `tests/e2e/integration-fix-log.md` | 修复记录 |
| `tests/e2e/INTEGRATION_FINAL_REPORT.md` | 最终联调报告 |
