# Phase 2 验证报告 — 岗位模块三端数据源一致性审计

**Phase:** 2 (PositionList + PositionDetail)
**Mode:** 重建+审计（此前无 SUMMARY.md / VALIDATION.md；本报告由 PLAN + 实时三端探针 + Serena 代码关系追踪 重建）
**Date:** 2026-07-27
**方法:** should = `docs/standards/02-frontend/05`+`01-backend/02`+`04-contracts`；is = 前端 PositionList/Detail + stores/jd → API `position.py` → PG `position_records`/`position_skill_relations` + Neo4j `Position`/`REQUIRES`；verify-first（截图+curl+SQL+Cypher），并用 **Serena** 追踪后端调用/过滤链做代码关系审查。

---

## 1. 三端一致性矩阵（实时探针，python 原生 UTF-8 + psql + cypher-shell）

| 维度 | Tier1 API `/positions` | Tier2 PG | Tier3 Neo4j | 一致？ |
|---|---|---|---|---|
| 公开（无 include_all） | **39** | approved=**39** | (approved 等价) | ✅ |
| admin include_all=true | **56** | total=**56** | Position=**56** | ✅ |
| search=`互联网` include_all | **38** | industry ILIKE `%互联网%`=**38** | industry CONTAINS `互联网`=**38** | ✅ 三端同值 |
| industry=`信息技术/互联网` include_all | **33** | 精确子集 33⊂38 | — | ✅ |
| 公开 search=`互联网` | **36** | 38 中 approved=36（2 为 pending） | — | ✅ 可由 39/17 推导 |

**结论：** 每个 API 数字均可由 PG 与 Neo4j 推导，且 PG≡Neo4j 原始计数（Position 56、industry-contains 38）。P-F1（公开仅 approved）、P-F2（search 跨 name+industry 与 Neo4j 对齐）**验证通过**。

---

## 2. Serena 代码关系审查（后端调用/过滤链）

- `list_positions`（position.py:53-154）确认：
  - **P-F1**：`if not include_all and effective_status is None: effective_status="approved"`（公开默认 approved）。
  - **P-F2**：count 与 page 两条语句均 `sa.or_(name.ilike, industry.ilike)`；`industry` 过滤用 `ilike`。
  - 跨端接线：`if total==0 and driver is not None: return await _list_positions_neo4j(...)`。
  - 技能批量 join（无 N+1），返回 name/name_cn/industry/review_status。
- `_list_positions_neo4j`（position.py:312-409）确认与 PG **语义对齐**：search→`name CONTAINS OR industry CONTAINS`；industry→`CONTAINS`；status approved→`(review_status IS NULL OR =approved)`。
- **残留 LOW（跨端字段对齐）**：`_list_positions_neo4j` 构造 `PositionNode` 时**未回写 `review_status`**（PG 路径有），故走 fallback 的项丢失状态徽标。触发条件窄（仅当 PG 该过滤为 0 而 Neo4j 有），admin/public 常规路径不触发。记为 OPEN-LOW。

---

## 3. Nyquist 覆盖审计（按成功标准）

| 标准 | 覆盖 | 证据 / 缺口 |
|---|---|---|
| POS-01 列表 API 分页/筛选 | ✅ live + 回归 | 三端矩阵 + `test_position_conformance.py`（4 测试，锁 search-OR-industry / 公开 approved / include_all 去过滤 / `_escape_like` 转义） |
| POS-02 详情加载+技能图谱 | ⚠️ live 仅 | 详情 200 + `skills_required`=15（proficiency=精通）已 live 验证；**缺** PositionDetail 自动化测试（MEDIUM） |
| POS-03 前端冒烟 | ⚠️ 薄 | `PositionList.spec`/`PositionDetail.spec` 仅渲染级；**缺** 分页/空态/中文详情/可见性 用例（MEDIUM） |

**新增回归锁（已生成并 PASS，无需 DB）：** `backend/tests/integration/test_position_conformance.py` — 4 passed（mock session 捕获 SQL 断言跨端契约；若未来把 search 退回 name-only 或去掉公开 approved 默认即红）。

---

## 4. 残留 / OPEN

- **[OPEN · LOW]** Neo4j fallback `PositionNode` 回写 `review_status`（跨端字段对齐）。
- **[OPEN · MEDIUM · 测试]** PositionDetail 自动化测试 + PositionList 分页/空态/可见性用例。
- **[NOTE]** 本 phase 缺 SUMMARY.md；建议 `/gsd-complete-phase 2` 或补 SUMMARY（不阻塞本审计结论）。

---

## 5. 产物

- 本报告 `VALIDATION.md`
- 回归测试 `backend/tests/integration/test_position_conformance.py`（4 passed）
- 代码修复（前会话/本会话）：`backend/app/api/v1/position.py`（P-F1/P-F2）、`frontend/src/pages/PositionList.vue`（include_all 仅 admin）