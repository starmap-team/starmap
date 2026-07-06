# Phase 3: 前端功能闭环 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-06
**Phase:** 03-frontend-closure
**Areas discussed:** 演化视图集成方式, 学习计划数据闭环, 演化交互细节, 操作反馈一致性

---

## 演化视图集成方式

| Option | Description | Selected |
|--------|-------------|----------|
| 加 overview 第4模式 | 在现有 radio 加第4个'演化'，选中时加载 EVOLVES_TO 边 | |
| 独立图层切换 | 加图层开关，可叠加在任意 overview 上显示演化边 | ✓ |
| 独立演化页面 | 新建页面专门展示演化关系 | |

**User's choice:** 独立图层切换
**Notes:** 更灵活（能同时看技术栈+演化），但视图密度高、着色易冲突——用户接受此代价

### 演化范围

| Option | Description | Selected |
|--------|-------------|----------|
| 聚焦当前岗位 | 默认渲染选中岗位的演化上下游，其他节点变暗 | ✓ |
| 显示全部 | 一次渲染所有 52 个岗位的演化关系网络 | |
| 双模式 | 图层开关控制显隐，另加'聚焦/全局'切换 | |

**User's choice:** 聚焦当前岗位
**Notes:** 调 `/evolution/paths/{position}` 而非全量，避免视觉过载

### 2D/3D 范围

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 3D 视图 | 3D 力导向图是默认视图且更适合关系网络 | ✓ |
| 2D + 3D 都支持 | 双倍工作量 | |
| 仅 2D 视图 | G6 边控制精细但 3D 是默认视图 | |

**User's choice:** 仅 3D 视图
**Notes:** Phase 3 快速闭环，2D 演化留作增强

### 跨领域演化

| Option | Description | Selected |
|--------|-------------|----------|
| 仅当前领域内 | 只高亮当前知识领域内的演化关系 | ✓ |
| 加载全部演化路径 | 聚焦岗位的全部上下游都加进图 | |
| 跨域单独提示 | 跨领域目标以虚拟节点或弹窗列表呈现 | |

**User's choice:** 仅当前领域内
**Notes:** 聚焦、不溢出，与 position 层语义一致。跨域网络可作 Phase 4/6 增强

---

## 学习计划数据闭环

### 用户绑定

| Option | Description | Selected |
|--------|-------------|----------|
| 硬编码 demo user | localStorage 存固定 user_id | |
| 不显示计划列表，仅创建 | 保留'加入计划'按钮，进度在 MatchDiagnosis 显示 | |
| localStorage 暂存 plan_id | 前端 localStorage 存 plan_id，调 GET 显示进度 | ✓ |

**User's choice:** localStorage 暂存 plan_id
**Notes:** 无 demo 痕迹、不新增页面、能闭环

### plan_id 过期策略

| Option | Description | Selected |
|--------|-------------|----------|
| 7 天过期自动清除 | 简单、无状态管理负担 | |
| 永不过期 | 但 plan 可能已在后端被删除导致 404 | |
| 每次验证有效性 | 打开时调 GET 验证，无效则清除 | ✓ |

**User's choice:** 每次验证有效性
**Notes:** 最可靠，无效时显示空状态

### 多计划支持

| Option | Description | Selected |
|--------|-------------|----------|
| 单计划，覆盖式 | 最简单 | |
| 多计划，列表式 | 需新增列表 UI | |
| 单计划，覆盖前确认 | 折中，避免误覆盖 | ✓ |

**User's choice:** 单计划，覆盖前确认
**Notes:** 用 el-message-box confirm

---

## 演化交互细节

### 时间线滑块

| Option | Description | Selected |
|--------|-------------|----------|
| 控制快照时间点 | 选中后显示该时间点的演化关系 | ✓ |
| 控制时间范围过滤 | 前端按时间过滤 EVOLVES_TO 边 | |
| 控制动画播放 | 自动按时间顺序播放演化变化 | |

**User's choice:** 控制快照时间点
**Notes:** 最符合'演化'语义，后端 `/evolution/snapshots` 已返回时间点列表

---

## 操作反馈一致性

### 弹窗形态

| Option | Description | Selected |
|--------|-------------|----------|
| el-dialog 弹窗 | 居中弹窗，Admin.vue 已用 | |
| el-drawer 抽屉 | 右侧滑出，更现代 | ✓ |
| Inline 行内编辑 | 最轻量，但复杂表单不适合 | |

**User's choice:** el-drawer 抽屉
**Notes:** 统一所有编辑场景

### 保存反馈

| Option | Description | Selected |
|--------|-------------|----------|
| 自动刷新列表 | 最流畅 | ✓ |
| toast 提示，手动刷新 | 更可控但多一步 | |
| toast + 自动刷新 | 最明确但可能冗余 | |

**User's choice:** 自动刷新列表
**Notes:** 同时显示 toast 提示

### Toast 文案

| Option | Description | Selected |
|--------|-------------|----------|
| 简洁统一 | '保存成功'/'保存失败，请重试' | ✓ |
| 动态具体 | '[操作名]成功'/'[操作名]失败：[原因]' | |
| 极简英文 | 'Done'/'Failed' | |

**User's choice:** 简洁统一
**Notes:** 不暴露技术细节

---

## Claude's Discretion

- 演化图层开关 UI 位置
- 演化边箭头样式和加载动画
- 未选岗位时演化图层默认状态
- 快照时间点无数据时的降级显示
- EVOLVES_TO 边点击详情的具体字段布局
- LearningCenter 空状态引导文案
- 学习进度百分比的可视化形式

## Deferred Ideas

- **用户系统（登录/注册/权限）** — 全新能力，建议 Phase 7 或后续里程碑
- **2D 视图演化边渲染** — 可作 Phase 5/6 增强
- **跨领域演化目标渲染** — 可作 Phase 4/6 增强
- **演化动画播放** — 可作后续增强
