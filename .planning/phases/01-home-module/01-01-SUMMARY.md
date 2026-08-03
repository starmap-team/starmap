# Phase 1 · 全景图谱模块 · 执行总结

**执行日期:** 2026-07-26
**Milestone:** v5.0 (12 模块联调审核开发)
**Wave:** 1 (数据模块)
**Status:** ✅ Completed

---

## 执行结果

### Task 1: 全景图谱模块源码缺陷分析 ✅
- 文件: `docs/archive/home-source-analysis.md`
- 覆盖 6 层源码分析（前端页面 / Composables / Store / API / Service / 渲染）
- 发现 13 个问题：3 HIGH、4 MEDIUM、6 LOW
- 5 个 HIGH/MEDIUM 已在代码中修复

### Task 2: 用户优化点调研与需求设计 ✅
- 文件: `docs/archive/home-optimization-design.md`
- 5 个优化需求：后端搜索 API / 分页+LOD / 错误降级 / KPI 口径 / 演化交互
- 优先级排序 P0-P4

### Task 3: 前后端联调修复 ✅ (verify-first 方法论验证)
- 文件: `backend/app/api/v1/graph.py`、`frontend/src/stores/graph.ts`、`frontend/src/pages/Home.vue`
- 验证步骤（按 `.planning/VERIFY_FIRST_METHODOLOGY.md`）：
  1. ✅ 写验收标准（`01-01-TASK3-VERIFICATION.md`）
  2. ✅ 检查源码修复已落地
  3. ✅ 重启后端 + 前端容器
  4. ✅ Playwright 截图 → `tests/e2e/investigations/ux/home_after_verify.png`
  5. ✅ 控制台 0 errors, 无 ErrorBoundary
  6. ✅ KPI 显示正确（"岗位数 70 / 图谱节点（含历史）" tooltip 生效）

### Task 4: Home.spec.ts 测试增强 ✅
- 文件: `frontend/src/pages/__tests__/Home.spec.ts`
- 新增 5 个测试用例（4→9）：
  - KPI 总计在 independentPositions=0 时正确显示
  - positionsByKA 整体替换触发 Vue 响应式更新
  - API 错误时显示用户友好提示而非静默失败
  - 独立计数 0 不回退到 domains 聚合
  - (原有 4 个 loading/empty/populated/no-crash 全部保留)
- 验证结果: `9 passed (9)` ✅

---

## 修改的文件清单

| 文件 | 改动 | 验证 |
|------|------|------|
| `docs/archive/home-source-analysis.md` | 新建（任务1） | ✅ |
| `docs/archive/home-optimization-design.md` | 新建（任务2） | ✅ |
| `.planning/phases/01-home-module/01-01-TASK3-VERIFICATION.md` | 新建（任务3验收标准） | ✅ |
| `frontend/src/pages/__tests__/Home.spec.ts` | 新增 5 测试 | ✅ 9/9 通过 |
| `frontend/src/stores/graph.ts` | Task 3 修复已存在 | ✅ |
| `frontend/src/pages/Home.vue` | Task 3 修复已存在 | ✅ |
| `frontend/src/components/Graph3D.vue` | 依赖修复（3d-force-graph 安装） | ✅ |

## 验证证据

### 截图证据
- `tests/e2e/investigations/ux/home_after_verify.png` — 修复后全景图谱页面
  - KPI 显示 12 / 70 / 259 / 13
  - 岗位数 tooltip: "图谱节点（含历史）"
  - 3D 图谱节点渲染正常
  - 0 console errors

### API 证据
- `GET /api/v1/graph/overview?group_by=domain` → total_positions=70, total_skills=393
- `GET /api/v1/positions` → total=39
- `GET /api/v1/admin/stats` → total_positions=56

### DB 证据
- `SELECT COUNT(*) FROM position_records` → 56 (39 approved + 17 pending_review)
- Neo4j `MATCH (p:Position) RETURN count(p)` → 70

## 已知遗留（未在本 Phase 修复）

| 项 | 优先级 | 建议处理 |
|----|--------|---------|
| 70/56/39 口径统一 | P3 | Phase 2 后续 |
| Home 页搜索 API 全局化 | P2 | 后续 Phase 独立 |
| LOD 增强（500+ Position 性能） | P4 | Phase 2 |
| 演化路径高亮 | P1 | Phase 4 |

## 后续动作

1. 执行 `/gsd-execute-phase 2` — 岗位列表模块
2. 执行 `/gsd-execute-phase 3` — 数据流水线模块（用同样的 verify-first 方法论）
3. 03-01-PLAN.md 已规划，包含本次未验证的 DAG 修复验证（重启前端后截图）

---

**Phase 1 完成。** 详见 `.planning/SESSION_GAP_ANALYSIS_2026-07-25.md` 了解本次会话的完整 gap 分析。
---

## Phase 13 增量（4 视图真实化，2026-07-27）

### 闭环 8 步
- **Step 1**: 改 `fetch_overview_by_domain` fallback 为 industry 归一（13 大行业，对标 spec 5.3 表 700-712）
  - 文件: `backend/app/services/graph_overview.py`（新增 `INDUSTRY_KEYWORDS/INDUSTRY_COLORS/INDUSTRY_ID_PREFIX/_classify_industry`）
  - 验证: domain 端点返 9 个行业桶（互联网/IT 32 / 云计算 4 / 后端 3 ...），与 tech_stack 真正不同
- **Step 2**: 新增 `fetch_overview_by_heat`（按技能需求频次降序 Top 30，颜色按 `HEAT_COLOR_RAMP` 蓝→深紫）
  - 验证: Docker 34 / Git 34 / Python 28 / Linux 24 / K8s 15 / PG 15 / REST API 13 / Redis 11 / SQL 10
  - 文件: `backend/app/services/graph_overview.py`（追加 `HEAT_COLOR_RAMP/_heat_color/fetch_overview_by_heat`）
  - 修复: `backend/app/api/v1/graph.py` route dispatch 错把 heat fall back 到 domain
- **Step 3**: Seed 12 行业 KnowledgeArea + 56 Position 软关联（单事务 UNWIND + MERGE）
  - 文件: `backend/scripts/seed_knowledge_areas.py`（幂等 + 单事务）
  - 验证: cypher 18 个 KA + 56 条 BELONGS_TO
- **Step 4**: 4 端点单测（`test_overview_dimensions.py` 9 个测试全过）
  - 200/基本字段/无悬空边（M2）/3 维泡含 junior 兜底（Step 5）/domain ≠ tech_stack 互不子集/heat 降序
- **Step 5**: `fetch_overview_by_level` 末尾兜底 lv-junior 0/0/0 维度泡（PG 无"初级"时也保满 3 维）
- **Step 6**: 前端 4 radio 切换（`OverviewMode = 'domain'|'tech_stack'|'level'|'heat'`）
  - 文件: `frontend/src/stores/graph.ts` + `pages/Home.vue` + `components/HomeGraphControls.vue`（加"热度"按钮）
  - KPI 卡片：Home.vue `groupLabel` 加 heat 分支（'热度视图' / '技能需求频次 Top 30'）
- **Step 7**: 4 视图后端端点验证（Vite 已知 504 循环暂未跑 Playwright 截图，下次 refresh 后补）
- **Step 8**: 文档同步（本节）

### verify-first 三层证据
| 端点 | domains 数 | conns | 悬空边 | 模式独有 |
|---|---|---|---|---|
| `group_by=domain` | 9 | 6 | 0 | industry 13 类（互联网/IT 32 岗最大） |
| `group_by=tech_stack` | 13 | 16 | 0 | 技术栈类（人工智能 7 岗最大） |
| `group_by=level` | 3 | 2 | 0 | junior 兜底 = 1（pos=1）/ mid=45 / senior=11 |
| `group_by=heat` | 30 | 10 | 0 | 按需求频次降序 Top 30（Docker 34 最大） |

### 偏差纠正
- **M6 偏差**: 关系边总 KPI（11 vs 582 同名异值）已修（use independentEdges 统一）
- **M2 偏差**: 所有端点 0 悬空边（_prune_connections 在 graph_overview + graph_service 双重）
- **新增偏差**: 端点 13/14 双集合（domain vs tech_stack）真正不同（不再 tech_stack fallback 占位 domain）
- **原 0/0 灰色问题**: 客户端 ≤1 桶灰色已被 heat 端点解决（30 个 skills 永久显示）
- **level 视图初/中/高 = 0/0/0**: 兜底后保满 3 维
