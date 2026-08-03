# 蓝图：全景图谱维度真实化 + 四视图补全

**目标**：让 Home.vue 领域视图 ≠ 技术栈视图；级别视图补齐初级节点；补热度视图。
**对标**：`docs/星图-项目设计文档v2.0.md:713-718`（4 视图显式要求）、`docs/ontology/starmap-ontology-v1.md:53`（领域→子领域→技能三层树）、`docs/星图-项目设计文档v2.0.md:368`（Position.level 字段）、`docs/星图-项目设计文档v2.0.md:439-450`（Skill→KA 必属关系 + 12 KA 节点）。
**范围**：后端 domain 端点 + Neo4j KA 节点种子 + level 端点补 lv-junior + heat 端点；前端分组切换 UI。
**不在范围**：Phase B 的 industry 归一表（独立 PR 后续处理）；G6 → 3d-force-graph 切换重构（独立 phase）。

---

## 依赖图与并行度

```
Step 1 ─┐
Step 2 ─┼─ Step 3 (mermaid-domain-import) ─┐
Step 4 ─┤                                   ├── Step 6 ── Step 7 ── Step 8
        Step 5 (level-junior)  ──────────────┘
```

并行：Step 2 (按 industry 聚类端点) 与 Step 3 (KA 节点种子) 可并行；Step 5 (level 补 junior) 需等 Step 1。  
串行：Step 6 (前端切换 UI) 需 Step 2/3/5/4 全部就绪；Step 7 (3 视图截图回归) 需 Step 6；Step 8 (luma 文档) 在最后。

---

## Step 1: 后端 — `fetch_overview_by_domain` 真领域（按 industry 聚类）

**Context brief**：当前 `fetch_overview_by_domain` 因 Neo4j 无 KA 节点 → fallback tech_stack 分类（domain ≡ tech_stack 根因）。改为按 `Position.industry` 聚类 — 是 spec 业务层 12 大行业（互联网/AI/金融/医疗…）而非 IT 技术栈。industry 字段 PG 已有（见 schema:1）。

**Files**：
- `backend/app/services/graph_service.py`（改 `fetch_overview_by_domain`）
- `backend/app/api/v1/graph.py`（端点已就位）

**Tasks**：
1. 验证 PG 现有 `Position.industry` 取值集合（跑 `SELECT DISTINCT industry FROM position_records WHERE industry IS NOT NULL`）
2. 实现 `fetch_overview_by_domain`：用 tech_stack classifier 改用 industry 归一映射（13 大行业 dict），无 industry 的归"其他"
3. 复用 `_prune_connections` 过滤悬空边
4. 返回 `domains: [{id, name, color, position_count, skill_count}]`

**Tier**：default（haiku）。变更小。

**Verification**：
```bash
curl /api/v1/graph/overview?group_by=domain
# 期望：domains 数 12-13（按 industry 聚类，与 group_by=tech_stack 的 ts-* 列表显著不同）
```

**Exit criteria**：domain 视图的 domain 列表 ≠ tech_stack 视图的 domain 列表。

---

## Step 2: 后端 — `fetch_overview_by_heat` 热度视图（frequency 热力图色阶）

**Context brief**：spec § 3.3.3 行 717：「热度视图：按技能需求频率着色（热力图模式）」。当前无该端点。需求频率 = 多少 Position 通过 REQUIRES 引用该 Skill。

**Files**：
- `backend/app/services/graph_overview.py`（新增）
- `backend/app/api/v1/graph.py`（注册路由 + 响应 schema）

**Tasks**：
1. 新增 `fetch_overview_by_heat`：扫所有 `(:Position)-[:REQUIRES]->(:Skill)` 按 Skill 频次统计；返回 domains 用频次桶（高频/中频/低频）配色（红/黄/蓝）
2. skill 出现 0 次的归"低频"占位（不可见但保留在 KPI 计数里）
3. connections 节点 = Skill（同维度，连接用 REQUIRES 自然形成）

**Tier**：default（haiku）。

**Verification**：
```bash
curl /api/v1/graph/overview?group_by=heat
# 期望：domains 含 frequency 字段；KPI 显示"高频技能 TOP 5"
```

**Exit criteria**：热度视图组件能正常加载并按频次着色。

---

## Step 3: 数据 — Neo4j KnowledgeArea 12 节点种子脚本

**Context brief**：spec 11-13 领域节点 + ontology v1 § 1 列了 12 个 KA 名称（编程/前端/后端/数据库/云原生/AI/数据工程/DevOps/安全/移动/测试/项目管理）。当前 Neo4j 无 KA 节点 → fetch_overview_by_domain fallback → domain≡tech_stack。

**Files**：
- `backend/scripts/seed_knowledge_areas.py`（新建）
- `backend/scripts/neo4j_seed_runner.py`（若已存在则用其入口；否则新建）

**Tasks**：
1. 从 `docs/ontology/starmap-ontology-v1.md:73-89` 复制 12 领域名+description+parent_area 到硬编码 dict
2. 用 `MERGE (ka:KnowledgeArea {name: $n}) SET ka.description=..., ka.parent_area=..., ka.color=...` 幂等种子
3. 用 `MATCH (p:Position) WHERE p.industry CONTAINS 'AI' OR p.industry CONTAINS '技术' MATCH (ka:KnowledgeArea {name:'AI/机器学习'}) MERGE (p)-[:BELONGS_TO]->(ka)` 给 Position 挂 KA（软关联，不要求完整覆盖；缺挂的归"未分类"）
4. 让 fetch_overview_by_domain 优先走 KA 路径（fallback 仍保留 tech_stack）

**Tier**：default（haiku）。幂等脚本。

**Verification**：
```bash
docker exec starmap-neo4j cypher-shell -u neo4j -p starmap123456 \
  "MATCH (ka:KnowledgeArea) RETURN count(ka)"
# 期望：12
curl /api/v1/graph/overview?group_by=domain
# 期望：domains=12（按 12 领域），与 tech_stack 不再相同
```

**Exit criteria**：domain 端点返回 12 个 KA 节点（按 spec），与 tech_stack 端点的 12 个 ts-* 完全不同。

---

## Step 5: 后端 — `fetch_overview_by_level` 补初级节点 lv-junior

**Context brief**：当前 level 视图只有 `lv-mid`（45 岗）和 `lv-senior`（11 岗）—— `lv-junior` 因 PG 中无 Position.level='初级' 名称被过滤。spec 12-13 行：「初级 5 岗」 期望补齐。

**Files**：
- `backend/app/services/graph_overview.py`
- `backend/app/api/v1/graph.py`

**Tasks**：
1. 验证 PG `SELECT level, COUNT(*) FROM position_records GROUP BY level` — 找到有"初级"还是没
2. 如果有"初级"Position 但 fetch_overview_by_level 漏了：检查 `_classify_level` 与 `LEVEL_COLORS` 映射 + `level_id`
3. 兜底：若 PG 真无"初级"Position（只有"中级"/"高级"），在 `fetch_overview_by_level` 兜底返回 `lv-junior` 域 pos=0 skill=0 灰占位（spec 列 12 视图完整性 > 真实数据）
4. `level_id` mapping + `LEVEL_COLORS` 全部完整（junior/mid/senior）保持原样，不改 UI 文本

**Tier**：default。

**Verification**：
```bash
curl /api/v1/graph/overview?group_by=level
# 期望：domains 3 个（lv-junior, lv-mid, lv-senior），不再仅 2 个
```

**Exit criteria**：级别视图在 3D/2D 都有 3 个域泡（即使 junior 0/0 占位也算 spec 合规）。

---

## Step 4: 后端 — `total_skills` 取值 + `fetch_overview_by_tech_stack` 一致性

**Context brief**：本 step 顺带把 Step 1-3 引入的 domain 视图与已有 tech_stack 视图放一起回归一遍 — 确保 frontend Home.vue 切换时 3 个端点（domain/tech_stack/level）独立返回不同结构。

**Files**：
- `backend/tests/test_overview_dimensions.py`（新建单元测试）

**Tasks**：
1. 单测 fetch_overview_by_domain 返回 12 个领域（按 industry ），按颜色 hex
2. 单测 fetch_overview_by_tech_stack 返回 12 个 ts-*（按 tech_stack 分类）
3. 单测 fetch_overview_by_level 返回 3 个 lv-*（包括 junior 占位）
4. 单测 fetch_overview_by_heat 返回频率域
5. 单测所有端点：connections 中所有端点都在 domains 列表中（无悬空）

**Tier**：default。

**Verification**：`pytest backend/tests/test_overview_dimensions.py -v` 全绿。

**Exit criteria**：4 端点互不重复 + 无悬空边回归测。

---

## Step 6: 前端 — Home.vue 三视图切换 UI + 第四视图占位

**Context brief**：当前 HomeGraphControls 有领域/技术栈/级别三个 radio。需改为领域/技术栈/级别/热度（4 选 1），与后端 4 端点对齐。

**Files**：
- `frontend/src/pages/Home.vue`（分组切换 + 文案）
- `frontend/src/composables/home/useGraph3DData.ts`（按 group_by 切换 4 路 data source）
- `frontend/src/composables/home/useGraph2DData.ts`（同理）

**Tasks**：
1. HomeGraphControls 第三个 radio "级别" 之后加第四个 "热度"
2. store `graphStore.overviewMode` 类型扩展为 `'domain' | 'tech_stack' | 'level' | 'heat'`
3. fetchOverview 根据 mode 选端点；前端 3D/2D 数据按 mode 切换
4. KPI 卡片根据 mode 显示不同 label（领域视图=12 领域；技术栈=12 栈；级别=3 级；热度=需求频次 Top）
5. tooltip 复用 M5 已加的 口径 说明

**Tier**：default。

**Verification**：手动跑 Home.vue 切换 4 radio，console 0 error，每视图都有节点渲染（heatmap 用颜色编码显示频率）。

**Exit criteria**：4 视图可正常切换，KPI 文案随视图动态变化。

---

## Step 7: 视觉回归 — 截图四视图

**Context brief**：端到端 verify-first 截图。spec § 3.3.3 要求 4 视图。

**Files**：
- `tests/e2e/investigations/ux/home_view_{domain,tech_stack,level,heat}.png`（4 张截图）

**Tasks**：
1. Playwright 登录 + 进入 Home + 切到领域 + 截图（对比 tech_stack 必须显著不同）
2. 同上切到技术栈截图
3. 同上切到级别（应 3 个域泡）
4. 同上切到热度（heatmap 色阶）
5. 检查 console errors 均为 0

**Tier**：default。

**Exit criteria**：4 张截图互不重复 + 0 error。

---

## Step 8: 文档同步

**Files**：
- `.planning/phases/13-design-conformance/CONFORMANCE-home.md`（更新 4 视图状态）
- `01-UI-REVIEW.md`（更新 6 栏分级 — 视觉一致性、交互完整性从 2 升到 3）
- `DESIGN-graph-views.md`（更新 § 2 实施策略 — 4 视图全就位）

**Tier**：default。

**Exit criteria**：文档与代码同步；引用 4 张新截图。

---

## Rollback Strategy

每个 step 独立 commit + revert。Step 1-2 后端改动是 additive（新增分支），不破坏旧端点。Step 3 种子脚本幂等（`MERGE` 幂等 + `idempotent: true`），重复跑无副作用。Step 5 兜底 `lv-junior` 0/0 占位 = spec 合规，无数据风险。Step 6 前端 radio 扩展是 additive。Step 7 仅截图无代码。Step 8 仅文档。

回滚策略：每 step `git revert <commit>`，Phase 2 (industry 归一表) 仍可独立 PR。

---

## Anti-Patterns to Avoid

- 一次性大批量改 4 视图端点 → 单 PR 难 review + 出问题回滚面积大。**避免**：本蓝图保持 Step 1-8 单 PR 单验证单元。
- 改 `level_id` mapping 文本"初级"→"Entry"等 → **避免**：spec 明确"初级/中级/高级"，改文案破契约。
- 让 Step 1 的 fallback 同时支持 industry 和 tech_stack → **避免**：spec 要求视图互不重复（dimension 排他），fallback 仍应只一份。
- Step 5 在 `lv-junior` 强行塞虚构 Position 满足 KPI 美观 → **避免**：数据完整性 > KPI 美观，0/0 占位是 spec 合规的最佳解。
- 改 backend 4 端点用 4 个新函数 → **避免**：4 端点共 `_prune_connections` 与 `_fetch_independent_counts`，共享 helper。

---

## Estimated Effort

| Step | Effort | Risk |
|------|--------|------|
| 1 domain 端点 | 0.5 day | LOW（仅改 fallback） |
| 2 heat 端点 | 0.5 day | LOW（新端点） |
| 3 KA 种子 | 0.5 day | LOW（幂等脚本） |
| 4 单测 | 0.5 day | LOW |
| 5 level-junior | 0.3 day | LOW（兜底） |
| 6 前端 4 radio | 0.5 day | MED（store 扩展） |
| 7 截图 | 0.2 day | LOW |
| 8 文档 | 0.3 day | LOW |
| **合计** | **3.3 day** | |

---

*Blueprint generated 2026-07-27 by /blueprint. 8 步、5 并行组、估算 3.3 人天。*
