---
title: 准确设计 — 全景图谱三视图维度（对标 /docs）
date: 2026-07-26
owner: Phase 1 (Home)
spec_basis: docs/ontology/starmap-ontology-v1.md, docs/星图-项目设计文档v2.0.md, docs/architecture/overview.md, docs/standards/04-contracts/01-API契约规范.md
---

# 准确设计：全景图谱三视图维度（对标 /docs）

## 1. 对标 `/docs`：设计要求 vs 现状

### 1.1 原始设计要求（真值源）

`docs/ontology/starmap-ontology-v1.md`：
- **本体三层级树**：`领域(Domain) → 子领域(Subdomain) → 具体技能(Skill)`。
- **12 个 KnowledgeArea（领域）**：编程语言 / 前端开发 / 后端开发 / 数据库 / 云原生 / AI·机器学习 / 数据工程 / DevOps / 安全 / 移动开发 / 测试 / 项目管理 + 通用软技能。
- `import_neo4j_schema.py` 应定义 **8 种关系类型 + 12 个 KnowledgeArea 节点**。
- 关系：`Skill —BELONGS_TO→ KnowledgeArea`（必连至少 1 个）。

`docs/星图-项目设计文档v2.0.md`：
- 模块 C 全景图谱 = **知识领域层级图**（核心不是技术栈）。
- 第 713-715 行明文要求三种视图：
  - **技术栈视图**：按 AI/大数据/物联网等分组。
  - **级别视图**：初级/中级/高级。
  - 隐含第三维：**知识领域视图**（主视图）。
- 第 1428+ 行：左侧筛选器 = 技术栈 + 级别；右上是图谱本体。

`docs/standards/04-contracts/01-API契约规范.md` M2：**404 仅用于“资源真不存在”；“资源存在但暂无可用画像/数据”须返回 200 + 解释字段，禁止与 not-found 混用**。
M6：**同一业务量在不同端点/页面须同口径或显式标注口径差异**；聚合字段不得与去重计数同名混用。

### 1.2 现状（实测，Phase 5 重建 Neo4j 之后）

| group_by | domains | 备注 |
|---|---|---|
| `domain` | **12 个 `ts-*`** | ids 全是 `ts-ai/ts-bigdata/...`（**与 tech_stack 一模一样**） |
| `tech_stack` | **12 个 `ts-*`** | 同上 |
| `level` | **2 个**（`lv-mid`, `lv-senior`） | 缺 `lv-junior`；connections 含指向 `lv-junior` 的**悬空边** |

控制台实证（切到级别时）：
```
Error: node not found: lv-junior
    at find (3d-force-graph.js)
    at force.links
    at comp.update
```

### 1.3 差距（对标结论）

| 设计要求 | 现状 | 差距 |
|---|---|---|
| 三维度独立（领域 / 技术栈 / 级别） | domain ≡ tech_stack（回退到 `_classify_tech_stack`） | **缺"知识领域"维度** |
| level = 初级/中级/高级 | 只有 mid/senior | **缺初级** |
| 关系不得引用被省略节点（M2） | level 返 `lv-junior` 边 → 节点缺席 | **悬空边**（真因） |
| 视图切换不破坏状态 | 3d-force-graph 实例污染 | **实例不复用/stale pos/links** |
| 节点规模差异下视觉合理 | 两团=一个大球 | **nodeVal 线性放大** |

根因（已锁定、有证据）：
- **R1** 后端 `fetch_overview_by_domain` 在 Neo4j 0 KA 节点时**回退到 `_classify_tech_stack`**，与 `tech_stack` 视图**完全等价**。
- **R2** 后端 `connections` 含被 `domains` 过滤掉的空组之边（如 `lv-junior`），违反 M2。
- **R3** 前端 `Graph3D.vue` 的 `watch` 在 mode 变化时仅 `graphData()` 更新数据，但**实例状态（位置/链接索引/sim 缓存）不复位**，导致 3d-force-graph 在悬空边处抛错并留下坏状态。
- **R4** 前端 `visibleEdges`（domain 分支）原样透传 `domainConnections`，未按当前 `domains` id 过滤；`limitedLinks` 在 `maxNodes=0` 时也直接 `return props.links` 不过滤，**双重纵深缺口**。
- **R5** 级别视图仅 2 组，节点半径按 `position_count` 线性放大到 45/11 → 两大球贴在一起，UX 偏差。
- **R6** 缺"知识领域（KnowledgeArea）"维度本身：Neo4j 0 KA 节点，需投影或虚拟分类（见下）。

---

## 2. 准确设计：分层契约与数据流

### 2.1 三个维度的语义与权威源（必须三独立）

| 维度 | 后端 group_by | 数据源 | 输出 domain.id 命名 | 权威来源 |
|---|---|---|---|---|
| **领域 (domain)** | `group_by=domain` | KnowledgeArea/Subdomain 树（ontology v1 12 个） | KA 节点 `elementId` | `docs/ontology/starmap-ontology-v1.md` |
| **技术栈 (tech_stack)** | `group_by=tech_stack` | `_classify_tech_stack(industry, name)` 关键字 | `ts-<stack>` | `docs/星图-项目设计文档v2.0.md:715` |
| **级别 (level)** | `group_by=level` | Position.经验要求 + 名称推断 | `lv-junior/mid/senior` | `docs/星图-项目设计文档v2.0.md:715` |

**三维度必须互不依赖**（任一变更不影响其他维度的领域集合），且三者均按"非空"过滤（空组不出现在 `domains`，且其所有 incident 边必须从 `connections` 中剔除 —— M2 契约）。

### 2.2 后端设计（graph_service / graph_overview）

#### 2.2.1 `domain` 维度（核心修复）

`fetch_overview_by_domain(driver)` 改造：
- 路径 A（首选，KA 已建）：`MATCH (ka:KnowledgeArea)<-[:BELONGS_TO]-(s:Skill)<-[:REQUIRES]-(p:Position) ...` 按 KA 分组（路径 A 维持现有正确性）。
- **路径 B（KA=0 回退，按 ontology v1 十二个领域名分类）**：实现 `_classify_domain(name, industry) -> str`：
  - 输入：`name` 字符串 + `industry` 字符串。
  - 关键词表（初版，可后续扩展）：编程语言 / 前端 / 后端 / 数据库 / 云原生&DevOps / AI / 数据工程 / 安全 / 移动 / 测试 / 管理 / 其他。
  - 来源：`docs/ontology/starmap-ontology-v1.md:73-89` 的 12 个领域 + 子领域关键词映射。
  - 兜底：`其他`。
- 输出的 `domain.id` 用 `ka-<slug>`（如 `ka-frontend`），与 tech_stack 的 `ts-*`、level 的 `lv-*` 命名空间**严格不冲突**。

#### 2.2.2 `level` 维度

`_classify_level(name)` 保留 3 类：`junior` / `mid` / `senior`（按 design 1428+ 行："初级/中级/高级"）。**当前 mid/senior 二分改为三分**。

#### 2.2.3 `tech_stack` 维度

保持现状（`_classify_tech_stack`），无改动。

#### 2.2.4 连接完整性（M2 契约，所有维度共有的硬约束）

每个 `fetch_overview_by_*` 函数在**返回前**执行（不依赖调用方）：

```python
# pseudo
domain_ids = {d["id"] for d in domains}
connections = [c for c in connections
               if c["source_id"] in domain_ids and c["target_id"] in domain_ids]
```

并对 `domains[i].id` 同样使用合法命名空间（`ka-/ts-/lv-`），避免 cross-namespace 误判。

### 2.3 前端设计（stores/graph / composables / components）

#### 2.3.1 `stores/graph.ts` 修复

```ts
// visibleEdges domain 分支 —— M2 / R4 修复
const visibleEdges = computed(() => {
  if (currentLayer.value === 'domain') {
    const validIds = new Set(domains.value.map(d => d.id))
    return domainConnections.value
      .filter(c => validIds.has(c.source_id) && validIds.has(c.target_id))
      .map(c => ({ source_id: c.source_id, target_id: c.target_id, type: c.type, properties: c.properties }))
  }
  // 其它分支保留
})
```

> 关键点：在 **store 层过滤**，所有消费方（Graph2D、Graph3D、position/detail 视图）一次性收益；不再让 3d-force-graph 自己 throw。

#### 2.3.2 `Graph3D.vue` 视图模式变化时强制重建实例（核心 R3 修复）

修改 `watch(() => [props.nodes, props.links, ...])`：
- 检测**节点 id 集合变化**（用 `oldIds: Set<string>` 与 `newIds: Set<string>` 对比；任一 id 增/减或维度切换 → "dimension 改变"）。
- 若 **dimension 改变**（group_by 变化 → 节点 id 命名空间切换如 `ts-` ↔ `ka-` ↔ `lv-`）：**重建图实例**——`graph._destructor?.(); graphInstance.value = null; await initGraph();` 而不是 `graph.graphData(...)`。
- 若仅数据增/减但 dimension 一致：`graph.graphData({nodes, links})` + 位置继承（保留 posMap 继承逻辑），不变。

#### 2.3.3 `Graph3D.vue` `linksForNodes` 防御性过滤

把 `maxNodes=0` 路径的"直接 return props.links"改为始终过滤：

```ts
function linksForNodes(links, nodes) {
  const ids = new Set(nodes.map(n => String(n.id)))
  return links.filter(l => ids.has(endpointId(l.source)) && ids.has(endpointId(l.target)))
}
```

`limitedLinks`（line 170）也走该函数 → maxNodes=0 也不漏过滤。

#### 2.3.4 节点规模视觉（级别两团重叠修复 R5）

- `getNodeRadius(node)` 在**分组少时**封顶：`radius = min(base, log(position_count+1) * scale + base)`（对数而非线性）。
- 同时 `applyForceConfig`（`useGraph3D`）在 `nodeCount <= 5` 时**加大 link distance 与 charge strength**（避免大球互压）。
- 这些为视觉调优，不改数据。

### 2.4 数据流总图（修复后）

```
[Neo4j] → graph_service.fetch_overview_by_{domain|tech_stack|level}
         ├─ 维度语义互独立（按 §2.1）
         ├─ domains 按"非空"过滤
         └─ connections **强制**按保留的 domain_ids 过滤（M2 契约层）  ← R2
              ↓
[GET /api/v1/graph/overview?group_by=*]
              ↓
[stores/graph.ts] fetchOverview → domains.value / domainConnections.value
              ↓
visibleEdges  computed：**按当前 domains.id 过滤**  ← R4
              ↓
Graph2D / Graph3D  props.nodes / props.links（已无悬空）
              ↓
Graph3D  watch：dimension 改变 → 重建实例；否则 graphData+继承  ← R3
```

### 2.5 验收标准（verify-first）

| 编号 | 验收 |
|---|---|
| A1 | `curl /api/v1/graph/overview?group_by=domain` 返回的 domain.id 全部以 `ka-` 开头，且与 `tech_stack` 视图**完全不同**（集合差 > 0） |
| A2 | `curl ...?group_by=level` 返回的 domain.id 集合 ⊃ `{lv-junior, lv-mid, lv-senior}` 的子集；**3 类 ≤**；且 `connections` 中任一端点 id 都在该 `domain.id` 集合中（无悬空） |
| A3 | Playwright 切到 3D，分别点 领域 / 技术栈 / 级别 三个 radio，**console 无 `node not found` 报错**；每个视图下 graph canvas 中**可见节点数与该视图 domains 数一致**；切回 上一视图不报 `lv-junior` 之类 |
| A4 | `docs/ontology` 仍为唯一真理源；不复制其内容到 frontend |
| A5 | 单元：`test_graph_services.py` 现有断言不破；新增 case：`fetch_overview_by_level` 返回 3 类（若 PG 实际只 2 类，先种 1 条 junior 级别） + `connections` 端点 ⊂ `domain.id` 集合 |
| A6 | lint：ruff + eslint 通过 |

---

## 3. 实施分阶段

### Phase A（最小修复，1 天内）
- A1: 后端 `connections` 完整性过滤（R2 硬约束，M2 契约）—— **必修**
- A2: 前端 `visibleEdges` + `linksForNodes` 防御性过滤（R4）—— 必修
- A3: `Graph3D.vue` watch 在 dimension 变化时重建实例（R3）—— 必修
- A4: `level` 维度补 `junior` 类—— 一行 if 改动
- A5: 节点半径对数封顶 + 少量节点 force 增强（视觉 R5）—— 可选

### Phase B（领域维度落地，1–2 天）
- B1: 写 `docs/ontology/domain_keywords.yaml`（从 ontology v1 12 领域关键词生成首版）
- B2: 后端 `_classify_domain(name, industry)` + `fetch_overview_by_domain` 改用 → 三维度互不依赖
- B3: 端到端验证：domain 视图与 tech_stack 视图**显著不同**（截图 + 节点数对比）

### Phase C（数据层重建，2+ 天，单独 phase）
- 在 Neo4j 中真正创建 12 个 KnowledgeArea 节点 + Subdomain + `BELONGS_TO` 关系（按 ontology v1）。
- 改 `fetch_overview_by_domain` 走路径 A（按 KA 分组），回退路径 B 保留（容错）。
- 改 `import_neo4j_schema.py` / 重建脚本（与 Phase 5 解耦）。

> **当前会话**只跑 Phase A 即可解决 3 个用户报告的 3D 缺陷（悬空边 + 持续错误 + level 重合），并把数据契约层修正。Phase B/C 是数据/产品层面，按 `gsd-plan-phase` 立项。

---

## 4. 对应到现状的 fix 清单

| 缺陷 | 设计章节 | 修复位置 |
|---|---|---|
| ① domain ≡ tech_stack | §2.2.1（路径 B） | `graph_service.py::fetch_overview_by_domain` + `graph_overview.py::_classify_domain`（Phase B） |
| ② 级别视图重合 / 节点规模视觉 | §2.2.2 + §2.3.4 | `_classify_level` 补 junior + `getNodeRadius` 对数封顶 |
| ③ 切到级别后持续渲染错误 | §2.3.2 + §2.2.4 | 后端 connections 过滤 + `Graph3D.vue` watch dimension 检测重建 |

---

## 5. 与既有 spec 的一致性

- 满足 `standards/04-contracts` M1（路径参数类型保真——`source_id`/target_id/`domain_id` 必须为合法命名空间内 UUID/字符串）+ M2（404 与无画像区分）+ M6（口径单一，无悬空边）。
- 满足 `standards/02-frontend/05-页面组件规范` 中"组件须可独立验证、可视化正确" 的隐含要求。
- 满足 `standards/04-contracts` M7 verify-first：每改一处必须截图+API+DB 三层证据。

---

## 6. 风险与回退

- **风险 R3** 重建图实例在动画期间可能闪烁。**缓解**：销毁旧实例时先取消 growth animation 计时器（已存在 `cancelGrowthAnimation`），再重建；视觉差异 ≤ 0.3s。
- **风险 B1** 关键词表首版会漏分类（错到"其他"）。**缓解**："其他"桶在 UI 上明确标灰并加 tooltip "该岗位未匹配到已知领域关键词"，便于人工后续补关键词。
- **回退**：所有修复按 `git diff` 评估；前后端均保持旧行为开关（`FF_GRAPH_DOMAIN_V1` 之类的 env 标志），默认开新逻辑，紧急时可一键回退。
