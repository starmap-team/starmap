# Phase 13 — 设计-实现一致性对照表 (CONFORMANCE-MAP)

**用途:** Phase 13 的种子上下文。逐模块给出「规范基线 / 既有分析 / 页面 / API / 本会话已发现的偏移种子」，使审计从真实发现起步，而非空泛比对。每个模块执行时产出 `CONFORMANCE-<module>.md`，按 verify-first（修复前验收标准 + 改后截图 + API + DB）闭环。

**对照方法（每模块三项基线）:**
1. **should** = `docs/standards/**` 对应层规范 + `docs/architecture/*` + `docs/ontology/starmap-ontology-v1.md` + `docs/星图-项目设计文档v2.0.md`
2. **was-analyzed** = `docs/archive/<module>-source-analysis.md`
3. **is (live)** = 前端页面 + Pinia store + API + PostgreSQL + Neo4j，用 Playwright 截图 + curl + SQL/Cypher 实测

**SSOT 规则（全模块通用，源自方案 B）:** PostgreSQL 权威；Neo4j 为只读投影（`canonical_id` 对齐，`REQUIRES` 边由 `position_skill_relations` 投影）；无孤儿；`/admin/data-truth` 健康度=ok；KPI 单口径 + tooltip 解释。

---

## 模块对照与已知偏移种子

| 模块 | 规范基线(should) | 既有分析 | 页面 | API 前缀 | 已知偏移种子（verify-first 状态） |
|---|---|---|---|---|---|
| 1 Home | standards/02-frontend/05,04 + ontology + arch/overview | archive/home-source-analysis.md | Home.vue | /graph/* | ✅ 已修：补 582 条 REQUIRES 关系→12 领域渲染；修 Vite 匿名卷空白页；KPI tooltip。**残留**：`total_skills=395`(按域累加重复计数) vs `independent_skills=257` 标签歧义，需在前端明确用 distinct 值 |
| 2 Position | standards/02-frontend/05 + 01-backend/02,10 | archive/position-source-analysis.md | PositionList/Detail | /positions, /graph/position/* | 列表 `total=39`(approved) 与全景 56/70 口径歧义；列表页是否标注「仅已发布」待查 |
| 3 Pipeline | standards/01-backend/07 + arch/pipeline | archive/pipeline-source-analysis.md | PipelineMonitor | /pipeline/* | ✅ SSE 风暴已修；`last_crawl_at` 已加。**待页面验证**：DAG `dedup_clean` 重复显示(consumed 集合代码已改)、僵尸 run 自动检测、今日采集 0 文案 |
| 4 DataSources | standards/01-backend/09 + 03-crawler | archive/datasource-source-analysis.md | DataSources | /datasources | 数据源记录量=0（未真正爬取）；`/datasources/{id}/stats` 曾 422（id 类型 UUID vs int） |
| 5 Match | standards/01-backend/06 | archive/match-source-analysis.md | MatchDiagnosis | /match/* | `/match/position` 曾 500/400（请求体/目标岗位在 Neo4j 缺失）；孤儿清理+关系重建后应改善，待验证 |
| 6 ExtractJD | standards/01-backend/03 | archive/extract-source-analysis.md | ExtractJD | /extract/* | 云端 LLM key 未配→降级 Ollama；反幻觉结果前端可见性待查 |
| 7 Loop | standards/01-backend/07 | archive/loop-source-analysis.md | LoopDemo | /loop/* | `/loop/run` 曾 500；闭环步骤状态待页面验证 |
| 8 Learning | standards/01-backend/05 | archive/learning-source-analysis.md | LearningCenter | /learning/* | `PUT /learning/plan/{id}/progress` 曾 500 |
| 9 Dashboard | standards/01-backend/08 | archive/dashboard-source-analysis.md | DataDashboard | /dashboard/* | ✅ **[2026-07-27 CLOSED · M6 边数口径]** 三端一致：`dashboard.total_edges=582` = Neo4j `MATCH ()-[r:REQUIRES]->()=582` = PG `position_skill_relations=582`（live 验证）。`archive/dashboard-source-analysis.md` 中所述"1179 vs 1375 差 196"为旧 Tool/KA/Industry 残留数据，已随 Phase 5 重建清空。 |
| 10 Evolution | standards/01-backend/04(+ -v2) | archive/evolution-source-analysis.md | EvolutionDashboard | /evolution/* | 趋势/快照/路径端点 200 但数据稀疏；信任度=0 待查 |
| 11 Quality | standards/05-evaluation | archive/quality-source-analysis.md | QualityDashboard | /quality/* | precision/recall/f1=0、warning_level=red（无评估基线/标注数据） |
| 12 Admin | standards/01-backend/02,09 + 02-frontend | archive/admin-source-analysis.md | Admin/AuditLog/UserMgmt | /admin/* | ✅ data-truth 健康度+批量审核已加。**待查**：review-items 翻页 limit 参数、用户管理/审计日志页 |

---

## 跨模块通用偏移（一次修复多模块受益）

- **Vite 匿名卷 `/app/node_modules` 漂移** → 任意页空白。修复：`docker compose -f docker-compose.dev.yml up -d --renew-anon-volumes --force-recreate frontend`，随后 `npm install 3d-force-graph@1.80.0 --save`。见记忆 `starmap-vite-anon-volume-blank-page-fix.md`。
- **三端口径裸呈现** → 所有展示「岗位/技能/关系数」的页面须 tooltip 解释口径，禁止 70/56/39 并列无说明。
- **loading/empty/error 三态** → 每页核查，缺者补设计（参见 standards/02-frontend/05）。
- **console 0 error 门禁** → 每页 Playwright 截图 + `console_messages(level=error)` 必为 0。

---

## 执行建议

1. `/gsd-plan-phase 13` 生成本 phase 计划：建议 Wave 1（模块 1-4）先做，每模块一个 tracer task = 出 CONFORMANCE 报告 → 修 CRITICAL/HIGH → verify-first 取证。
2. 已在本会话修复的项（标 ✅）仍需补「改后截图 + API + DB」三件套写入对应 CONFORMANCE 报告，方算闭环。
3. 残留项（标 **残留/待查**）作为各模块 plan 的首要 task。

*Seeded: 2026-07-26 from multi-endpoint investigation session.*

---

## 本次执行已核实 / 已闭环（Wave 1 部分，verify-first）

| 模块 | 结论 | 证据 |
|---|---|---|
| 1 Home | **CONFORM（可见层）**；latent LOW：API `total_skills=395` 语义歧义（前端已忽略） | 截图 `home_graph_rendered.png`；`Home.vue:38` |
| 4 DataSources | **CONFORM**（422 为 harness artifact）；OPEN MEDIUM：测试用非 UUID id、零数据空态 | curl UUID→200 / int→422 |
| 5 Match | **FIXED+VERIFIED**：Chroma 缺失致全 500 → 降级词法 200；OPEN MEDIUM：profile-less 岗位 404 混淆 | curl 测试工程师 500→200 score .7652 |
| 11 Quality | **FIXED+VERIFIED(契约)**：无基线 red→gray+explanation；OPEN MEDIUM：前端 store 颜色待消费字段 | curl report.warning_level red→gray |

**修复文件：** `backend/app/core/matching/scorer.py`、`backend/app/api/v1/quality.py`
**CONFORMANCE 详报：** `CONFORMANCE-{home,datasources,match,quality}.md`

### 仍 OPEN（按价值排序，含定位）
1. [MEDIUM] Match profile-less 岗位 404 混淆 — `core/matching/service.py` run_match/_load_target_profile + `MatchDiagnosis.vue`
2. [MEDIUM] Quality 前端“未评估”灰色态 — `stores/quality.ts` card.color + `QualityDashboard.vue:97,109`（数据已就绪）
3. [MEDIUM] DataSources 测试 UUID 保真 + 零数据空态 — `admin.test.ts:132`、`DataSources.spec.ts`、`DataSources.vue`
4. [LOW] Home API `total_skills` 字段语义 — `services/graph_service.py:264-265`
5. [MEDIUM] Dashboard 边数口径 1179 vs Neo4j 1375（非 REQUIRES 关系未计入）— `core/dashboard/dashboard_service.py`
6. 模块 2,3,6,7,8,9,10,12 — 尚未审计/核实（按计划逐模块推进）