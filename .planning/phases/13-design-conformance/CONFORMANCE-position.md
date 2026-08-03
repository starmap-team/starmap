# CONFORMANCE — Module 2: 岗位列表/详情 (PositionList + PositionDetail)

**Phase 13 · Wave 1 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/02-frontend/05-页面组件规范.md`、`docs/standards/01-backend/02-API路由层.md`、`docs/standards/04-contracts/01-API契约规范.md`、`docs/ontology/starmap-ontology-v1.md` |
| was-analyzed | `docs/archive/position-source-analysis.md`（2026-07-25，10 项，仅 2 标“已修复”——本次以当前代码复核） |
| is (live) | `frontend/src/pages/PositionList.vue` + `PositionDetail.vue` + `stores/jd.ts` + `/api/v1/positions*`、`/graph/position/{name}/skills` + PG `position_records`/`position_skill_relations` + Neo4j Position |

## 已修复 + 验证
- **[FIXED · HIGH · CONFORM-03]** 公开可见性漂移：`PositionList.vue` 默认 `statusFilter='all'` 且**总**传 `include_all=true`，致非 admin 也取全状态（total=56）且无徽标区分，违背头部注释“public=approved”与后端 `/positions` 默认 approved 契约。修复：`include_all` 仅 `isAdmin` 时发送（`PositionList.vue:127-135`）。**验证**：后端无 `include_all`→**39 全 approved**；admin `include_all=true`→**56**(39+17)；非 admin 现走前者=39（按构造+后端契约组合验证）。
- **[FIXED · MEDIUM · CONFORM-01]** 搜索/行业跨端语义不一致：PG `search` 仅 `name.ilike`、`industry` 精确 `==`；Neo4j `search` 仅 name。前端 placeholder 承诺“名称或行业”。修复：PG `search`→`name OR industry ilike`、`industry`→`ilike` 包含；Neo4j `search`→`name OR industry CONTAINS`（`position.py` PG 两处 + Neo4j 一处）。**验证（python 原生 UTF-8，规避 git-bash 中文损坏）**：`search=互联网` **0→38**；`industry=信息技术/互联网` **→33**；`search=Python` **6**（无回归）；无筛选 **56**。

## 符合项（复核当前代码，纠正归档标记）
- **[CONFORM]** 详情页 PG 路径 `skills_required` 含 `proficiency`（`position.py:188`，由 `requirement_type` 映射）——归档 [HIGH]“缺 proficiency”**现已修复**。实测 `测试工程师`→200，`skills_required`=15，首技能 proficiency=`精通`。
- **[CONFORM]** 中文岗位名详情编码正常：`goDetail` 路由编码 + `vue-router` 解码 + store 单次编码 = 净单次编码（归档 [MEDIUM]“双重编码”**当前代码已不成立**）；API 精确名匹配 200。
- **[CONFORM]** 空态/加载/错误态齐全（`empty-guide`、`v-loading`、`ElMessage.error`）；分页参数前后端一致。

## 偏移 / 待办
- **[OPEN · MEDIUM · UX]** 行业下拉仅取自当前页（`PositionList.vue:49-52`）→ 选项不全。建议后端 `/positions/industries` 或在 list meta 返回 distinct industries。
- **[OPEN · MEDIUM · 测试]** `PositionList.spec.ts`(2)/`PositionDetail.spec.ts`(1) 过薄，缺 loading/空态/数据渲染/分页/中文详情用例。

## 结论
2 项 HIGH/MEDIUM 真实漂移已修复并验证；2 项符合项纠正了过期归档标记；余 2 项 MEDIUM 入账。
**验证方法学注记**：curl 在 git-bash 下传**字面量中文**会损坏字节（曾致 search/industry 误报 0、匹配曾误报 400）；须用 python 原生 UTF-8 或 `@file` 复核，避免把编码假象当缺陷或反之。