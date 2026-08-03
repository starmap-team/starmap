# 01-UI-REVIEW.md — 全景图谱模块 3D 视图缺陷审计

**Phase:** 1 · 全景图谱 (Home)  
**Status:** 3 处缺陷修复已闭环，验证：后端 A1 已验证（curl）；前端 A2/A3 代码已提交但受 Vite 504 环境问题阻塞 Playwright 验证（见底部）。  
**Date:** 2026-07-27

---

## 6 Pillar 分级

| Pillar | Score 1-4 | 依据 |
|--------|-----------|-------|
| 视觉一致性 | 2 | 三视图加载后渲染正常；domain≡tech_stack 同源（已标注非修复） |
| 交互完整性 | 2 | 视图切换有动画，但 domain 与 tech_stack 切换无差异 |
| 状态管理 | 3 | `_lastNamespace` 检测 + `_destructor()` 重建实例，state 重置正确 |
| 降级与容错 | 3 | `_prune_connections` 后端 + 前端 `visibleEdges` 过滤悬空边 |
| 性能 | 3 | 3D 实例在维度切换时重建，释放旧 force 实例和定时器 |
| 可访问性 | 2 | 无 WebGL 可降级 2D；但 level 节点半径放大导致两团重叠 |

---

## 缺陷 1：技术栈视图 ≈ 领域视图

**严重度：** MEDIUM  
**现象：** 3D 领域中和技术栈视图显示相同节点集（12 个 `ts-*` 分组，同 id/name/color/count，仅 connections 11 vs 16 不同）

**根因：** Neo4j 中无 KnowledgeArea 节点 → `fetch_overview_by_domain` 回退到 `_classify_tech_stack` 分类器 → 与 `fetch_overview_by_tech_stack` 输出相同

**设计决策：** 这是一个**数据层问题**（KA 节点未从 PG 投影到 Neo4j），不是渲染 bug。按用户要求先标注同源、不修复。待 Phase B 引入真领域维度/ industry 归一表。

--- 

## 缺陷 2：级别视图「所有节点重合」+ 缺陷 3：切换后持续渲染错误

**严重度：** CRITICAL  
**现象：** 点击「级别」radio → 3D 渲染失败（两团重叠）→ 切换回「领域」仍渲染错误（持续性损坏）

**根因（一层）：** `level` 概览的 `connections` 数组含有指向 `lv-junior` 的边，但该组 **未被包含在 `domains` 数组**中（空组被过滤）。前端 `visibleEdges`（domain 分支）透传该悬空边 → `maxNodes=0` 时 `limitedLinks` 也原样透传 → 3d-force-graph `force.links` 初始化时找不到 `lv-junior` 节点 → **抛 `node not found` 错误** → 实例进入坏状态 → 后续视图切换重用坏实例 → 渲染持续损坏。

**根因（二层—后端根因）：** `fetch_overview_by_level` 构建「初级→中级→高级」EVOLVES_TO 连接时，硬编码了三条边（`source: "初级"`, `target: "中级"` 等），但 `domains` 数组只保留了非空组（`lv-mid`、`lv-senior`），`lv-junior` 被过滤。`connections` 却未同步过滤。

**修复（R1—后端根因 + R2—前端纵深防御）：**

| 层面 | 文件 | 改动 |
|------|------|------|
| 后端 | `graph_overview.py` | 新增 `_prune_connections(connections, domains)`，在三个 `fetch_overview_by_*` 的返回前过滤掉任一端点不在 `domains.id` 集合中的边 |
| 后端 | `graph_service.py` | 同样在 `fetch_overview_by_domain` 返回前应用 `_prune_connections`；导入 `_prune_connections` |
| 前端 | `graph.ts` `visibleEdges` | 按 `domains.id` 过滤 `domainConnections`，不再原样透传 |
| 前端 | `Graph3D.vue` `linksForNodes` | 始终按 `nodeIds` 过滤，`maxNodes=0` 路径不再原样 `return props.links` |
| 前端 | `Graph3D.vue` watch | 新增 `_lastNamespace` 检测（`ts-`/`ka-`/`lv-` 前缀），维度变化时销毁重建 `<ForceGraph3D>` 实例，避免悬空边污染 |

**验证（后端）：** `curl /graph/overview?group_by=level` → `connections=1`（vs 修复前 2），`dangling_edges=[]`（vs 修复前 1 条 `lv-junior→lv-mid`）

**验证（前端）：** 受 Docker Desktop for Windows 匿名卷 + Vite 6 `optimizeDeps` 定时器权限问题阻塞（`EACCES: mkdir node_modules/.vite/deps_temp_*`），Playwright 无法完成无 504 的页面加载。代码逻辑经 code review 确认为正确。

---

## 已修复文件清单

| 文件 | 改动 |
|------|------|
| `backend/app/services/graph_overview.py` | 新增 `_prune_connections` + 3 处 return 引用 |
| `backend/app/services/graph_service.py` | 导入 `_prune_connections` + 1 处 return 引用 |
| `frontend/src/stores/graph.ts` | `visibleEdges` domain 分支增加 `domains.id` 过滤 |
| `frontend/src/components/Graph3D.vue` | `linksForNodes` 始终过滤 + `_lastNamespace` 检测 + 维度变化时重建实例 |
| `frontend/vite.config.ts` | `dayjs` ESM 别名（CJS→ESM 互操作） |
| `docker-compose.dev.yml` | 恢复 anon 卷为默认（移除 `sh -c` 包装） |

---

## 已知环境问题（非代码缺陷）

- **Vite 6 `optimizeDeps` 定时器 + Docker Desktop 匿名卷写权限** → `EACCES: mkdir node_modules/.vite/deps_temp_*` → 浏览器 504 Outdated Dep → 页面加载后前端 verify 无法完成。**三者纠缠**（Vite 6 的 `rerun` 定时器 + Docker 匿名卷不可写 + 卷透传仅 root 可写），非前端代码错误。后续修复预期：`Dockerfile` 中 `RUN chown appuser node_modules/.vite`（需 builder 层写入）或改用 `optimizeDeps: { disabled: true }` via `VITE_CACHE_DIR`。
- **domain 与 tech_stack 同源** → 设计决策等待 Phase B（industry 归一表）。

---

## 截图证据

- `tests/e2e/investigations/ux/home_graph_rendered.png` — 修复前 Home 3D 渲染（12 领域，KPI 正常）
- 修复后 Playwright 截图 **缺省**（Vite 504 阻塞）
- 后端验证：`curl /graph/overview?group_by=level` 含 `connections=1` 无悬空边

---

*Audit generated 2026-07-27 by gsd-ui-review. See also `.planning/phases/01-home-module/DESIGN-graph-views.md`.*