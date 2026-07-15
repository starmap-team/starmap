# StarMap 管理后台重构方案

## 🎯 目标

让**未接触过该系统的用户**通过前端页面就能清晰理解项目的设计功能和业务意图。
两个审核流并存（§5.2 演化变更 + Phase 23 内容审核），并按业务环节重设计 Tab。

## 📋 业务流全景（让新用户一眼看懂）

```
┌──────────────────────────────────────────────────────────┐
│  StarMap 业务闭环：JD → 抽取 → 图谱 → 匹配 → 学习        │
│                                                            │
│  [采集]    [抽取]    [图谱]    [审核]    [匹配]    [学习]  │
│  数据源  →  LLM  →  Neo4j  →  人工  →  诊断  →  路径   │
└──────────────────────────────────────────────────────────┘
```

## 🏗️ 实施步骤（5 个阶段）

### Step 1: 后端实现 §5.2 设计意图（缺失的 INSERT 路径）

**文件**: `backend/app/core/evolution/orchestrator.py`

修改 `_save_changelog` 方法：保存 `evolution_changelog` 时，**同时**根据 `trust_score` 把变更写入 `review_queue`：
- `trust_score < 0.6` → 插入 `review_queue` 标记 `pending`
- `trust_score >= 0.6` → 直接入图谱（已实现）

```python
async def _save_changelog(self, diff_result: DiffResult) -> int:
    count = 0
    for change in diff_result.changes:
        if change.change_type.value == "retained":
            continue
        # 1. 写 evolution_changelog (已有)
        record = EvolutionChangelog(...)
        self._session.add(record)
        # 2. 根据 trust_score 决定是否入 review_queue (§5.2 §7.1)
        if change.trust_score < 0.6:
            self._session.add(ReviewQueue(
                entity_type="new_skill" if ... else "position",
                entity_name=change.skill_name,
                status="pending",
                payload={"trust": int(change.trust_score * 100), ...},
            ))
        count += 1
    await self._session.flush()
    return count
```

### Step 2: 修复 `approve_audit` 数据一致性 bug

**文件**: `backend/app/services/admin_audit_service.py:181-192`

Phase 23 加了 `review_status` 列后，`approve_audit` 创建新 `PositionRecord`/`SkillRecord` 时**没设** `review_status='approved'`：

```python
# Bug: phase 23 之前写的代码
session.add(PositionRecord(name=row.entity_name))

# 修复: 显式设 review_status=approved
session.add(PositionRecord(
    name=row.entity_name,
    review_status="approved",
    reviewed_by="admin:approval",
    reviewed_at=datetime.now(UTC),
))
```

### Step 3: Admin.vue 重设计 Tab（按业务环节）

**文件**: `frontend/src/pages/Admin.vue` + 新增 `AdminOverview.vue`

**新 Tab 结构**（按用户视角的"业务环节"）：

| Tab | 名称 | 内容 | 后端 | 业务定位 |
|-----|------|------|------|----------|
| 0 | **业务总览** | 系统健康 KPI + 数据流图谱 | `/dashboard/overview` + 业务说明 | 让新用户第一眼理解 |
| 1 | **内容审核** | position/skill review_status=pending | `/admin/review-items` | Phase 23: 主数据生命周期 |
| 2 | **演化变更** | evolution_changelog trust<0.6 | `/admin/review-queue` | §5.2: 能力更新审核 |
| 3 | **图谱与质量** | Neo4j 节点 CRUD + 质量数据 | `/admin/graph/nodes` + 质量 | §7: 图谱健康 |
| 4 | **数据采集** | 数据源 + 爬虫状态 | `/datasources` | §5.2: 数据输入 |
| 5 | **Prompt 工程** | LLM prompt 版本 | `/admin/prompts` | §7.2: 幻觉防控 |
| 6 | **系统** | 用户 + 审计日志 | `/admin/users` + `/admin/audit-events` | 运维与安全 |

**AdminOverview.vue** 设计：

```
┌─ StarMap 业务总览 ─────────────────────────────────────────┐
│ [采集]    [抽取]    [图谱]    [审核]    [匹配]    [学习]    │
│  数据源 →  LLM  →  Neo4j →  人工  →  诊断  →  路径    │
├──────────────────────────────────────────────────────────┤
│ 4 个核心 KPI 卡片：                                        │
│  ┌─────────┬──────────┬──────────┬──────────┐            │
│  │ 待审内容 │ 待审演化 │ 本周新增 │ 平均信任度 │            │
│  │   0     │   0     │  +5     │   82%   │            │
│  └─────────┴──────────┴──────────┴──────────┘            │
├──────────────────────────────────────────────────────────┤
│ 各 Tab 一句话说明（让新用户秒懂）                          │
│ • 内容审核：新发现的岗位/技能需要管理员确认                │
│ • 演化变更：定期分析发现的能力变化需要人工裁决            │
│ • 图谱管理：直接编辑 Neo4j 节点                            │
│ ...                                                          │
└──────────────────────────────────────────────────────────┘
```

### Step 4: 每个 Tab 添加业务说明横幅

**所有 Tab**: 在 `<el-card>` 顶部添加 `<el-alert type="info">` 说明这个 tab 的业务含义

**示例** (内容审核 Tab):
```vue
<el-alert type="info" :closable="false" show-icon>
  <template #title>本 Tab 用于审核新发现的内容实体</template>
  <p>当系统从数据源抽取新岗位/技能、或在 /extract/jd 提取新内容时，
  这些实体进入"待审核"状态。审核通过后才会出现在公开图谱中。</p>
</el-alert>
```

**示例** (演化变更 Tab):
```vue
<el-alert type="warning" :closable="false" show-icon>
  <template #title>本 Tab 用于审核能力演化变更</template>
  <p>系统每周自动分析岗位能力图谱的演化（§5.2），对于信任度低于 0.6 的
  变更提案，需要人工确认是否更新图谱。</p>
</el-alert>
```

### Step 5: 用户文档与引导

**新增**: `frontend/src/pages/Admin.vue` 顶部加一个"业务流程图"组件 (`AdminFlow.vue`)：
- 显示 6 个业务环节的图标和箭头
- 每个环节点击跳转到对应 Tab 或页面
- 让用户随时能看到"我在整个业务流的位置"

```
JD抽取  →  图谱节点  →  演化分析  →  人工审核  →  入图谱
[采集]    [抽取]      [图谱]      [审核]      [发布]
   ↑                                              ↓
   └────── 数据源  ←──────  Prompt  ←────  匹配诊断
```

## 📁 涉及的文件

### 后端
- `backend/app/core/evolution/orchestrator.py` — 添加 trust_score → review_queue 逻辑
- `backend/app/services/admin_audit_service.py` — 修复 `approve_audit` 数据一致性

### 前端
- `frontend/src/pages/Admin.vue` — 重设计 tab 结构
- `frontend/src/components/AdminOverview.vue` — 新增（业务总览）
- `frontend/src/components/AdminFlow.vue` — 新增（业务流图）
- `frontend/src/components/ContentReviewPanel.vue` — 业务说明横幅
- `frontend/src/components/ReviewQueuePanel.vue` — 业务说明横幅
- `frontend/src/components/GraphNodeEditor.vue` — 业务说明横幅

## ✅ 验收标准

1. 后端：运行 `analyze_evolution_trends` 后，trust<0.6 的变更自动进入 ReviewQueue
2. ReviewQueue tab 不再"几乎为空" — 它显示真实的中等信任度变更
3. 内容审核 Tab 显示新发现但未批准的实体
4. Admin 页面第一屏是"业务总览"——让新用户 10 秒理解系统
5. 每个 Tab 顶部有业务说明
6. 用户能从 Admin 页面看到自己的"业务位置"

## 🚦 实施顺序

1. 后端: orchestrator.py 加 review_queue 写入逻辑 + 修复 approve_audit bug
2. 前端: 新增 AdminOverview + AdminFlow
3. 前端: Admin.vue 重设计 tab + 业务说明
4. 测试 + 提交

## ⚠️ 风险与缓解

| 风险 | 缓解 |
|------|------|
| orchestrator 修改影响 evolution 测试 | 现有 review_queue 行为 0 → 添加新行为 |
| Tab 重设计破坏现有用户习惯 | 保留 `activeTab` 默认值 + 业务流程图导航 |
| AdminOverview 加载慢 | 复用 `useDashboardStore` 已有的缓存 |