# CONFORMANCE — Module 4: 数据源管理 (DataSources)

**Phase 13 · Wave 1 · verified 2026-07-26**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/09-服务层-services.md`、`docs/standards/03-crawler/01-爬虫模块规范.md`、`docs/standards/04-contracts/01-API契约规范.md`（路径参数 UUID） |
| was-analyzed | `docs/archive/datasource-source-analysis.md` |
| is (live) | `frontend/src/pages/DataSources.vue` + `stores/datasource.ts` + `/api/v1/datasources/*` + PG `datasource_records` |

## 符合项（已验证）
- **[CONFORM]** `GET /datasources/{source_id}/stats` 契约 `source_id: UUID`（`datasource.py:271-272`）；前端 `fetchStats(id)` 传 list 的 `id`（UUID 字符串，`stores/datasource.ts:103-107`）。**实测真实 UUID → 200**。
- **[ARTIFACT, 非缺陷]** 早先记录的 422 仅在我方 harness 传整数 id 时复现（`/datasources/1/stats` → 422），属测试夹具 artifact，**产品路径符合契约**，不予“修复”。

## 偏移 / 待办
- **[OPEN · MEDIUM · 测试契约]** 测试用非 UUID id，与真实 UUID 契约不符，给出虚假信心：`frontend/src/stores/__tests__/admin.test.ts:132`（`/datasources/1/sync`）、`frontend/src/pages/__tests__/DataSources.spec.ts`（`src-42`/`src-7`）。建议改用 UUID 形态 id 或工厂，使测试覆盖真实解析路径。
- **[OPEN · MEDIUM · UX]** 各数据源 `total_records=0`（未真正采集）。页面应明确“未采集 / 待同步”空态，而非暗示存在数据；与 SSOT/可观测性规范相符。定位 `DataSources.vue` 列表/统计卡。

## 结论
后端 API 契约 **符合**；偏移集中在测试保真度与“零数据”空态 UX（均 MEDIUM，未阻断功能）。