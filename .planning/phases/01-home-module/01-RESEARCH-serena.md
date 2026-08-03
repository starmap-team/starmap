# RESEARCH.md — Phase 1 4 视图真实化（Serena 代码研究）

**Date:** 2026-07-27
**Method:** `mcp__serena__find_symbol` 读 3 个核心符号 + `mcp__serena__get_symbols_overview` 读 4 个文件

---

## 1. 后端 — 3 端点当前实现

### `fetch_overview_by_domain` (graph_service.py:184)
- **路径**：优先 `MATCH (ka:KnowledgeArea)` → 若 KA 不存在则 fallback 到 `_classify_tech_stack`（行业→ts-*）
- **fallback 行为**：13 个 `ts-ai`/`ts-bigdata`/`ts-bigdata`/`ts-frontend`/.../12 个 tech_stack 桶（与 `fetch_overview_by_tech_stack` 同源）
- **关键颜色映射** `_domain_colors` 已含 spec 13 大行业（人工智能、AI/机器学习、数据科学、数据工程、数据库与存储、前端工程、前端开发、后端架构、后端开发、云计算、DevOps、云原生与基础设施、大数据、网络安全、编程语言与框架、游戏开发、移动开发、测试、嵌入式与物联网、项目管理与协作、设计、区块链与Web3、其他、其他技能领域、AI与机器学习、云原生）
- **现有 color 共 22 项**，与 13 大行业 1:1 不全
- **现有 level_id prefix**：`{"人工智能": "ts-ai", "大数据": "ts-bigdata", ...}` 全是 `ts-*` 命名

### `fetch_overview_by_level` (graph_overview.py:309)
- **等级定义**：`LEVEL_COLORS` 包含 3 个 key（初级/中级/高级）
- **核心 bug**：`for level, data in groups.items(): if not data["positions"] and not data["skills"]: continue` → **空组直接跳过**，lv-junior 永远不出现
- **位置命名映射** `level_id`：`{"初级": "lv-junior", "中级": "lv-mid", "高级": "lv-senior"}`
- **位置分类** `_classify_level`：用 `name` + `props["level"]` 字段分类，PG 中 Position.level 为 NULL 时 fallback 关键词（"高级"/"资深"/"senior"/"专家"/"架构师" → 高级；"初级"/"实习"/"junior"/"助理" → 初级；else → 中级）
- **根本原因**：PG 中 Position.level 几乎全为 NULL → 全部落 else → 中级；高级仅匹配 "架构师/资深"等关键词
- **connections**：硬编码 `level_connections = [{初级→中级}, {中级→高级}]` — 若 lv-junior 不存在则 0 兜底连接
- **`_prune_connections` 已应用**（R1 修复）

---

## 2. 前端 — graph store

### `OverviewMode` 类型（line 47）：`'domain' | 'tech_stack' | 'level'`
- **缺 `'heat'`** — spec 要求的第四视图无对应端点

### `visibleNodes` (line 142)
- **domain 分支**：`domains.value.map(...)` — 依赖 `domains` 数组（fetch_overview_by_domain 的输出）
- **position/detail 分支**：`positionsByKA.value.get(expandedKAId.value)` + `nodeMap.value.get(...)`

### `visibleEdges` (line 185)
- **已加 R2 修复**：domain 分支按 `domains.id` 集合过滤 `domainConnections`，防悬空
- **未应用 R1.5**（filter level connections by level domains）：当前 level 分支 hardcoded `level_connections` 用了 `level_id.get(...)` 但 `_prune_connections` 兜底

### `fetchOverview` (line 221)
- 当前只 fetch 3 个端点
- 需扩展为 4 个（`group_by=heat`）

### `overviewMode` 默认值（line 120）：`'domain'`

---

## 3. 前端 — Graph3D.vue 关键符号（深度 1）

### `initGraph` 已知
- 创建 `ForceGraph3D` 实例
- `linksForNodes` 已在 R4 修复（始终按 `nodeIds` 过滤）
- `_lastNamespace` + `_destructor()` 重建逻辑已就位（R3）
- 错误处理：try/catch + console error

### watch 监听
- `[props.nodes, props.links, props.showEvolution, props.evolutionPaths, props.currentDomainId, props.currentLayer]`
- 触发条件：命名空间变化 → 销毁 + 重建实例
- 当前 `graph3DLinks` 来源 = `graphStore.visibleEdges` → store 已含 level 维度（3 桶可能仅 2 桶）→ 传给 Graph3D 后会渲染空域

---

## 4. 实现约束总结

| 改动 | 文件 | 影响面 |
|------|------|--------|
| 改 fallback 为 industry 归一（按 spec 13 大行业） | graph_service.py:fetch_overview_by_domain | 1 端点 |
| 新增 heat 端点 | graph_overview.py + graph.py | 1 文件 + 1 路由 |
| 新增 KA 12 节点种子 | backend/scripts/ | 1 新文件 |
| level-junior 兜底（PG 无数据时 0/0 占位） | graph_overview.py | 1 函数内 |
| 前端 4 radio + KPI 动态 | Home.vue + store + composable | 5+ 文件 |
| 单测 | test_overview_dimensions.py | 1 新文件 |

---

## 5. 已查的同源路径

- `_prune_connections(connections, domains)`：4 端点均用（level/tech_stack/domain）
- `_fetch_independent_counts(driver)`：全局单次查询
- `LEVEL_COLORS` 已 3 个 key
- `TECH_STACK_COLORS` 已 12 个 key
- `_classify_tech_stack(industry, name)` 复用

---

## 6. Serena 工具限制

- `find_symbol` 不支持 `name_path_pattern` 与 `relative_path` 组合搜索非 Python 文件（graph.ts 是 TS）
- `get_symbols_overview` 对 TS 文件 OK，但只列顶层符号
- 通过 Grep 补充实现细节

---

*研究完成。下一步：直接进入实现（按 `plans/panorama-graph-views-blueprint.md` 8 步执行，verify-first 闭环）。*