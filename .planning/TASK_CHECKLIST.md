# StarMap 业务闭环优化 — 完整任务清单

**创建日期**: 2026-07-16
**来源**: 全栈代码实现 vs 设计文档 v2.0 + Roadmap v3.0 + 前后端联调审计
**状态**: 待执行
**总任务数**: 15 项主任务 + 衍生子任务

---

## 优先级定义

| 级别 | 含义 | 修复时限 |
|------|------|---------|
| **P0** | 业务正确性阻断 — 数据不一致或核心流程断裂 | 立即 |
| **P1** | 数据完整性 — 字段丢失/契约不匹配 | 本迭代 |
| **P2** | 评审指标/用户体验 — 影响评分或观感 | 下迭代 |
| **P3** | 可选增强 — 锦上添花 | 有余力时 |

---

## 🔴 P0 — 业务正确性阻断 (2 项)

### BUG-01: batch_audit 缺少 Neo4j 同步

| 属性 | 值 |
|------|-----|
| **ID** | BUG-01 |
| **优先级** | P0 |
| **类型** | Bug — 数据不一致 |
| **描述** | `admin_audit_service.py:277` 的 `batch_audit()` 函数不接收 `neo4j_driver` 参数，也不调用 `_sync_neo4j_on_audit()`。批量审核通过/拒绝的条目仅更新 PostgreSQL，不同步到 Neo4j，导致图谱数据与关系数据不一致。 |
| **影响** | Admin 批量审核后，Neo4j 中节点状态/trust_score 不变，前端图谱展示与审核结果脱节 |
| **涉及文件** | `backend/app/services/admin_audit_service.py` (line 277-331), `backend/app/api/v1/admin.py` (line 151) |
| **修复方案** | 1. `batch_audit()` 添加 `neo4j_driver: Any \| None = None` 参数<br>2. 循环内对每个 item 调用 `_sync_neo4j_on_audit()`<br>3. `admin.py` API 端点注入并传递 `neo4j_driver` |
| **衍生子任务** | BUG-01-S1: 为 batch_audit Neo4j 同步添加单元测试<br>BUG-01-S2: 验证批量审核后 Neo4j 节点状态一致性 |
| **验证标准** | 1. 批量审核 3+ 条目后，Neo4j 对应节点 trust_score/status 更新<br>2. 单条审核与批量审核结果一致<br>3. 无 neo4j_driver 时不报错（graceful degradation） |

### FLOW-02: 学习进度 → 用户技能更新 未闭环

| 属性 | 值 |
|------|-----|
| **ID** | FLOW-02 |
| **优先级** | P0 |
| **类型** | 数据流断点 — 业务闭环缺失 |
| **描述** | 设计文档 §2.1 模块D 要求"技能差距 + 针对性改进建议 + 学习路径规划"形成闭环。当前学习计划中 skill 标记 mastered 后，`userStore.parsedSkills` 不更新，重新匹配不反映学习进步。用户完成学习后看不到匹配分数提升，闭环断裂。 |
| **影响** | 学习中心与匹配诊断之间无反馈环，用户无法量化学习成果 |
| **涉及文件** | `frontend/src/stores/learningPlan.ts` (updateProgress), `frontend/src/stores/user.ts` (parsedSkills), `frontend/src/stores/match.ts` |
| **修复方案** | 1. `learningPlan.ts` 的 `updateProgress()` 中，当 skill 状态变为 `mastered` 时，将该 skill 添加到 `userStore.parsedSkills`<br>2. 在 `MatchDiagnosis.vue` 或 `LearningCenter.vue` 添加"重新匹配"按钮，使用更新后的技能重新调用 match API<br>3. 展示匹配分数变化 (before → after) |
| **衍生子任务** | FLOW-02-S1: 设计 userStore.parsedSkills 的更新接口 (addSkill/removeSkill)<br>FLOW-02-S2: LearningCenter 添加"重新匹配"交互<br>FLOW-02-S3: 匹配分数变化可视化 (差值动画/趋势箭头) |
| **验证标准** | 1. 学习计划中 skill 标记 mastered → userStore.parsedSkills 包含该 skill<br>2. 重新匹配后 match_score 提升<br>3. UI 展示分数变化 |

---

## 🟠 P1 — 数据完整性 (5 项)

### FLOW-03: 简历技能 proficiency 丢失

| 属性 | 值 |
|------|-----|
| **ID** | FLOW-03 |
| **优先级** | P1 |
| **类型** | 数据流断点 — 字段丢失 |
| **描述** | `resume.ts` 将 LLM 返回的技能存为 plain string + fake skill_id，丢失 proficiency 数据。后端 `resume_service.py` 调用 JD 抽取管线，LLM 返回含 proficiency 的结构化数据，但前端 store 未保留。 |
| **影响** | 简历技能无熟练度信息，匹配时所有技能视为同等水平，影响匹配精度 |
| **涉及文件** | `frontend/src/stores/resume.ts`, `frontend/src/stores/user.ts`, `backend/app/core/extraction/jd_extract.py` |
| **修复方案** | 1. `resume.ts` 存储结构化技能对象 `{name, proficiency, source}` 而非 plain string<br>2. `user.ts` 的 `parsedSkills` 支持带 proficiency 的技能<br>3. 匹配时传入 proficiency 信息 |
| **衍生子任务** | FLOW-03-S1: 定义 ResumeSkill 接口 (name, proficiency, category, source)<br>FLOW-03-S2: 后端 /resume/upload 响应包含 proficiency 字段<br>FLOW-03-S3: 匹配引擎使用 proficiency 加权 |
| **验证标准** | 1. 上传简历后，store 中技能含 proficiency<br>2. 匹配诊断雷达图展示熟练度差异 |

### FLOW-01: Quality total_extractions 字段丢失

| 属性 | 值 |
|------|-----|
| **ID** | FLOW-01 |
| **优先级** | P1 |
| **类型** | 字段缺失 |
| **描述** | 后端 `QualityDashboard` 返回 `total_extractions` 字段，但前端 `QualityMetrics` 接口未定义该字段，数据被静默丢弃。 |
| **影响** | Quality Dashboard KPI 数据不完整 |
| **涉及文件** | `frontend/src/stores/quality.ts` (lines 10-30), `backend/app/api/v1/quality.py` (line 42) |
| **修复方案** | 1. `quality.ts` 的 `QualityMetrics` 接口添加 `total_extractions: number`<br>2. QualityDashboard 页面展示该 KPI |
| **衍生子任务** | FLOW-01-S1: QualityDashboard 页面添加"总抽取数"KPI 卡片 |
| **验证标准** | 1. Quality Dashboard 展示 total_extractions 数据<br>2. 无 TypeScript 类型错误 |

### ALIGN-01: OpenAPI 契约缺失 40+ 端点

| 属性 | 值 |
|------|-----|
| **ID** | ALIGN-01 |
| **优先级** | P1 |
| **类型** | 契约不匹配 |
| **描述** | `openapi.yaml` 仅覆盖 ~50 端点，后端实际 90+ 端点。缺失: `/graph/overview`, `/match/diagnose`, `/match/history`, `/evolution/*`, `/quality/*`, `/admin/*`, `/judge/*`, `/pipeline/*`, `/dashboard/*`, `/learning/*`, `/loop/*`, `/datasources/*`, `/auth/*` 等。 |
| **影响** | `npm run gen:api` 生成的 schema.ts 不完整，前端无法获得类型安全 |
| **涉及文件** | `starmap-contracts/openapi.yaml`, `frontend/src/api/schema.ts` |
| **修复方案** | 1. 逐模块补齐 openapi.yaml 端点定义<br>2. 运行 `npm run gen:api` 重新生成 schema.ts<br>3. 修复前端因类型变更产生的编译错误 |
| **衍生子任务** | ALIGN-01-S1: 补齐 auth 模块 7 端点<br>ALIGN-01-S2: 补齐 evolution 模块 12 端点<br>ALIGN-01-S3: 补齐 quality 模块 7 端点<br>ALIGN-01-S4: 补齐 admin 模块 15+ 端点<br>ALIGN-01-S5: 补齐 pipeline 模块 14 端点<br>ALIGN-01-S6: 补齐 learning/loop/dashboard/datasource 模块<br>ALIGN-01-S7: 运行 gen:api + 修复前端类型错误 |
| **验证标准** | 1. `starmap-contracts/validate.py` 通过<br>2. `npm run gen:api` 无错误<br>3. `vue-tsc --noEmit` 通过 |

### ALIGN-02: MatchResult schema 过时

| 属性 | 值 |
|------|-----|
| **ID** | ALIGN-02 |
| **优先级** | P1 |
| **类型** | 契约不匹配 |
| **描述** | 前端 `schema.ts` 中 MatchResult 仅有 `{match_score, matched_skills, gap_skills, recommendations}`，后端实际返回 `match_id, target_position, missing_required, missing_bonus, skill_gap_detail, overall_assessment, estimated_learning_time` 等额外字段。 |
| **影响** | 前端无法类型安全地访问完整匹配结果 |
| **涉及文件** | `starmap-contracts/openapi.yaml` (MatchResult schema), `frontend/src/api/schema.ts` |
| **修复方案** | 1. 更新 openapi.yaml MatchResult schema 包含全部字段<br>2. 重新 gen:api<br>3. 前端 match.ts store 使用完整类型 |
| **衍生子任务** | (包含在 ALIGN-01-S7 中) |
| **验证标准** | 1. MatchResult 类型包含全部后端返回字段<br>2. MatchDiagnosis 页面可访问 skill_gap_detail 等字段 |

### ALIGN-03~05: 类型/枚举不匹配 (合并)

| 属性 | 值 |
|------|-----|
| **ID** | ALIGN-03 (EmergingSkill), ALIGN-04 (ChangeType), ALIGN-05 (Evolution trends) |
| **优先级** | P1 |
| **类型** | 契约不匹配 — 类型定义不一致 |
| **描述** | ALIGN-03: 前端 EmergingSkill 用 `name/frequency/growth_rate`，后端返回 `skill_name/z_score/current_frequency`<br>ALIGN-04: 后端 ChangeType 6值 (`added_required/added_preferred/removed/promoted/demoted/retained`) vs 前端 6值 (`proficiency_change/requirement_change/new_skill/removed_skill/trend_change/confidence_change`)<br>ALIGN-05: 前端期望 evolution trends `{quarters, items}`，后端仅返回 `{items}` |
| **影响** | 前端需防御性解析，类型不安全 |
| **涉及文件** | `frontend/src/types/evolution.ts`, `frontend/src/stores/evolution.ts`, `starmap-contracts/openapi.yaml` |
| **修复方案** | 1. 统一 EmergingSkill 字段名 (以后端为准)<br>2. 统一 ChangeType 枚举 (以后端为准，前端做映射)<br>3. Evolution trends 响应添加 quarters 字段或前端适配 |
| **衍生子任务** | ALIGN-03-S1: 更新前端 EmergingSkill 接口 + EvolutionDashboard 适配<br>ALIGN-04-S1: 统一 ChangeType 枚举 + EvolutionChangelogDrawer 适配<br>ALIGN-05-S1: Evolution trends 响应结构对齐 |
| **验证标准** | 1. 无 `as any` 类型断言<br>2. EvolutionDashboard 正确展示 emerging skills 和 changelog |

---

## 🟡 P2 — 评审指标/用户体验 (5 项)

### METRIC-01: JD 解析 F1 提升至 90%+

| 属性 | 值 |
|------|-----|
| **ID** | METRIC-01 |
| **优先级** | P2 |
| **类型** | 评估指标 |
| **描述** | 当前 JD 解析 F1 = 0.8767 (M2)，设计文档要求 ≥90%。需优化 prompt 模板和后处理逻辑。 |
| **影响** | 评审"实用价值"维度可能丢分 (中档 10-24 vs 满档 25-30) |
| **涉及文件** | `backend/app/core/extraction/prompt.py`, `backend/app/core/extraction/jd_extract.py`, `evaluation/` |
| **修复方案** | 1. 分析 baseline_report 中低 F1 字段 (job_title? required_skills?)<br>2. 优化 prompt 模板 (更明确的字段指引、few-shot 示例)<br>3. 优化归一化逻辑 (别名映射覆盖率)<br>4. 重新运行评估验证 |
| **衍生子任务** | METRIC-01-S1: 分析 F1 误差分布 (按字段/按样本)<br>METRIC-01-S2: Prompt A/B 测试<br>METRIC-01-S3: 归一化别名映射扩展<br>METRIC-01-S4: 重新评估 + 生成报告 |
| **验证标准** | 1. F1 ≥ 0.90 on 100 条 Golden Set<br>2. 评估报告可复现 |

### METRIC-02: 简历提取准确率验证

| 属性 | 值 |
|------|-----|
| **ID** | METRIC-02 |
| **优先级** | P2 |
| **类型** | 评估指标 — 未验证 |
| **描述** | 设计文档要求简历提取 F1 ≥90%，但当前无标注数据集和评估结果。 |
| **影响** | 评审"实用价值"维度缺一项验证 |
| **涉及文件** | `evaluation/run_real_eval.py`, `evaluation/judge_eval.py` |
| **修复方案** | 1. 准备 50 份标注简历 (技能+熟练度)<br>2. 运行 `evaluation/run_real_eval.py`<br>3. 如 F1 < 90%，优化 resume 抽取逻辑 |
| **衍生子任务** | METRIC-02-S1: 创建简历标注 Golden Set (50份)<br>METRIC-02-S2: 运行评估 + 生成报告<br>METRIC-02-S3: 如需优化，改进 resume 抽取 |
| **验证标准** | 1. 简历提取 F1 ≥ 0.90<br>2. 评估报告可复现 |

### METRIC-03: 人岗匹配准确率验证

| 属性 | 值 |
|------|-----|
| **ID** | METRIC-03 |
| **优先级** | P2 |
| **类型** | 评估指标 — 未验证 |
| **描述** | 设计文档要求匹配准确率 ≥90%，但当前无 100 个 (JD, 简历) 配对评估结果。 |
| **影响** | 评审"实用价值"维度缺一项验证 |
| **涉及文件** | `evaluation/`, `backend/app/core/matching/` |
| **修复方案** | 1. 准备 100 个 (JD, 简历) 配对标注<br>2. 运行匹配评估<br>3. 如准确率 < 90%，优化匹配算法 |
| **衍生子任务** | METRIC-03-S1: 创建匹配评估配对数据集<br>METRIC-03-S2: 运行评估 + 生成报告<br>METRIC-03-S3: 如需优化，改进 scorer.py |
| **验证标准** | 1. 匹配准确率 ≥ 90% (阈值 0.6 二元判定)<br>2. 评估报告可复现 |

### UX-01: 移除 agent log 遥测代码

| 属性 | 值 |
|------|-----|
| **ID** | UX-01 |
| **优先级** | P2 |
| **类型** | 生产安全 — 调试代码残留 |
| **描述** | `Home.vue` 和 `useHomeInteractions.ts` 中约 10 处 `#region agent log` 块调用 `fetch('http://127.0.0.1:7337/ingest/...')`，每次用户交互 (zoom/toggle/camera) 都发送遥测数据到本地调试服务器。生产环境必须移除。 |
| **影响** | 生产环境产生大量无效网络请求 + 潜在信息泄露 |
| **涉及文件** | `frontend/src/pages/Home.vue`, `frontend/src/composables/home/useHomeInteractions.ts` |
| **修复方案** | 1. 搜索所有 `#region agent log` 块<br>2. 移除或用 `import.meta.env.DEV` 条件包裹<br>3. 确保生产构建不含这些调用 |
| **衍生子任务** | UX-01-S1: 搜索并清理所有 agent log 块<br>UX-01-S2: 添加 DEV 环境变量守卫 (可选保留开发模式) |
| **验证标准** | 1. `npm run build` 后无 127.0.0.1:7337 请求<br>2. 开发模式可选保留 |

### UX-02: Login 页 3D 背景增强

| 属性 | 值 |
|------|-----|
| **ID** | UX-02 |
| **优先级** | P2 |
| **类型** | 用户体验 — 设计未对齐 |
| **描述** | 设计文档 `frontend-page-design.md` §2.1 要求 Login 页左侧 3D 粒子背景 (Graph3D auto-rotate, opacity=0.25, maxNodes=150)，登录成功后 opacity 0.25→1.0 过渡。当前 Login 页为纯表单，无 3D 背景。 |
| **影响** | 与设计稿不一致，缺少"登录即进入图谱"的沉浸感 |
| **涉及文件** | `frontend/src/pages/Login.vue` |
| **修复方案** | 1. Login.vue 引入 Graph3D 组件作为背景<br>2. 设置 auto-rotate, opacity=0.25, maxNodes=150<br>3. 登录成功动画: opacity 0.25→1.0 (300ms) + 卡片 fade-out (200ms) |
| **衍生子任务** | UX-02-S1: Graph3D 背景集成 (props: opacity, autoRotate, maxNodes)<br>UX-02-S2: 登录成功过渡动画<br>UX-02-S3: 移动端适配 (≤768px 单栏全屏) |
| **验证标准** | 1. Login 页展示 3D 图谱背景<br>2. 登录成功有过渡动画<br>3. 移动端正常显示 |

### DATA-01: 技能节点数提升至 500+

| 属性 | 值 |
|------|-----|
| **ID** | DATA-01 |
| **优先级** | P2 |
| **类型** | 数据指标 |
| **描述** | 设计文档要求标准化技能节点 ≥500，当前本体 240 + 抽取补充约 380+，未达标。 |
| **影响** | 评审"图谱规模"指标可能扣分 |
| **涉及文件** | `docs/ontology/skill_taxonomy.yaml`, `scripts/import_esco_skill.py` |
| **修复方案** | 1. 扩展 skill_taxonomy.yaml 覆盖更多子领域<br>2. 增加 ESCO 映射覆盖率<br>3. 运行 `import_esco_skill.py` 导入更多 ESCO 技能 |
| **衍生子任务** | DATA-01-S1: 审计当前技能节点数 (Cypher COUNT)<br>DATA-01-S2: 扩展 taxonomy + ESCO 映射<br>DATA-01-S3: 重新导入 + 验证 ≥500 |
| **验证标准** | 1. `MATCH (s:Skill) RETURN count(s)` ≥ 500 |

---

## 🟢 P3 — 可选增强 (3 项)

### UX-03: Graph3D z 轴分层 (能力阶梯)

| 属性 | 值 |
|------|-----|
| **ID** | UX-03 |
| **优先级** | P3 |
| **类型** | 可视化增强 |
| **描述** | 设计文档 §2.2 提到"可选增强": 将 proficiency 映射到 z 轴 (初级在下/高级在上)，形成"能力阶梯"视觉效果，与 Marble 的"年龄分层"同构。当前 Graph3D 为纯 force-directed 布局。 |
| **影响** | 无功能影响，纯视觉增强 |
| **涉及文件** | `frontend/src/components/Graph3D.vue`, `frontend/src/composables/useNodeThreeObject.ts` |
| **修复方案** | 1. 在 3D force 布局中添加 z 轴约束: `node.z = proficiency * zScale`<br>2. 不同层级用不同发光强度区分 |
| **衍生子任务** | UX-03-S1: 设计 z 轴映射规则 (proficiency→z坐标)<br>UX-03-S2: 实现 3D 布局 z 约束<br>UX-03-S3: 添加层级视觉区分 |
| **验证标准** | 1. 3D 图谱中技能节点按熟练度分层<br>2. 视觉上可区分初/中/高级 |

### UX-04: Evolution changelog 参数命名修正

| 属性 | 值 |
|------|-----|
| **ID** | UX-04 |
| **优先级** | P3 |
| **类型** | 代码质量 — 命名误导 |
| **描述** | `evolution.ts:99` 的 `fetchChangelog(positionName: string)` 参数名为 `positionName`，但调用处实际传入 skill name (fallback: `row.related_positions?.[0] ?? row.skill_name`)。后端 `identifier` 参数同时支持 position 和 skill。参数命名误导开发者。 |
| **影响** | 无功能影响，代码可读性问题 |
| **涉及文件** | `frontend/src/stores/evolution.ts` |
| **修复方案** | 1. 重命名参数为 `identifier: string`<br>2. 更新 JSDoc 说明同时支持 position 和 skill |
| **衍生子任务** | (无) |
| **验证标准** | 1. 参数名准确反映语义<br>2. 功能无回归 |

### UX-05: ChangeType 枚举统一

| 属性 | 值 |
|------|-----|
| **ID** | UX-05 |
| **优先级** | P3 |
| **类型** | 契约一致性 |
| **描述** | 后端 ChangeType: `added_required, added_preferred, removed, promoted, demoted, retained`<br>前端 ChangeType: `proficiency_change, requirement_change, new_skill, removed_skill, trend_change, confidence_change`<br>两套完全不同的枚举值，前端需做映射。 |
| **影响** | 前端 EvolutionChangelogDrawer 需要硬编码映射，维护成本高 |
| **涉及文件** | `frontend/src/components/EvolutionChangelogDrawer.vue`, `backend/app/core/evolution/diff_engine.py` |
| **修复方案** | 1. 以后端枚举为准，前端统一使用后端值<br>2. 更新 EvolutionChangelogDrawer 的标签映射<br>3. 更新 openapi.yaml 枚举定义 |
| **衍生子任务** | UX-05-S1: 前端 ChangeType 枚举重定义<br>UX-05-S2: EvolutionChangelogDrawer 标签适配 |
| **验证标准** | 1. 前后端 ChangeType 值一致<br>2. Changelog 展示正确标签 |

---

## 任务依赖关系

```
BUG-01 (batch_audit Neo4j同步)
  └── BUG-01-S1 (单元测试)
  └── BUG-01-S2 (一致性验证)

FLOW-02 (学习→匹配反馈环)
  ├── FLOW-02-S1 (userStore接口) ← 先行
  ├── FLOW-02-S2 (重新匹配交互) ← 依赖 S1
  └── FLOW-02-S3 (分数变化可视化) ← 依赖 S2

FLOW-03 (简历proficiency)
  ├── FLOW-03-S1 (ResumeSkill接口) ← 先行
  ├── FLOW-03-S2 (后端响应) ← 与 S1 并行
  └── FLOW-03-S3 (匹配加权) ← 依赖 S1+S2

ALIGN-01 (OpenAPI补齐) ← 阻塞 ALIGN-02, ALIGN-03~05
  ├── ALIGN-01-S1~S6 (各模块补齐) ← 可并行
  └── ALIGN-01-S7 (gen:api + 修复) ← 依赖 S1~S6

ALIGN-02 (MatchResult) ← 依赖 ALIGN-01
ALIGN-03~05 ← 依赖 ALIGN-01

METRIC-01~03 ← 可并行，无代码依赖
UX-01 (agent log) ← 独立
UX-02 (Login 3D) ← 独立
DATA-01 (技能500+) ← 独立
UX-03~05 ← 独立
```

## 推荐执行顺序

| 批次 | 任务 | 预估工时 | 驱动方式 |
|------|------|---------|---------|
| **Batch 1** | BUG-01 + FLOW-02 | 2-3h | `/gsd:quick` 轻量修复 |
| **Batch 2** | FLOW-03 + FLOW-01 | 1-2h | `/gsd:quick` |
| **Batch 3** | ALIGN-01 (S1~S6 并行) | 3-4h | `/gsd:plan-phase` + `/gsd:execute-phase` |
| **Batch 4** | ALIGN-01-S7 + ALIGN-02 + ALIGN-03~05 | 2-3h | `/gsd:quick` |
| **Batch 5** | UX-01 + UX-02 | 2-3h | `/gsd:quick` |
| **Batch 6** | METRIC-01~03 + DATA-01 | 4-6h | `/gsd:plan-phase` (评估需准备数据) |
| **Batch 7** | UX-03~05 | 1-2h | `/gsd:quick` (有余力时) |

---

## 完成追踪

| ID | 状态 | 完成日期 | 备注 |
|----|------|---------|------|
| BUG-01 | ✅ 已完成 | 2026-07-16 | batch_audit 添加 neo4j_driver + _sync_neo4j_on_audit 调用 |
| FLOW-01 | ✅ 已完成 | 2026-07-16 | QualityMetrics 添加 total_extractions 字段 |
| FLOW-02 | ✅ 已完成 | 2026-07-16 | S1: addParsedSkill(v3.0已有); S2: LearningCenter重新匹配按钮+MatchDiagnosis路由; S3: GapAnalysisReport分数差值卡片 |
| FLOW-03 | 🟡 部分完成 | | ParsedSkill 含 proficiency, 但 userStore.setResume 仍为 string[] |
| ALIGN-01 | ⬜ 待开始 | | OpenAPI 93/125 路径覆盖, 缺 ~32 端点 |
| ALIGN-02 | ✅ 已修复 | (v3.0) | MatchResult schema 已含 match_id/missing_required/skill_gap_detail |
| ALIGN-03 | ✅ 已修复 | (v3.0) | EmergingSkill 前端为后端超集, 核心字段匹配 |
| ALIGN-04 | ⬜ 待开始 | | ChangeType 枚举前后端不一致 |
| ALIGN-05 | ⬜ 待开始 | | Evolution trends 响应结构 |
| METRIC-01 | ⬜ 待开始 | | JD F1=0.8767, 需提升至 ≥90% |
| METRIC-02 | ⬜ 待开始 | | 简历提取 F1 未验证 |
| METRIC-03 | ⬜ 待开始 | | 匹配准确率未验证 |
| UX-01 | ⬜ 待开始 | | agent log 遥测代码需移除 |
| UX-02 | ⬜ 待开始 | | Login 页 3D 背景未实现 |
| DATA-01 | ⬜ 待开始 | | 技能节点 ~380, 需 ≥500 |
| UX-03 | ⬜ 待开始 | | Graph3D z 轴分层 |
| UX-04 | ⬜ 待开始 | | changelog 参数命名修正 |
| UX-05 | ⬜ 待开始 | | ChangeType 枚举统一 |

---

*本清单为活文档，每完成一项任务后更新状态，并检查是否产生衍生子任务。*
