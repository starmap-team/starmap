# 过程编号归档（Phase / Task / 决策 / 关注点 等）

> 本仓库的历史推进过程使用过一套编号体系（`Phase N` / `Plan N Task N` / 决策 `D-N` / 关注点 `CONCERN N.N` /
> 缺陷 `BUG-N` / 用例 `TC-N` / 优先级 `P0-N` 等）。其索引文件（`.planning/`）**未纳入版本控制**，
> 已不可获取，因此这些编号留在代码注释里只会指向无法查证的目标。
>
> **存放位置说明**：原本按仓库惯例放在 `docs/archive/`，但该目录被 `.gitignore:192` 忽略、
> 不随版本控制分发，归档会因此在任何一次本地清理中丢失，与「保留必要记录」的目的相悖，
> 故改置于受版本控制的 `docs/reference/`。
>
> 本文件把这些编号**统一归档**：每个编号 → 它出现在哪些位置、所标注的技术陈述是什么。
> 代码注释中的编号已移除，技术说明保留在原处；追溯记录集中于此。
>
> 由脚本从提交前的注释内容自动生成（2026-10-09），共 291 个编号 / 843 处引用 / 339 个文件，未做人工改写。

## 编号族汇总

| 编号族 | 唯一编号数 | 引用处数 |
|---|---|---|
| `Phase` | 45 | 210 |
| `D` | 16 | 169 |
| `Step` | 13 | 140 |
| `PLAN` | 15 | 61 |
| `Plan` | 23 | 43 |
| `Task` | 10 | 42 |
| `P` | 15 | 40 |
| `SEC` | 6 | 37 |
| `BL` | 9 | 33 |
| `批` | 6 | 23 |
| `NEW` | 13 | 22 |
| `LOOP` | 9 | 22 |
| `BUG` | 14 | 18 |
| `PIPE` | 7 | 13 |
| `C` | 3 | 13 |
| `UX` | 3 | 13 |
| `IC` | 4 | 11 |
| `DC` | 5 | 10 |
| `FLOW` | 3 | 10 |
| `API` | 3 | 8 |
| `DATA` | 5 | 8 |
| `SSE` | 2 | 7 |
| `DEV` | 2 | 6 |
| `PERF` | 5 | 6 |
| `INJ` | 3 | 6 |
| `AP` | 2 | 6 |
| `AUTH` | 1 | 6 |
| `ALIGN` | 2 | 6 |
| `TC` | 6 | 6 |
| `FE` | 3 | 5 |
| `DF` | 4 | 5 |
| `IS` | 3 | 4 |
| `CRON` | 4 | 4 |
| `DEF` | 2 | 4 |
| `MAJOR` | 1 | 2 |
| `SOURCE` | 2 | 2 |
| `AUTHZ` | 2 | 2 |
| `T` | 2 | 2 |
| `CFG` | 1 | 2 |
| `M` | 2 | 2 |
| `CR` | 1 | 2 |
| `US` | 1 | 2 |
| `CANCEL` | 1 | 2 |
| `AC` | 2 | 2 |
| `ADMIN` | 1 | 1 |
| `EV` | 1 | 1 |
| `POLL` | 1 | 1 |
| `F` | 1 | 1 |
| `RECALL` | 1 | 1 |
| `data` | 1 | 1 |
| `SYNC` | 1 | 1 |
| `MINOR` | 1 | 1 |
| `LOG` | 1 | 1 |
| `ALIGNE` | 1 | 1 |

## 明细

### 编号族 `Phase`

#### `Phase 1`  （9 处）
- `backend/app/api/v1/pipeline/trigger_routes.py:63` — """软取消 + Redis STOP flag + Celery 阶段开始时检查。"""
- `backend/app/core/extraction/industry_gate.py:1` — """industry_gate — 岗位行业分类门禁。
- `backend/app/core/pipeline/engine.py:82` — # STOP flag 检查
- `backend/app/core/pipeline/orchestrator.py:516` — # Cancel run (: 软取消 + STOP flag + Celery 阶段开始时检查)
- `backend/app/core/pipeline/status_aggregator.py:1` — """Pipeline status aggregator.
- `backend/tests/unit/test_cancel_run.py:1` — """Unit tests for cancel_run feature.
- `backend/tests/unit/test_graph_overview_heuristics.py:1` — """+ (M1) closure: graph_overview / dashboard 启发式补测（债务消除）。
- `backend/tests/unit/test_graph_overview_heuristics.py:197` — # 6. (M1): _classify_industry 纯函数测试
- `frontend/src/components/__tests__/Graph3D.spec.ts:4` — * 2026-08-13: (M1 全景图谱)

#### `Phase 2`  （9 处）
- `backend/app/api/v1/pipeline/events_routes.py:56` — """SSE polling fallback — 返回最近事件数组。
- `backend/app/api/v1/pipeline/schedule_routes.py:38` — """创建定时调度（: 创建时计算 next_run_at）。"""
- `backend/app/core/pipeline/cron_scheduler.py:1` — """Cron scheduler module.
- `backend/app/core/pipeline/loop/steps/graph_update.py:69` — # Pass extraction_data for DB-query + graph_writer mode
- `backend/app/core/pipeline/orchestrator.py:289` — # AUTHORITY-01: 更新所有数据源权威分
- `backend/app/core/pipeline/orchestrator.py:298` — # AUTHORITY-02: quality < 0.3 的数据源标记 paused
- `backend/app/core/pipeline/stages/crawl.py:162` — """AUTHORITY-03: Log paused sources (the actual skip happens in the spider call)."""
- `backend/app/core/pipeline/stages/dedup.py:197` — # execute_dedup 后更新 duplicate_rate (UAT 修复)
- `backend/app/core/pipeline/stages/import_.py:356` — # execute_import 后更新 valid_records (UAT 修复)

#### `Phase 3`  （7 处）
- `backend/app/core/pipeline/loop/common.py:107` — # 逐步核验摘要
- `backend/app/core/pipeline/loop/status.py:171` — # 闭环管道逐步核验
- `backend/app/core/pipeline/sse/engine.py:62` — # 每步成功后推送详细输出供前端可视化核验
- `backend/app/core/pipeline/sse/engine.py:168` — # 逐步可视化核验 — 每步的输出摘要和验证检查
- `backend/tests/unit/test_pipeline_dag.py:1` — """DAG 串行调度 + JdStatus.cleaned 状态机测试。"""
- `backend/tests/unit/test_pipeline_orchestrator.py:60` — # serial DAG (clean 依赖 dedup, import 依赖 clean,
- `backend/tests/unit/test_pipeline_orchestrator.py:111` — # clean 现在依赖 dedup，必须 dedup 完成才能 ready

#### `Phase 4`  （3 处）
- `backend/scripts/kpi_audit.py:118` — # 静态 KPI 审计（保留，用于输出页面级口径来源清单）
- `backend/scripts/kpi_audit.py:199` — # 静态审计产物保留（页面级 KPI 口径来源清单）
- `backend/tests/unit/test_llm_cost_tracker.py:1` — """LLM cost tracker unit tests.

#### `Phase 5`  （8 处）
- `backend/app/api/v1/admin.py:82` — """手动触发 PG → Neo4j 同步 + 孤儿节点剪枝。
- `backend/app/api/v1/admin.py:171` — # 写 audit_events 记录
- `backend/app/api/v1/admin_data_truth.py:274` — # 计算同步健康度
- `backend/app/core/pipeline/cron_scheduler.py:324` — # 定时 reconcile 状态
- `backend/app/core/pipeline/cron_scheduler.py:338` — # 定时 reconcile
- `backend/app/core/pipeline/cron_scheduler.py:354` — # 写 audit_events 供健康度监控查询
- `backend/scripts/phase5_rebuild_neo4j.py:1` — """修复 Neo4j 字段映射 + 清空 + 从 PG 重建
- `backend/scripts/phase5_rebuild_neo4j.py:142` — """执行：备份 → 清空 → 从 PG 重建。"""

#### `Phase 7`  （9 处）
- `backend/app/api/v1/admin.py:947` — # ── Sub-routers (admin domain split) ──
- `backend/app/api/v1/evolution_career_path.py:1` — """Evolution career-path endpoint — extracted from evolution.py (evolution domain split).
- `backend/app/api/v1/evolution_emerging_alerts.py:1` — """Evolution emerging-skill alerts endpoint — extracted from evolution.py (evolution domain split).
- `backend/app/api/v1/evolution_industry_report.py:1` — """Evolution industry-report endpoint — extracted from evolution.py (evolution domain split).
- `backend/app/api/v1/pipeline/trigger_routes.py:133` — # fix: detect and mark stuck stages before advancing
- `backend/app/api/v1/pipeline/trigger_routes.py:445` — # ──: Crawler completion Webhook (fix) ──
- `backend/app/api/v1/quality_trends_alerts.py:1` — """Quality trends + alerts endpoints — extracted from quality.py (quality domain split).
- `backend/app/core/pipeline/stages/graph_sync.py:29` — # ── Graph Write Outbox helpers (; 原 executor.py, 随阶段迁入) ──
- `backend/tests/unit/test_stage3_outbox.py:1` — """fix: outbox regression test for run_batch_extract_jd.

#### `Phase 02`  （6 处）
- `backend/app/core/pipeline/stages/graph_sync.py:188` — # Position PG↔Neo4j 一致性校验（**默认开启**，仅观察不阻断）。
- `backend/app/core/pipeline/stages/graph_sync.py:228` — # ── Position PG↔Neo4j 一致性校验（；沿 M3 仅观察不阻断）──
- `backend/app/services/admin_audit_service.py:58` — # single source of the Position MERGE Cypher.
- `backend/app/services/admin_audit_service.py:76` — # 剪枝早期按 name MERGE 产生的遗留 Position 节点（无 canonical_id，不受 SSOT 管理）。
- `backend/tests/integration/test_admin_sync_position.py:1` — """Integration tests for POST /api/v1/admin/sync/all-positions-to-neo4j.
- `backend/tests/unit/test_graph_sync_position_drift.py:1` — """graph_sync 阶段末 Position PG↔Neo4j 一致性校验单元测试。

#### `Phase 03`  （14 处）
- `backend/app/core/pipeline/cron_scheduler.py:37` — # 5 字段值域常量
- `backend/app/core/pipeline/engine.py:1` — """Pipeline DAG 执行引擎（拆分：从 executor.py 迁出）。
- `backend/tests/unit/test_cron_validation.py:1` — """Cron 校验完整测试。
- `backend/tests/unit/test_layer_boundary.py:50` — # pipeline 按领域拆 6 子路由，逐一纳入层边界守卫
- `backend/tests/unit/test_pipeline_routes_split.py:1` — """APIRouter 子路由分片验证。
- `backend/tests/unit/test_pipeline_t5_fix.py:1` — """T5 bug 修复 — execute_clean→cleaned + import reads cleaned + batch_size 可配。
- `backend/tests/unit/test_stages_clean.py:1` — """stages/clean.py 阶段测试。
- `backend/tests/unit/test_stages_common.py:1` — """stages/common.py 公共层测试。
- `backend/tests/unit/test_stages_crawl.py:1` — """stages/crawl.py 阶段测试。
- `backend/tests/unit/test_stages_dedup.py:1` — """stages/dedup.py 阶段测试。
- `backend/tests/unit/test_stages_graph_sync.py:1` — """stages/graph_sync.py 阶段测试。
- `backend/tests/unit/test_stages_import.py:1` — """stages/import_.py 阶段测试 + SSOT 可观测化测试。
- `backend/tests/unit/test_stages_timeseries.py:1` — """stages/timeseries.py 阶段测试。
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:2` — * PipelineMonitor.vue 测试套件。

#### `Phase 10`  （1 处）
- `crawler/run.py:130` — # (b): CLI 触发完整 pipeline run

#### `Phase 11`  （3 处）
- `backend/tests/integration/test_hallucination_rate_schema.py:1` — """hallucination_rate 三段式契约 schema 集成测试。"""
- `backend/tests/unit/test_graph_overview_heuristics.py:1` — """+ (M1) closure: graph_overview / dashboard 启发式补测（债务消除）。
- `backend/tests/unit/test_hallucination_rate.py:1` — """hallucination_rate 补测 + schema 三段式契约。

#### `Phase 13`  （11 处）
- `backend/app/core/pipeline/status_aggregator.py:141` — # M5（强制规范）：以“已质检/已入库记录数”判断是否有可评估数据。
- `backend/app/services/graph_overview.py:118` — # heat 视图（按技能需求频率着色）
- `backend/app/services/graph_overview.py:173` — # 行业归一（13 大行业，对标 spec 5.3）
- `backend/app/services/graph_overview.py:220` — """按 Position.name + industry 关键词分类到 14 大行业。
- `backend/app/services/graph_overview.py:535` — # 热度视图（技能需求频次）
- `backend/app/services/graph_overview.py:544` — """按技能需求频率排序的"热度视图"。
- `backend/tests/unit/test_graph_services.py:720` — # ── graph_overview: fetch_overview_by_heat (M1 closure) ─
- `backend/tests/unit/test_graph_services.py:820` — # ── graph_service: fetch_overview_by_domain (M1 closure) ─
- `backend/tests/unit/test_graph_services.py:824` — """fetch_overview_by_domain —: 行业归一(13 大行业)视图。
- `backend/tests/unit/test_overview_dimensions.py:1` — """验证 4 个 overview 端点（domain/tech_stack/level/heat）：
- `backend/tests/unit/test_overview_dimensions.py:48` — # level 端点必须 3 维泡保满（含 junior 兜底）

#### `Phase 15`  （4 处）
- `backend/app/core/extraction/translation.py:1` — """English → Chinese translation hook for non-CJK JD sources (I18N-01).
- `backend/app/core/pipeline/stages/crawl.py:101` — # api/rss 源同样参与 crawl 阶段（修复在 rebase 中丢失，恢复）
- `backend/app/services/import_service.py:38` — # Fix H3 (review): 全量 hash 而非 [:500] 截断
- `backend/app/services/import_service.py:49` — # Fix H2 (review): PII 检测

#### `Phase 19`  （12 处）
- `backend/app/core/extraction/graph_writer.py:532` — # 投影落 trust_score（§6.2 四因子公式）——修复"投影不写信任 → 新技能
- `backend/app/core/extraction/graph_writer.py:740` — # 抽取置信度透传 → merge_skill 计算 trust_score（§6.2）
- `backend/app/core/pipeline/cron_scheduler.py:223` — # reconcile 时全量重算 Skill.trust_score（§6.2 四因子），
- `backend/app/core/pipeline/stages/dedup.py:106` — # 空分支 return 也补 current_activity（DB 快照持久化）
- `backend/app/core/pipeline/stages/dedup.py:209` — # 修复: return 补 current_activity（DB 快照持久化，卡片解释"为何 0/去重结果"）
- `backend/app/core/pipeline/stages/graph_sync.py:210` — # 修复: return 补 current_activity（DB 快照持久化，解释"0 条扫描/构建结果"）
- `backend/app/core/pipeline/stages/import_.py:376` — # 修复: return 补 current_activity（DB 快照持久化）
- `backend/app/services/graph_sync.py:19` — """全量重算 Skill 节点 trust_score。
- `backend/app/services/quality_service.py:30` — """§6.2 四因子综合信任度分布（与 KPI avg(n.trust_score) 同口径）。
- `backend/tests/unit/test_entity_trust.py:1` — """Coverage: core/trust/entity_trust.py — 实体信任四因子评分器。
- `backend/tests/unit/test_graph_writer_coverage.py:394` — # 投影落 trust_score（§6.2 四因子）——断言 Cypher props 含 trust_score
- `backend/tests/unit/test_recompute_skill_trust.py:1` — """Coverage: services/graph_sync.py recompute_skill_trust — 全量重算 Skill.trust_score。

#### `Phase 20`  （3 处）
- `backend/tests/unit/test_auth_service.py:120` — """JOSE header carries `kid` for rotation keyring lookup."""
- `backend/tests/unit/test_auth_service.py:131` — # JWT rotation — kid keyring
- `backend/tests/unit/test_auth_service.py:136` — """JWT kid + keyring rotation —.

#### `Phase 22`  （1 处）
- `backend/tests/unit/test_pipeline_crawl_integrity.py:1` — """爬虫多源数据完整性回归测试。"""

#### `Phase 23`  （7 处）
- `backend/app/api/v1/admin.py:316` — # Review workflow endpoints (D-tier redesign)
- `backend/app/core/extraction/graph_writer.py:627` — # 双模式：canonical_id 优先，否则 name 回退
- `backend/scripts/kpi_audit.py:154` — # 三段 KPI 唯一事实源 status_aggregator.py
- `backend/scripts/kpi_audit.py:208` — # 运行时断言：接受 --aggregates <json-file> 输入（无输入则打印跳过提示，
- `backend/tests/unit/test_reconcile_requires_edges.py:313` — """核验修复 (M1b 闭环): reconcile_all 节点快照必须限定 approved。
- `backend/tests/unit/test_reconcile_requires_edges.py:385` — """核验修复 (M1b 闭环): reconcile 端点 PG 计数必须限定 approved。
- `backend/tests/unit/test_stage3_outbox.py:74` — # 门控: 默认 approved（保持既有 outbox 测试语义），

#### `Phase 24`  （8 处）
- `backend/app/core/extraction/prompt_injection.py:1` — """Input-side prompt-injection detector (CONCERN 1.6).
- `backend/app/services/admin_audit_service.py:458` — # (evolution orchestrator stores it under
- `backend/tests/unit/test_admin_data_truth.py:95` — """核验修复: data-truth PG 计数必须限定 approved 口径。
- `backend/tests/unit/test_celery_task_failure.py:1` — """CONCERN 2.4 : Celery task_failure signal wiring tests."""
- `backend/tests/unit/test_pipeline.py:325` — """P4 fix: skill_gap_detail 必须含 score 字段（前端 Math.round(row.score*100) 依赖）。
- `backend/tests/unit/test_pipeline.py:365` — """P5 fix: top_matches 岗位名必须用 name_cn（_display_name）优先。
- `backend/tests/unit/test_pipeline_steps_smoke.py:50` — # P1 fix (求职者分析): 30s→120s 对齐 LLM 降级链（本地 fallback 40-120s)
- `backend/tests/unit/test_prompt_injection.py:1` — """Unit tests for input-side prompt-injection detector (CONCERN 1.6)."""

#### `Phase 27`  （20 处）
- `backend/app/config.py:227` — # (qwen-plus 资源包优化): LLM 响应 Redis 缓存与翻译缓存
- `backend/app/config.py:238` — # 资源包严格保护: 单次请求 input token 上限。资源包规则要求
- `backend/app/config.py:243` — # 资源包严格保护: 全局启用开关。True = 正常调用 qwen-plus,
- `backend/app/core/extraction/jd_extract.py:233` — # 资源包严格保护: blocked = 严格不调用(不重试,不消耗任何 token)
- `backend/app/core/extraction/llm_client.py:393` — # 曾按"实测抽取 JSON ~1500 tokens"把 4096 降到 2048 以节省
- `backend/app/core/extraction/llm_client.py:471` — # (qwen-plus 资源包优化): 优先按 model + prompt 查 Redis 缓存,
- `backend/app/core/extraction/llm_client.py:486` — # 每日成本 cap 检查 —— 防止意外情况下累积成本爆表
- `backend/app/core/extraction/llm_client.py:498` — # 资源包严格保护: 全局启用开关。紧急止血用,
- `backend/app/core/extraction/llm_client.py:507` — # 资源包严格保护: 单次请求 input token 128K 闸门。
- `backend/app/core/extraction/translation.py:28` — # 翻译缓存命名空间与 TTL
- `backend/app/core/extraction/translation.py:131` — # 先查 Redis 缓存(覆盖同 title 多次翻译)
- `backend/app/core/llm/cost_tracker.py:105` — # cap 检查 (软警告 + 硬阻断)
- `backend/app/core/pipeline/stages/import_.py:225` — # (qwen-plus 资源包优化): 同批内 content_hash 重复的 JD 复用首次抽取结果,
- `backend/app/main.py:86` — # (qwen-plus 资源包优化): 启动时按 settings 注入每 model 每日成本 cap,
- `backend/app/main.py:98` — # 把 settings.llm_response_cache_ttl_seconds 注入到 response_cache 单例
- `backend/tests/integration/test_import_dedup.py:1` — """import stage in-batch dedup tests.
- `backend/tests/unit/test_cost_tracker.py:1` — """Cost tracker cap tests.
- `backend/tests/unit/test_llm_hard_guards.py:1` — """hard guard tests.
- `backend/tests/unit/test_llm_response_cache.py:1` — """LLM response cache unit tests.
- `backend/tests/unit/test_translation_cache.py:1` — """Translation cache unit tests.

#### `Phase 38`  （7 处）
- `backend/alembic/versions/041_add_position_definition_columns.py:1` — """Add A3 five-element definition columns to position_records (2026-08-31).
- `backend/app/api/v1/admin.py:573` — # 审核通过 → 若岗位缺五要素则 LLM 生成（fail-soft，失败仅记 warning）
- `backend/app/api/v1/position.py:235` — # A3 五要素（持久化列，缺省返回 null/空列表）
- `backend/app/models/extraction_models.py:356` — # ── A3 岗位定义五要素（：全岗位持久化）──
- `backend/scripts/backfill_position_definitions.py:1` — """全量回填岗位五要素(A3 持久化）。
- `frontend/src/pages/PositionDetail.vue:50` — // A3 五要素
- `frontend/src/pages/PositionDetail.vue:556` — /*岗位定义（五要素）卡片 */

#### `Phase 3.7`  （2 处）
- `backend/app/core/pipeline/orchestrator.py:103` — # 实时活动字段
- `backend/app/core/pipeline/orchestrator.py:237` — # 实时活动上下文持久化

#### `Phase 07-02`  （14 处）
- `backend/app/core/pipeline/loop/common.py:1` — """Loop orchestration shared types & persistence helpers.
- `backend/app/core/pipeline/loop/status.py:1` — """Loop status / history retrieval + per-step verification.
- `backend/app/core/pipeline/loop/steps/extract.py:1` — """— Skill Extraction.
- `backend/app/core/pipeline/loop/steps/extract.py:126` — # explicit model + aggregate confidence
- `backend/app/core/pipeline/loop/steps/graph_update.py:1` — """— Neo4j graph sync.
- `backend/app/core/pipeline/loop/steps/learning_path.py:1` — """— Learning path derivation.
- `backend/app/core/pipeline/loop/steps/match.py:1` — """— Match diagnosis.
- `backend/app/core/pipeline/loop/steps/validate.py:1` — """— JD input validation + target_position resolution.
- `backend/app/core/pipeline/loop_orchestrator.py:1` — """Closed-Loop Orchestrator — compat / re-export shell.
- `backend/tests/unit/test_loop_orchestrator.py:301` — # degradation判定 + model_used 透传 (T7)
- `frontend/src/components/loop/__tests__/LoopStepGraph.spec.ts:2` — * LoopStepGraph.spec — T9
- `frontend/src/components/loop/__tests__/LoopStepMatch.spec.ts:2` — * LoopStepMatch.spec — T9
- `frontend/src/components/loop/__tests__/LoopStepSkills.spec.ts:2` — * LoopStepSkills.spec — T8
- `frontend/src/pages/__tests__/LoopDemo.spec.ts:146` — // ---- T10: 错误透传 + 重新开始新 run_id + 状态映射 ----

#### `Phase 15-01`  （1 处）
- `backend/tests/unit/test_spiders.py:1` — """Tests for spider integrations.

#### `Phase 15-02`  （4 处）
- `backend/alembic/versions/022_unique_content_hash.py:1` — """Add UNIQUE constraint on jd_raw.content_hash.
- `backend/alembic/versions/022_unique_content_hash.py:21` — # 让 content_hash 成为真正的去重 key
- `backend/alembic/versions/023_drop_source_url_unique.py:1` — """Drop source_url UNIQUE constraint, keep content_hash UNIQUE.
- `backend/tests/unit/test_import_jd.py:1` — """Tests for import service + PII detector + CSV parser."""

#### `Phase 15-04`  （3 处）
- `backend/alembic/versions/024_data_source_metrics.py:1` — """Add data_source_metrics table + last_successful_crawl_at column.
- `backend/app/api/v1/health_monitor.py:1` — """Health monitor API endpoints.
- `backend/app/services/health_monitor.py:1` — """Health monitor for data sources.

#### `Phase 17-03`  （3 处）
- `backend/app/core/extraction/graph_writer.py:702` — # (Fix B3): 缺失 position_name 静默跳过, 不阻塞 batch
- `backend/app/core/extraction/graph_writer.py:810` — # (Fix B4): try/except 单条隔离, 一条失败不阻塞整个 batch
- `backend/tests/unit/test_graph_writer_coverage.py:474` — # (Fix B3): 缺失 position_name 静默跳过(不阻塞 batch),返回 skipped 标记。

#### `Phase 3.8.1`  （2 处）
- `backend/app/core/pipeline/orchestrator.py:216` — # stage 完成/失败时强制 progress=1.0 (避免显示 0%)
- `backend/app/core/pipeline/orchestrator.py:603` — # 5. FIX: 通过 SSE 广播 cancel 事件，让前端立即响应

#### `Phase 3.8.5`  （1 处）
- `backend/app/api/v1/pipeline/trigger_routes.py:176` — """强制重置卡死的 run (is_running=true 但无 stage running).

#### `Phase 3.8.7`  （2 处）
- `backend/app/core/pipeline/engine.py:111` — # also fail required stages (not just skip optional ones)
- `backend/app/core/pipeline/engine.py:124` — # FIX: Required dep failed -> 标记下游 stage 为 failed

#### `Phase 3.8.10`  （1 处）
- `crawler/spiders/v2ex_remote.py:1` — """V2EX + Remotive API spider — 真实 JD 数据源 (Pony).

#### `Phase 23 Task 1`  （2 处）
- `backend/tests/unit/test_outbox_retry_worker.py:1` — """Outbox retry worker tests.
- `backend/tests/unit/test_stage3_outbox.py:140` — """retry worker 只消费 failed 行，completed/drift_warning 不误捡。

#### `Phase 23 Task 2`  （4 处）
- `backend/app/core/extraction/graph_writer.py:473` — # MERGE 键从 name 切为 canonical_id。
- `backend/app/core/extraction/graph_writer.py:538` — # 同 merge_position——无 canonical_id 落图会再次产生孤儿
- `backend/tests/unit/test_graph_writer_coverage.py:554` — """无 canonical_ids_list 时 batch 逐条跳过（不产生孤儿）。"""
- `backend/tests/unit/test_graph_writer_merge_key.py:1` — """— MERGE key name→canonical_id (checkpoint:decision) tests.

#### `Phase 23 Task 3`  （4 处）
- `backend/app/api/v1/admin.py:157` — # 健康度（扩展：边 ±0.5% 容差纳入三档）
- `backend/app/services/graph_projector.py:527` — """按 canonical_id 补缺 REQUIRES 边（PG approved PSR）。
- `backend/tests/unit/test_admin_endpoints.py:856` — """ReconcileResult 含 REQUIRES 边对账字段（可观测）。"""
- `backend/tests/unit/test_reconcile_requires_edges.py:1` — """— /admin/reconcile-neo4j REQUIRES 边对账  + skills_synced bug.

#### `Phase 23 Task 4`  （3 处）
- `backend/alembic/versions/039_seed_daily_reconcile_schedule.py:1` — """Seed daily_reconcile schedule row.
- `backend/tests/integration/test_daily_reconcile_full.py:1` — """— 每日对账 cron 集成测试。
- `backend/tests/unit/test_cron_scheduler.py:181` — """daily_reconcile name 分发到 reconcile_graph_task.delay。

#### `Phase 23 Task 5`  （4 处）
- `backend/tests/unit/test_entity_trust.py:108` — """ 回归锁定：EntityTrustScorer 不参与写回闸门。
- `backend/tests/unit/test_evolution_write_back.py:96` — """pending 行 trust<0.6 仍被拦（0.6 保守闸门保留）。"""
- `backend/tests/unit/test_evolution_write_back.py:108` — """approved 行 trust<0.6 直接放行写回 PSR。"""
- `backend/tests/unit/test_trust_scorer.py:88` — """单源 cold-start trust 数值固化（文档锚点）。

#### `Phase 23 Task 6`  （1 处）
- `backend/tests/unit/test_graph_requires_spec.py:1` — """— REQUIRES 边属性契约收敛tests.

#### `Phase 23 Task 7`  （1 处）
- `backend/tests/unit/test_graph_write_metrics.py:1` — """— source_count max 语义探针与回归测试.

#### `Phase 23 Task 8`  （3 处）
- `backend/tests/unit/test_datasource_api.py:359` — """PATCH status='inactive' 被接受（替代 DELETE 独占软删）。"""
- `backend/tests/unit/test_datasource_api.py:642` — """新源不能直接建为停用 → Literal 拒绝 (422)。"""
- `backend/tests/unit/test_datasource_api.py:664` — """共享 DataSourceStatus 覆盖 'inactive' 且被 schema 引用。"""

#### `Phase 23 Task 9`  （1 处）
- `frontend/src/composables/__tests__/usePipelineMonitor.kpi.spec.ts:2` — * usePipelineMonitor KPI 三段口径测试(防跨页漂移）。

#### `Phase 23 Task 10`  （5 处）
- `backend/tests/unit/test_eval_ingestion_metrics.py:1` — """— ingestion_consistency 6 项入库完整性指标单测。
- `evaluation/ingestion_consistency.py:1` — """— 入库完整性指标评估（ingestion gate）。
- `evaluation/run_baseline.py:18` — # 第二道门禁 — 入库完整性指标（连实时库，阈值集中 config.py）
- `evaluation/run_baseline.py:249` — # 第二道门禁 — ingestion gate（入库完整性，..07 回归守护）。
- `scripts/ensure_data_consistency.py:30` — # 改走 Pydantic/settings（不硬编码环境变量）。

#### `Phase 15-01 Task 6`  （1 处）
- `backend/alembic/versions/021_seed_free_api_sources.py:1` — """Seed 4 free API/Feed data sources.

#### `Phase 15-02 Task 2`  （1 处）
- `backend/app/services/import_service.py:1` — """Import service — 复用 dao.upsert_jd 路径."""

#### `Phase 15-02 Task 3`  （2 处）
- `backend/app/services/csv_parser.py:1` — """CSV parser with multi-encoding support (Fix M3).
- `backend/app/services/pii_detector.py:1` — """PII detector — 检测导入文本中的个人信息 (.5, Fix H2).

#### `Phase 15-02 Task 4`  （1 处）
- `backend/app/api/v1/import_jd.py:1` — """Import JD API endpoints.

#### `Phase 15-04 Task 1`  （1 处）
- `backend/alembic/versions/029_add_data_source_metrics.py:1` — """Add data_source_metrics table (2026-08-07 补建).

#### `Phase 16-01 Task 4`  （1 处）
- `backend/alembic/versions/025_add_pipeline_indexes.py:1` — """Add pipeline_runs + data_source_metrics indexes.

### 编号族 `D`

#### `D-01`  （20 处）
- `backend/app/core/pipeline/loop/steps/extract.py:1` — """— Skill Extraction.
- `backend/app/core/pipeline/loop/steps/graph_update.py:1` — """— Neo4j graph sync.
- `backend/app/core/pipeline/loop/steps/learning_path.py:1` — """— Learning path derivation.
- `backend/app/core/pipeline/loop/steps/match.py:1` — """— Match diagnosis.
- `backend/app/core/pipeline/loop/steps/validate.py:1` — """— JD input validation + target_position resolution.
- `backend/app/core/pipeline/stages/__init__.py:1` — """Pipeline 阶段模块聚合入口。
- `backend/app/core/pipeline/stages/clean.py:1` — """Pipeline clean 阶段。
- `backend/app/core/pipeline/stages/crawl.py:1` — """Pipeline crawl 阶段。
- `backend/app/core/pipeline/stages/dedup.py:1` — """Pipeline dedup 阶段。
- `backend/app/core/pipeline/stages/graph_sync.py:1` — """Pipeline graph_sync 阶段。
- `backend/app/core/pipeline/stages/import_.py:1` — """Pipeline import 阶段。
- `backend/app/core/pipeline/stages/timeseries.py:1` — """Pipeline timeseries 阶段。
- `backend/app/services/admin_audit_service.py:58` — # single source of the Position MERGE Cypher.
- `backend/app/services/admin_audit_service.py:76` — # 剪枝早期按 name MERGE 产生的遗留 Position 节点（无 canonical_id，不受 SSOT 管理）。
- `backend/app/services/admin_audit_service.py:231` — """全量补跑 PG PositionRecord → Neo4j Position 节点（幂等 MERGE）。
- `backend/tests/unit/test_graph_overview_heuristics.py:1` — """+ (M1) closure: graph_overview / dashboard 启发式补测（债务消除）。
- `backend/tests/unit/test_run_match.py:111` — """响应携带 score_breakdown（分数组件可感知，前端可展示拆解）。"""
- `backend/tests/unit/test_stages_common.py:91` — """未迁出的 stage 调用应抛 NotImplementedError（进度标识）。
- `backend/tests/unit/test_stages_graph_sync.py:99` — """进度完成标志：未迁出 stub 列表为空。"""
- `frontend/src/components/__tests__/MatchTrustGuide.spec.ts:2` — * MatchTrustGuide.spec.ts —/分数拆解 + 信任度降级文案测试。

#### `D-02`  （25 处）
- `backend/app/api/v1/pipeline/config_routes.py:1` — """Pipeline 配置子路由（拆分）。
- `backend/app/api/v1/pipeline/events_routes.py:1` — """Pipeline events 子路由（拆分起步）。
- `backend/app/api/v1/pipeline/runs_routes.py:1` — """Pipeline 运行历史子路由（拆分）。
- `backend/app/api/v1/pipeline/schedule_routes.py:1` — """Pipeline 定时调度子路由（拆分）。
- `backend/app/api/v1/pipeline/status_routes.py:1` — """Pipeline 状态/概览子路由（拆分）。
- `backend/app/api/v1/pipeline/trigger_routes.py:1` — """Pipeline 操作类子路由（拆分）。
- `backend/app/core/pipeline/cron_scheduler.py:223` — # reconcile 时全量重算 Skill.trust_score（§6.2 四因子），
- `backend/app/core/pipeline/loop/status.py:1` — """Loop status / history retrieval + per-step verification.
- `backend/app/core/pipeline/loop_orchestrator.py:1` — """Closed-Loop Orchestrator — compat / re-export shell.
- `backend/app/core/pipeline/loop_orchestrator.py:42` — """5-step closed-loop pipeline (compat shell)."""
- `backend/app/core/pipeline/loop_orchestrator.py:240` — # ---- Module-level helpers re-export (compat shim) ----
- `backend/app/services/admin_audit_service.py:58` — # single source of the Position MERGE Cypher.
- `backend/app/services/admin_audit_service.py:231` — """全量补跑 PG PositionRecord → Neo4j Position 节点（幂等 MERGE）。
- `backend/app/services/graph_sync.py:19` — """全量重算 Skill 节点 trust_score。
- `backend/tests/integration/test_admin_sync_position.py:1` — """Integration tests for POST /api/v1/admin/sync/all-positions-to-neo4j.
- `backend/tests/unit/test_auth_service.py:120` — """JOSE header carries `kid` for rotation keyring lookup."""
- `backend/tests/unit/test_auth_service.py:131` — # JWT rotation — kid keyring
- `backend/tests/unit/test_auth_service.py:136` — """JWT kid + keyring rotation —.
- `backend/tests/unit/test_evolution_emergence_path.py:255` — """三重条件边界锁定（z>2.0 且 频次>=3 且 源>=3 → EMERGING）。"""
- `backend/tests/unit/test_evolution_emergence_path.py:366` — """阈值来自配置（emergence_z_emerging=2.0 / emergence_z_rising=1.5），非硬编码。"""
- `backend/tests/unit/test_hallucination_rate.py:1` — """hallucination_rate 补测 + schema 三段式契约。
- `backend/tests/unit/test_layer_boundary.py:63` — # 纯聚合入口：routes.py 仅 include_router 子路由，无业务逻辑，
- `backend/tests/unit/test_pipeline_routes_split.py:33` — """events_routes 子模块必须存在（拆分起步）。"""
- `backend/tests/unit/test_proxy_breaker.py:1` — """验收：熔断行为契约。"""
- `frontend/src/components/__tests__/MatchTrustGuide.spec.ts:2` — * MatchTrustGuide.spec.ts —/分数拆解 + 信任度降级文案测试。

#### `D-03`  （17 处）
- `backend/app/core/pipeline/loop_orchestrator.py:51` — """Execute the full 5-step closed-loop pipeline (fail-fast + degrade)."""
- `backend/app/core/pipeline/loop_orchestrator.py:169` — # Determine overall status : only path/match failures → COMPLETED; ≥3 failures → FAILED
- `backend/app/core/pipeline/stages/graph_sync.py:188` — # Position PG↔Neo4j 一致性校验（**默认开启**，仅观察不阻断）。
- `backend/app/core/pipeline/stages/graph_sync.py:228` — # ── Position PG↔Neo4j 一致性校验（；沿 M3 仅观察不阻断）──
- `backend/app/core/pipeline/stages/graph_sync.py:286` — """Neo4j Position 节点数 vs PG PositionRecord 行数一致性校验。
- `backend/tests/unit/test_evolution_emergence_path.py:318` — """历史窗口 len(frequencies) < 2 时 Wilson 下界 > 0.3 → RISING 兜底。"""
- `backend/tests/unit/test_evolution_emergence_path.py:345` — """兜底比 文字更严格：source_count < MIN_SOURCES 则 STABLE（保持现状不放宽）。"""
- `backend/tests/unit/test_graph_sync_position_drift.py:1` — """graph_sync 阶段末 Position PG↔Neo4j 一致性校验单元测试。
- `backend/tests/unit/test_loop_orchestrator.py:301` — # degradation判定 + model_used 透传 (T7)
- `backend/tests/unit/test_loop_orchestrator.py:426` — """fail-fast + 降级判定:
- `backend/tests/unit/test_loop_orchestrator.py:434` — """Stack of patches used by degradation tests."""
- `backend/tests/unit/test_loop_orchestrator.py:467` — # only 1 failure (step3) → overall COMPLETED
- `backend/tests/unit/test_loop_orchestrator.py:481` — # only step 4/5 failed → overall COMPLETED
- `backend/tests/unit/test_pipeline_bootstrap.py:1` — """(c): bootstrap 行为契约测试。"""
- `crawler/run.py:86` — """(b): CLI 子命令触发一次完整 pipeline run."""
- `crawler/run.py:130` — # (b): CLI 触发完整 pipeline run
- `frontend/src/pages/__tests__/DataSources.spec.ts:74` — // （shallowMount + stub 会吞掉按钮树，见 11-04 quality 计划 T3/偏差教训）

#### `D-04`  （18 处）
- `backend/app/api/v1/pipeline/trigger_routes.py:63` — """软取消 + Redis STOP flag + Celery 阶段开始时检查。"""
- `backend/app/core/evolution/graph_projection.py:1` — """Incremental Neo4j projection of evolution write-back edges (tail).
- `backend/app/core/pipeline/cron_scheduler.py:223` — # reconcile 时全量重算 Skill.trust_score（§6.2 四因子），
- `backend/app/core/pipeline/engine.py:82` — # STOP flag 检查
- `backend/app/core/pipeline/orchestrator.py:516` — # Cancel run (: 软取消 + STOP flag + Celery 阶段开始时检查)
- `backend/app/core/pipeline/orchestrator.py:540` — """Cancel a running pipeline.
- `backend/app/services/graph_sync.py:19` — """全量重算 Skill 节点 trust_score。
- `backend/tests/integration/test_evolution_pipeline.py:188` — # 3) REQUIRES edge must be visible in Neo4j after projection (尾句闭环)
- `backend/tests/unit/test_cancel_run.py:23` — """Test: cancelling a running run sets status='cancelled'."""
- `backend/tests/unit/test_config.py:55` — """所有 LLM key 为空时输出 WARNING，含 MIMO_API_KEY 和 DEEPSEEK_API_KEY。"""
- `backend/tests/unit/test_evolution_graph_projection.py:1` — """Unit tests for incremental Neo4j projection counting (W2, tail).
- `backend/tests/unit/test_evolution_write_back.py:1` — """Unit tests for evolution write-back.
- `backend/tests/unit/test_evolution_write_back.py:176` — """retained is a no-op."""
- `backend/tests/unit/test_evolution_write_back.py:212` — """added_preferred maps to requirement_type='preferred' (mapping)."""
- `backend/tests/unit/test_evolution_write_back.py:300` — """demoted → SET requirement_type='preferred' (mapping)."""
- `frontend/src/pages/__tests__/MatchDiagnosis.spec.ts:213` — // 口径注记
- `frontend/src/pages/__tests__/PositionDetail.spec.ts:148` — // ──: 雷达图缺数据降级（沿 M5：无画像岗位不返回 404）──
- `frontend/src/pages/__tests__/PositionList.spec.ts:163` — // ──: 行业 chip（M10 数据透明）+ created_at 相对时间 ──

#### `D-05`  （18 处）
- `backend/app/core/evolution/trust_scorer.py:62` — # write-back gate: independent from LOW_TRUST_THRESHOLD (approved/review
- `backend/app/core/pipeline/loop/steps/extract.py:126` — # explicit model + aggregate confidence
- `backend/app/core/pipeline/loop/steps/graph_update.py:1` — """— Neo4j graph sync.
- `backend/app/core/pipeline/loop/steps/match.py:1` — """— Match diagnosis.
- `backend/app/core/pipeline/loop_orchestrator.py:206` — """Compat delegate → ``steps.graph_update.run_graph_update_step``."""
- `backend/app/core/pipeline/loop_orchestrator.py:210` — """Compat delegate → ``steps.match.run_match_step`` (score_breakdown)."""
- `backend/app/core/pipeline/loop_orchestrator.py:216` — """Compat delegate → ``steps.learning_path.run_learning_path_step``."""
- `backend/tests/integration/test_hallucination_rate_schema.py:1` — """hallucination_rate 三段式契约 schema 集成测试。"""
- `backend/tests/integration/test_hallucination_rate_schema.py:36` — """窗口默认 30 天，匹配 CONTEXT 统计窗口。"""
- `backend/tests/unit/test_evolution_write_back.py:1` — """Unit tests for evolution write-back.
- `backend/tests/unit/test_hallucination_rate.py:1` — """hallucination_rate 补测 + schema 三段式契约。
- `backend/tests/unit/test_hallucination_rate.py:14` — # 1. QualityDashboard schema 契约（三段式）
- `backend/tests/unit/test_loop_orchestrator.py:327` — # metric row fields also surfaced
- `backend/tests/unit/test_loop_orchestrator.py:420` — # Fallback path still has path_length key (metric row contract)
- `frontend/src/components/loop/__tests__/LoopStepGraph.spec.ts:3` — * Verifies 口径拆解行：nodes_written / edges_written (来自 graph_sync 既有契约).
- `frontend/src/components/loop/__tests__/LoopStepMatch.spec.ts:3` — * Verifies M5 分数拆解行（required_avg / bonus_avg / 权重 / inflated）.
- `frontend/src/components/loop/__tests__/LoopStepSkills.spec.ts:3` — * Verifies 口径拆解行（技能数 + 信任度均值）+ model_used 透传
- `frontend/src/pages/__tests__/PositionDetail.spec.ts:148` — // ──: 雷达图缺数据降级（沿 M5：无画像岗位不返回 404）──

#### `D-06`  （20 处）
- `backend/alembic/versions/032_add_written_back_to_evolution_changelog.py:1` — """Add written_back column to evolution_changelog (write-back marker).
- `backend/app/core/pipeline/loop/steps/extract.py:1` — """— Skill Extraction.
- `backend/app/core/pipeline/loop/steps/extract.py:80` — # surface the actual model used + aggregate confidence so the
- `backend/app/core/pipeline/loop/steps/extract.py:126` — # explicit model + aggregate confidence
- `backend/app/core/pipeline/loop_orchestrator.py:202` — """Compat delegate → ``steps.extract.run_extract_step`` (model_used)."""
- `backend/app/core/pipeline/stages/graph_sync.py:228` — # ── Position PG↔Neo4j 一致性校验（；沿 M3 仅观察不阻断）──
- `backend/app/core/pipeline/stages/graph_sync.py:289` — **仅观察不阻断**：任何异常都被吞掉并记日志，不影响 graph_sync 阶段结果（沿 M3）。
- `backend/app/core/pipeline/stages/import_.py:364` — # 阶段末 PG↔Neo4j 一致性告警（仅日志，不阻断不改数据）
- `backend/app/services/pipeline_consistency.py:1` — """Pipeline PG↔Neo4j 一致性告警服务。
- `backend/tests/unit/test_cancel_run.py:67` — """Test: cancelling a completed run raises RunAlreadyTerminalError."""
- `backend/tests/unit/test_cancel_run.py:87` — """Test: cancelling a non-existent run raises RunNotFoundError."""
- `backend/tests/unit/test_cancel_run.py:102` — """Test: re-cancelling raises RunAlreadyTerminalError."""
- `backend/tests/unit/test_evolution_orchestrator.py:103` — """write-back raising → warning appended, _diff_and_persist still returns."""
- `backend/tests/unit/test_evolution_orchestrator.py:209` — """graph_projection raising → warning appended, pipeline continues."""
- `backend/tests/unit/test_evolution_write_back.py:1` — """Unit tests for evolution write-back.
- `backend/tests/unit/test_evolution_write_back.py:418` — """fail-soft: any exception → warning appended, no raise."""
- `backend/tests/unit/test_graph_sync_position_drift.py:131` — """取数抛异常 → 吞掉并返回 0，绝不向上抛（M3 仅观察不阻断）。"""
- `backend/tests/unit/test_loop_orchestrator.py:301` — # degradation判定 + model_used 透传 (T7)
- `backend/tests/unit/test_stages_import.py:52` — """pipeline_consistency 服务提供仅日志告警（不改数据）。"""
- `frontend/src/components/loop/__tests__/LoopStepSkills.spec.ts:3` — * Verifies 口径拆解行（技能数 + 信任度均值）+ model_used 透传

#### `D-07`  （13 处）
- `backend/app/core/evolution/consistency.py:1` — """PG ↔ Neo4j REQUIRES-edge consistency check.
- `backend/app/core/pipeline/stages/graph_sync.py:1` — """Pipeline graph_sync 阶段。
- `backend/app/core/pipeline/stages/graph_sync.py:175` — # 可选 reconcile 子步骤（默认关闭）
- `backend/app/core/pipeline/stages/graph_sync.py:189` — # 与 reconcile 不同：这里只比对计数并告警，不改任何数据。
- `backend/app/core/pipeline/stages/graph_sync.py:336` — """对账子步骤 — 执行 PG↔Neo4j 一致性补齐。
- `backend/scripts/backfill_graph_to_pg.py:112` — # 一次性对账脚本不作自动调度，仅提示手动重投影
- `backend/tests/integration/test_evolution_pipeline.py:202` — # 4) summary must carry the consistency key
- `backend/tests/unit/test_evolution_consistency.py:1` — """Unit tests for PG ↔ Neo4j consistency check (read-only).
- `backend/tests/unit/test_evolution_consistency.py:223` — """only read Cypher — no MERGE/SET/CREATE/DELETE ever issued."""
- `backend/tests/unit/test_evolution_orchestrator.py:170` — """summary carries the consistency dict even when check succeeds."""
- `backend/tests/unit/test_evolution_orchestrator.py:241` — """consistency check raising → warning + summary error dict, no abort."""
- `backend/tests/unit/test_stages_graph_sync.py:25` — """reconcile 子步骤事件存在（sub_step="reconcile"）。"""
- `backend/tests/unit/test_stages_graph_sync.py:66` — """原对账脚本打 DEPRECATED banner。"""

#### `D-08`  （6 处）
- `backend/scripts/backfill_graph_to_pg.py:33` — # 4 个无 canonical_id 的 Position（无法参与演化回写解析，静默跳过）。
- `backend/scripts/backfill_graph_to_pg.py:104` — # 3)：4 个无 canonical_id 岗位补齐（PG 建行 + Neo4j SET canonical_id）
- `backend/scripts/backfill_graph_to_pg.py:118` — """为 4 个无 canonical_id 的岗位补齐 PG PositionRecord + Neo4j canonical_id。
- `backend/tests/integration/test_evolution_pipeline.py:79` — # PositionRecord so write-back can resolve position_id (: real row, not fabricated)
- `backend/tests/unit/test_config.py:55` — """所有 LLM key 为空时输出 WARNING，含 MIMO_API_KEY 和 DEEPSEEK_API_KEY。"""
- `backend/tests/unit/test_evolution_write_back.py:404` — """unresolvable position → skip + warning, never fabricate."""

#### `D-09`  （2 处）
- `backend/tests/unit/test_evolution_orchestrator.py:126` — """evidence_json includes factors {source, stability, type}."""
- `backend/tests/unit/test_health.py:67` — """/health/detail 返回 200 含 services(4) + llm_keys(3 bool) + demo_data。"""

#### `D-10`  （3 处）
- `backend/app/core/pipeline/loop/common.py:1` — """Loop orchestration shared types & persistence helpers.
- `backend/app/core/pipeline/stages/common.py:1` — """Pipeline 阶段公共层。
- `backend/tests/unit/test_evolution_emergence_path.py:379` — """信任度权重常量锁定（保持现状、不配置化）。"""

#### `D-11`  （5 处）
- `backend/app/api/v1/evolution.py:82` — """演化看板 KPI 行（涌现数/信任均值/CII 均值/预警数)。"""
- `backend/app/core/pipeline/stages/graph_sync.py:1` — """Pipeline graph_sync 阶段。
- `backend/app/services/evolution_service.py:120` — """Build the 4-KPI row for the evolution dashboard.
- `backend/tests/unit/test_evolution_api_service.py:226` — # KPI aggregation — build_evolution_kpi
- `frontend/src/stores/__tests__/evolution.test.ts:366` — // ── 10. fetchKpi action  ──

#### `D-12`  （3 处）
- `backend/tests/unit/test_evolution_api_service.py:226` — # KPI aggregation — build_evolution_kpi
- `backend/tests/unit/test_evolution_api_service.py:256` — """build_evolution_kpi — real trust aggregate + empty→zeros."""
- `backend/tests/unit/test_evolution_api_service.py:280` — # never fabricated estimates.

#### `D-13`  （1 处）
- `frontend/src/stores/__tests__/evolution.test.ts:418` — // ── 11. refreshAll action  ──

#### `D-15`  （8 处）
- `backend/app/core/pipeline/stages/crawl.py:1` — """Pipeline crawl 阶段。
- `backend/app/core/pipeline/stages/crawl.py:286` — # 每个数据源发 1 条 sub_step 事件
- `backend/app/core/pipeline/stages/import_.py:1` — """Pipeline import 阶段。
- `backend/app/core/pipeline/stages/import_.py:184` — # normalize 子步骤事件
- `backend/app/core/pipeline/stages/import_.py:239` — # persist 子步骤事件 (LLM 抽取完成 = 持久化就绪)
- `backend/tests/unit/test_stages_common.py:47` — """publish_stage_progress 必须支持 sub_step 参数。"""
- `backend/tests/unit/test_stages_crawl.py:35` — """每数据源/平台发 sub_step=crawl:<source_name> 事件。"""
- `backend/tests/unit/test_stages_import.py:16` — """import 阶段发 3 子步骤事件（extract/normalize/persist）。"""

#### `D-16`  （4 处）
- `backend/app/core/pipeline/cron_scheduler.py:37` — # 5 字段值域常量
- `backend/app/core/pipeline/cron_scheduler.py:95` — """完整校验 cron 表达式，返回 {valid: bool, errors: [{field, value, message}]}。
- `backend/tests/unit/test_cron_validation.py:1` — """Cron 校验完整测试。
- `backend/tests/unit/test_cron_validation.py:108` — """错误返回格式契约（错误格式 CRON_INVALID）。"""

#### `D-18`  （6 处）
- `backend/app/core/pipeline/stages/clean.py:1` — """Pipeline clean 阶段。
- `backend/app/core/pipeline/stages/crawl.py:1` — """Pipeline crawl 阶段。
- `backend/app/core/pipeline/stages/dedup.py:1` — """Pipeline dedup 阶段。
- `backend/app/core/pipeline/stages/graph_sync.py:1` — """Pipeline graph_sync 阶段。
- `backend/app/core/pipeline/stages/import_.py:1` — """Pipeline import 阶段。
- `backend/app/core/pipeline/stages/timeseries.py:1` — """Pipeline timeseries 阶段。

### 编号族 `Step`

#### `Step3`  （1 处）
- `backend/tests/unit/test_loop_orchestrator_coverage.py:572` — # should have failed because driver acquisition failed

#### `Step5`  （1 处）
- `backend/tests/unit/test_loop_orchestrator_coverage.py:505` — # with auto plan creation (session path)

#### `Step 0`  （3 处）
- `frontend/e2e/data-integrity.spec.ts:396` — // 输入技能
- `frontend/e2e/user-interaction.spec.ts:114` — // 确认在 — 应有"录入你的技能"标题
- `frontend/src/pages/MatchDiagnosis.vue:61` — // ──: 上传简历 ──

#### `Step 1`  （30 处）
- `backend/app/api/v1/position.py:332` — # Load timeseries data for frequency history
- `backend/app/core/extraction/graph_writer.py:713` — # Merge Position node using standalone retry-enabled function
- `backend/app/core/extraction/jd_extract.py:201` — # Fill prompt
- `backend/app/core/learning/path_engine.py:491` — # Build skill list with time estimates
- `backend/app/core/pipeline/loop/status.py:210` — # JD输入
- `backend/app/core/pipeline/loop/steps/validate.py:1` — """— JD input validation + target_position resolution.
- `backend/app/core/pipeline/loop/steps/validate.py:29` — """Validate JD input and resolve effective target_position.
- `backend/app/core/pipeline/loop_orchestrator.py:102` — # validation
- `backend/app/core/pipeline/loop_orchestrator.py:193` — """compat delegate → ``steps.validate.run_validate_step``."""
- `backend/app/core/pipeline/stages/graph_sync.py:342` — # PG ← Neo4j (补齐缺失 skill/position)
- `backend/app/services/graph_overview.py:173` — # 行业归一（13 大行业，对标 spec 5.3）
- `backend/app/services/graph_overview.py:220` — """按 Position.name + industry 关键词分类到 14 大行业。
- `backend/app/services/graph_service.py:333` — # ── Fallback: when no KA nodes, classify positions by 行业  ──
- `backend/app/services/timeseries_service.py:34` — # ──: Find the date range of extraction records ──
- `backend/real_full_test.py:49` — # ───: live internet crawl (already proven, reconfirm) ───
- `backend/scripts/phase5_rebuild_neo4j.py:1` — """修复 Neo4j 字段映射 + 清空 + 从 PG 重建
- `backend/scripts/phase5_rebuild_neo4j.py:142` — """执行：备份 → 清空 → 从 PG 重建。"""
- `backend/scripts/phase5_rebuild_neo4j.py:154` — # 备份
- `backend/tests/unit/test_graph_services.py:820` — # ── graph_service: fetch_overview_by_domain (M1 closure) ─
- `backend/tests/unit/test_graph_services.py:824` — """fetch_overview_by_domain —: 行业归一(13 大行业)视图。
- `evaluation/judge_eval.py:45` — # alias normalization (Kafka <-> Apache Kafka etc.)
- `frontend/e2e/data-integrity.spec.ts:409` — // 选择岗位
- `frontend/e2e/user-interaction.spec.ts:135` — // 应进入 — 应有"选择目标岗位"标题 (用 heading role 避免匹配到步骤条)
- `frontend/src/components/loop/LoopStepInput.vue:3` — * LoopStepInput —: JD Input
- `frontend/src/components/loop/LoopStepInput.vue:198` — /* ──: JD Input ── */
- `frontend/src/pages/LoopDemo.vue:8` — * - LoopStepInput.vue —: JD Input
- `frontend/src/pages/LoopDemo.vue:47` — // ── state ──
- `frontend/src/pages/MatchDiagnosis.vue:143` — // ──: 选岗 ──
- `frontend/src/stores/__tests__/loop.test.ts:169` — // is always set to success immediately
- `frontend/src/stores/__tests__/loop.test.ts:222` — // is set to success before the API call, so no running step to mark failed

#### `Step 2`  （30 处）
- `backend/app/api/v1/position.py:346` — # Run emergence detection
- `backend/app/core/extraction/graph_writer.py:723` — # Merge Skill nodes and create REQUIRES relationships using standalone functions
- `backend/app/core/extraction/jd_extract.py:229` — # Call LLM
- `backend/app/core/learning/path_engine.py:494` — # Load per-skill learning hours from Neo4j (best-effort)
- `backend/app/core/pipeline/loop/status.py:224` — # 技能提取
- `backend/app/core/pipeline/loop/steps/extract.py:1` — """— Skill Extraction.
- `backend/app/core/pipeline/loop/steps/extract.py:32` — """Extract skills from JD using LLM pipeline.
- `backend/app/core/pipeline/loop_orchestrator.py:112` — # extraction
- `backend/app/core/pipeline/stages/graph_sync.py:343` — # PG → Neo4j (补齐缺失 REQUIRES edges)
- `backend/app/services/graph_overview.py:118` — # heat 视图（按技能需求频率着色）
- `backend/app/services/graph_overview.py:535` — # 热度视图（技能需求频次）
- `backend/app/services/graph_overview.py:544` — """按技能需求频率排序的"热度视图"。
- `backend/app/services/graph_sync.py:218` — # ── 1. Build extraction from the current pipeline run's data ──
- `backend/app/services/timeseries_service.py:47` — # ──: Build monthly windows covering the date range ──
- `backend/real_full_test.py:61` — # ───: persist to raw_jd_records ───
- `backend/scripts/phase5_rebuild_neo4j.py:158` — # 清空
- `backend/tests/unit/test_graph_services.py:720` — # ── graph_overview: fetch_overview_by_heat (M1 closure) ─
- `backend/tests/unit/test_loop_orchestrator.py:64` — # QA B1: target_position 可选,空值不拒绝(从 JD 推断)。
- `backend/tests/unit/test_loop_orchestrator.py:172` — """returns FAILED when extraction raises an exception."""
- `backend/tests/unit/test_loop_orchestrator.py:271` — """returns SUCCESS when extraction works."""
- `backend/tests/unit/test_loop_orchestrator.py:290` — """returns FAILED when extraction returns success=false."""
- `backend/tests/unit/test_loop_orchestrator.py:304` — """(extract) must surface the actual LLM model name in data so the
- `backend/tests/unit/test_loop_orchestrator_coverage.py:186` — """QA B1: 空 target_position 不在 step1 拒绝,继续后续步骤(从 JD 推断岗位)。"""
- `backend/tests/unit/test_loop_service.py:94` — # QA B1: target_position 按 OpenAPI 契约可选,空值不拒绝(从 JD 推断岗位)。
- `evaluation/judge_eval.py:50` — # basic normalization (remove non-alphanumeric, lowercase)
- `frontend/src/components/loop/LoopStepSkills.vue:3` — * LoopStepSkills —: Skill Extraction Results
- `frontend/src/components/loop/LoopStepSkills.vue:255` — /* ──: Extracted Skills ── */
- `frontend/src/pages/LoopDemo.vue:9` — * - LoopStepSkills.vue —: Skill Extraction
- `frontend/src/pages/MatchDiagnosis.vue:189` — // ──: 开始诊断 ──
- `frontend/src/stores/__tests__/loop.test.ts:171` — // skill extraction

#### `Step 3`  （25 处）
- `backend/app/api/v1/admin.py:82` — """手动触发 PG → Neo4j 同步 + 孤儿节点剪枝。
- `backend/app/core/extraction/graph_writer.py:763` — # Build and write ontology triples for extended relationships
- `backend/app/core/extraction/jd_extract.py:260` — # Parse JSON
- `backend/app/core/learning/path_engine.py:497` — # Build prerequisite graph (Neo4j → fallback → extras)
- `backend/app/core/pipeline/cron_scheduler.py:324` — # 定时 reconcile 状态
- `backend/app/core/pipeline/cron_scheduler.py:338` — # 定时 reconcile
- `backend/app/core/pipeline/loop/status.py:238` — # 图谱更新
- `backend/app/core/pipeline/loop/steps/graph_update.py:1` — """— Neo4j graph sync.
- `backend/app/core/pipeline/loop/steps/graph_update.py:32` — """Sync extracted skills/positions into Neo4j graph.
- `backend/app/core/pipeline/loop_orchestrator.py:123` — # graph update — acquire Neo4j driver
- `backend/app/services/timeseries_service.py:50` — # ──: Load skill→category mapping from skill_records ──
- `backend/real_full_test.py:93` — # ───: real LLM extraction with qwen2.5:7b ───
- `backend/scripts/phase5_rebuild_neo4j.py:162` — # 从 PG 重建
- `backend/tests/unit/test_loop_orchestrator.py:229` — """returns FAILED when Neo4j driver is unavailable."""
- `backend/tests/unit/test_loop_orchestrator.py:245` — """returns FAILED when sync_from_pipeline fails."""
- `backend/tests/unit/test_loop_orchestrator.py:257` — """returns SUCCESS when sync works."""
- `frontend/src/components/GapAnalysisReport.vue:3` — * 差距分析报告 — 子组件
- `frontend/src/components/loop/LoopStepGraph.vue:3` — * LoopStepGraph —: Graph Update
- `frontend/src/components/loop/LoopStepGraph.vue:175` — /* ──: Graph ── */
- `frontend/src/composables/useLoopGraph.ts:2` — * useLoopGraph — G6 mini-graph rendering logic for LoopDemo
- `frontend/src/pages/LoopDemo.vue:10` — * - LoopStepGraph.vue —: Graph Update (uses useLoopGraph)
- `frontend/src/pages/LoopDemo.vue:75` — // 完成后渲染 G6 图谱
- `frontend/src/pages/MatchDiagnosis.vue:274` — // ──/4: computed for sub-components ──
- `frontend/src/stores/__tests__/loop.test.ts:174` — // graph update
- `frontend/src/stores/__tests__/loop.test.ts:202` — // graph update should be degraded

#### `Step 4`  （26 处）
- `backend/app/api/v1/admin.py:171` — # 写 audit_events 记录
- `backend/app/api/v1/admin_data_truth.py:274` — # 计算同步健康度
- `backend/app/core/evolution/orchestrator.py:181` — # ──: path recommender (single batch) ──
- `backend/app/core/extraction/jd_extract.py:267` — # Pydantic validation
- `backend/app/core/learning/path_engine.py:500` — # Topological sort
- `backend/app/core/pipeline/cron_scheduler.py:354` — # 写 audit_events 供健康度监控查询
- `backend/app/core/pipeline/loop/status.py:247` — # 匹配诊断
- `backend/app/core/pipeline/loop/steps/match.py:1` — """— Match diagnosis.
- `backend/app/core/pipeline/loop/steps/match.py:42` — """Run match diagnosis with extracted skills vs target position.
- `backend/app/core/pipeline/loop_orchestrator.py:139` — # match diagnosis (: skip if no effective target_position)
- `backend/app/services/graph_sync.py:253` — # with the target_position name so match diagnosis can find it.
- `backend/app/services/timeseries_service.py:55` — # ──: Aggregate per (skill, month) ──
- `backend/real_full_test.py:144` — # ───: orchestrator (uses both fixture + real data) ───
- `backend/scripts/phase5_rebuild_neo4j.py:175` — # 验证
- `backend/tests/unit/test_loop_orchestrator.py:185` — """returns FAILED when no skills are available."""
- `backend/tests/unit/test_loop_orchestrator.py:197` — """returns FAILED when match raises an exception."""
- `backend/tests/unit/test_loop_orchestrator.py:211` — """returns SUCCESS when match works."""
- `backend/tests/unit/test_overview_dimensions.py:1` — """验证 4 个 overview 端点（domain/tech_stack/level/heat）：
- `frontend/src/components/LearningPathPlan.vue:3` — * 学习路径规划 — 子组件
- `frontend/src/components/loop/LoopStepMatch.vue:3` — * LoopStepMatch —: Match Diagnosis
- `frontend/src/components/loop/LoopStepMatch.vue:385` — /* ──: Match Diagnosis ── */
- `frontend/src/pages/LoopDemo.vue:11` — * - LoopStepMatch.vue —: Match Diagnosis (radar chart + gap analysis)
- `frontend/src/pages/LoopDemo.vue:51` — // ── ref (for buildRadarData) ──
- `frontend/src/pages/LoopDemo.vue:80` — // 完成后渲染雷达图
- `frontend/src/stores/__tests__/loop.test.ts:176` — // match diagnosis
- `frontend/src/stores/__tests__/loop.test.ts:204` — // match should be degraded

#### `Step 5`  （17 处）
- `backend/app/core/evolution/orchestrator.py:196` — # ──: refresh skill timeseries (existing service) ──
- `backend/app/core/extraction/jd_extract.py:351` — # Normalize skills
- `backend/app/core/learning/path_engine.py:503` — # Build SkillNodes in topo order
- `backend/app/core/pipeline/loop/status.py:262` — # 学习路径
- `backend/app/core/pipeline/loop/steps/learning_path.py:1` — """— Learning path derivation.
- `backend/app/core/pipeline/loop/steps/learning_path.py:66` — """Derive learning path from match gaps and auto-create plan.
- `backend/app/core/pipeline/loop_orchestrator.py:155` — # learning path (: skip if no target or match skipped)
- `backend/app/services/graph_overview.py:480` — # 3 维泡始终保留(空 level 渲染为 0/0 透明泡),但占位不计入 total 计数。
- `backend/app/services/graph_overview.py:495` — # 兜底维度。PG 中 0 个 lv-junior 岗时，确保 3 维泡全在（0/0 透明），前端不会因缺桶渲染破图。
- `backend/app/services/timeseries_service.py:91` — # ──: Upsert into skill_timeseries ──
- `backend/real_full_test.py:156` — # ───: verify evolution API endpoints ───
- `backend/tests/unit/test_overview_dimensions.py:48` — # level 端点必须 3 维泡保满（含 junior 兜底）
- `frontend/src/components/loop/LoopStepLearning.vue:3` — * LoopStepLearning —: Learning Path
- `frontend/src/components/loop/LoopStepLearning.vue:183` — /* ──: Learning Path ── */
- `frontend/src/pages/LoopDemo.vue:12` — * - LoopStepLearning.vue —: Learning Path
- `frontend/src/stores/__tests__/loop.test.ts:178` — // learning path
- `frontend/src/stores/__tests__/loop.test.ts:206` — // learning path should be degraded

#### `Step 6`  （3 处）
- `backend/app/core/extraction/jd_extract.py:390` — # Anti-hallucination check
- `backend/app/core/learning/path_engine.py:538` — # Calculate totals
- `backend/app/core/learning/path_engine.py:542` — # Build phases

#### `Step 7`  （1 处）
- `backend/app/core/extraction/jd_extract.py:441` — # Dictionary post-filter — keep only LLM skills that match SKILL_ALIAS

#### `Step 8`  （1 处）
- `backend/app/core/extraction/jd_extract.py:465` — # — 非 CJK 岗位名翻译钩子 (RemoteOK 等英文 JD 源)

#### `Step 4.5`  （1 处）
- `backend/app/core/extraction/jd_extract.py:313` — # Clean up Chinese suffixes from skill names

#### `Step 6.5`  （1 处）
- `backend/app/core/extraction/jd_extract.py:419` — # 规则过滤 — 非技能词黑名单(职责/软词/行业词)

### 编号族 `PLAN`

#### `PLAN-002`  （4 处）
- `backend/app/core/pipeline/stages/crawl.py:32` — # executor 与单源调度端点共用; 补入 juejin/remoteok (003 落地后遗漏注册)
- `crawler/spiders/juejin.py:1` — """掘金 sitemap spider — D5 非结构化源。
- `crawler/tests/test_juejin_spider.py:1` — """掘金 sitemap spider 测试。
- `crawler/tests/test_spider_compliance_wiring.py:71` — """掘金 sitemap spider 必须经 compliance.fetch."""

#### `PLAN-003`  （4 处）
- `backend/tests/unit/test_i18n_translation_hook.py:1` — """/I18N-01: jd_extract 管线翻译钩子接线测试。
- `crawler/spiders/remoteok.py:1` — """RemoteOK API spider — 英文 JD 源。
- `crawler/tests/test_remoteok_spider.py:1` — """RemoteOK spider 测试 (mock compliance.fetch)。"""
- `crawler/tests/test_spider_compliance_wiring.py:99` — """RemoteOK spider 必须经 compliance.fetch."""

#### `PLAN-004`  （2 处）
- `crawler/spiders/v2ex_remote.py:28` — # 走 compliance.fetch（robots 检查 + QPS≤1 + compliance_log），
- `crawler/tests/test_spider_compliance_wiring.py:1` — """/ 回归：本地 spider 必须经由 crawler.compliance.fetch。

#### `PLAN-005`  （3 处）
- `backend/app/core/pipeline/stages/crawl.py:101` — # api/rss 源同样参与 crawl 阶段（修复在 rebase 中丢失，恢复）
- `backend/app/core/pipeline/stages/crawl.py:210` — # 复用本模块的 build_spider_registry (注册)
- `crawler/tests/test_run_incremental.py:10` — """_crawl_site 路由到真实开放源，未知源诚实返回空。"""

#### `PLAN-009`  （2 处）
- `backend/alembic/versions/027_add_simhash_to_jd_raw.py:1` — """Add simhash column to jd_raw for near-duplicate detection.
- `crawler/persistence/models.py:60` — # 拆列方案——content_hash 守精确去重(UNIQUE),

#### `PLAN-012`  （6 处）
- `backend/alembic/versions/028_add_source_trust_config.py:1` — """Add source_trust_config table (§4.2).
- `backend/app/core/trust/jd_trust.py:1` — """§7.1 多源交叉验证的数据信任度模型.
- `backend/app/models/pipeline_models.py:338` — """数据源信任度配置 (§4.2)。
- `backend/app/services/trust_config_service.py:1` — """source_trust_config 幂等播种。
- `backend/tests/unit/test_jd_trust.py:1` — """§7.1 JD 级 4 因子信任度模型测试。"""
- `backend/tests/unit/test_trust_config_service.py:1` — """source_trust_config 幂等播种测试。"""

#### `PLAN-013`  （10 处）
- `backend/tests/unit/test_admin_ab_service.py:1` — """Coverage boost: services/admin_ab_service.py — A/B 聚合纯逻辑 (收尾)。"""
- `backend/tests/unit/test_dashboard_route.py:1` — """Coverage boost: api/v1/dashboard.py — 路由层组装。
- `backend/tests/unit/test_extract_repo.py:1` — """Coverage boost: repositories/extract_repo.py — PG 抽取持久化。
- `backend/tests/unit/test_extraction_service.py:1` — """Coverage boost: services/extraction_service.py — service 边界 re-export 防回归。
- `backend/tests/unit/test_fetch_boss.py:1` — """Coverage boost: services/fetch_boss.py — BOSS 适配器。
- `backend/tests/unit/test_health_monitor.py:1` — """Coverage boost: services/health_monitor.py — 加权熔断/启动探针/退避。
- `backend/tests/unit/test_import_service.py:1` — """Coverage boost: services/import_service.py — JD 导入计数/PII/审计回归。
- `backend/tests/unit/test_quality_repo.py:1` — """Coverage boost: repositories/quality_repo.py — 幻觉趋势聚合。
- `backend/tests/unit/test_timeseries_loader.py:1` — """Coverage boost: core/evolution/timeseries_loader.py — 时序加载与分组。
- `backend/tests/unit/test_translation.py:1` — """Coverage boost: core/extraction/translation.py — CJK 检测与翻译回退。"""

#### `PLAN-014`  （16 处）
- `backend/app/schemas/admin.py:1` — """管理域 Schema：图谱节点管理/数据真相对账 (批次13 迁入集中管理)。"""
- `backend/app/schemas/datasource.py:1` — """数据源域 Schema：数据源详情/统计/健康/同步响应 (批次8 迁入集中管理)。"""
- `backend/app/schemas/evolution.py:1` — """演化域 Schema：职业路径/预警/行业报告/演化趋势 (批次10-12 迁入集中管理)。"""
- `backend/app/schemas/judge.py:1` — """Judge 域 Schema (批次10)。
- `backend/app/schemas/loop.py:1` — """Loop 域 Schema (批次12).
- `backend/app/schemas/prompt.py:1` — """Prompt 管理域 Schema (批次7)。
- `backend/app/schemas/quality.py:1` — """Quality 域 Schema (批次11).
- `backend/tests/unit/test_import_jd_schema.py:1` — """契约: import_jd 路由零内联 + 3 模型可达 (批次8)。
- `backend/tests/unit/test_judge_schema.py:1` — """契约: judge 路由零内联 + 6 模型可达 (批次10)。
- `backend/tests/unit/test_prompt_schema.py:1` — """契约回归: admin_prompts 路由零内联模型 (批次7)。
- `backend/tests/unit/test_route_zero_inline.py:1` — """批次9: 全路由零内联契约回归 (锁定 + 登记 follow-up)。
- `backend/tests/unit/test_route_zero_inline.py:29` — # 已零内联 (批次 2-8 已闭环) — 直接 PASS
- `frontend/src/types/contract-schemas.d.ts:2` — * 契约 JSON Schema 导入声明。
- `frontend/vite.config.ts:14` — // 批次17: 契约路径 alias (容器/本地一致, 修复容器内../../../ 不可达白屏)
- `frontend/vite.config.ts:22` — // 允许导入仓库根下 starmap-contracts/ 的契约 JSON Schema
- `frontend/vitest.config.ts:14` — // 允许导入仓库根下 starmap-contracts/ 的契约 JSON Schema

#### `PLAN-015`  （1 处）
- `backend/app/api/v1/auth.py:48` — # 2026-08-05：消除路由内联重复定义，启用更严格的字段约束）

#### `PLAN-006③`  （1 处）
- `backend/alembic/versions/027_add_simhash_to_jd_raw.py:1` — """Add simhash column to jd_raw for near-duplicate detection.

#### `PLAN-007a`  （2 处）
- `backend/app/api/v1/admin_data_truth.py:30` — # /admin/* 端点必须叠加 require_admin，
- `backend/tests/unit/test_admin_data_truth.py:1` — """admin_data_truth 端点门禁测试。

#### `PLAN-007b`  （2 处）
- `backend/tests/unit/test_contract_regression.py:13` — # 凭据单一来源 = 环境变量（默认值为 dev/demo 引导账号）。
- `backend/tests/unit/test_overview_dimensions.py:13` — # 凭据单一来源 = 环境变量（默认值为 dev/demo 引导账号，

#### `PLAN-015①`  （4 处）
- `backend/app/config.py:378` — """解析 trusted_proxy_cidrs 为 ipaddress 网列表 (惰性, 只解析一次)。"""
- `backend/app/core/security/client_ip.py:1` — """客户端真实 IP 提取。
- `backend/app/core/security/client_ip.py:75` — """settings-aware 客户端 IP (集中守门, follow-up)。
- `backend/tests/unit/test_client_ip.py:1` — """Coverage boost: core/security/client_ip.py — XFF 可信代理提取。

#### `PLAN-015②`  （2 处）
- `backend/app/api/v1/auth.py:287` — # 通道决策 (settings.forgot_password_delivery)
- `backend/tests/unit/test_forgot_password_delivery.py:1` — """Coverage boost: api/v1/auth.py — forgot-password 通道决策。

#### `PLAN-015③`  （2 处）
- `backend/app/services/dev_token.py:1` — """dev-token 集中守门。
- `backend/tests/unit/test_dev_token.py:1` — """Coverage boost: services/dev_token.py — dev-token 集中守门.

### 编号族 `Plan`

#### `Plan 02`  （2 处）
- `backend/tests/unit/test_pipeline_dag.py:1` — """DAG 串行调度 + JdStatus.cleaned 状态机测试。"""
- `frontend/src/components/PipelineStageCard.vue:14` — // 阶段描述，供 hover tooltip 引导新用户

#### `Plan 03`  （3 处）
- `backend/app/core/pipeline/engine.py:1` — """Pipeline DAG 执行引擎（拆分：从 executor.py 迁出）。
- `frontend/src/components/pipeline/ConfigDialog.vue:6` — * PipelineMonitor 流水线配置弹窗子组件（ 从内联模板抽出）。
- `frontend/src/composables/useVerifyLog.ts:2` — * 闭环验证日志 composable（ 从 PipelineMonitor.vue 抽出）。

#### `Plan 01-03`  （4 处）
- `frontend/src/components/Graph3D.vue:3` — * 2026-08-13: ( 全景图谱) + 01-04:
- `frontend/src/components/Graph3D.vue:174` — // 节点降噪 LOD + cluster 折叠 — 镜像 2D useGraphLOD + useGraphClustering
- `frontend/src/components/Graph3D.vue:189` — // maxNodes 优先 (background mode);否则 cluster 折叠
- `frontend/src/composables/graph3d/index.ts:4` — * 2026-08-13: + 01-04 创建

#### `Plan 02 Task 2`  （3 处）
- `backend/tests/unit/test_pipeline_orchestrator.py:60` — # serial DAG (clean 依赖 dedup, import 依赖 clean,
- `backend/tests/unit/test_pipeline_orchestrator.py:111` — # clean 现在依赖 dedup，必须 dedup 完成才能 ready
- `frontend/src/components/PipelineDag.vue:408` — /* DAG 串行箭头（: clean 依赖 dedup，取消 fork/merge） */

#### `Plan 03 Task 0`  （1 处）
- `backend/tests/unit/test_pipeline_t5_fix.py:1` — """T5 bug 修复 — execute_clean→cleaned + import reads cleaned + batch_size 可配。

#### `Plan 03 Task 1`  （2 处）
- `backend/tests/unit/test_stages_common.py:1` — """stages/common.py 公共层测试。
- `backend/tests/unit/test_stages_timeseries.py:1` — """stages/timeseries.py 阶段测试。

#### `Plan 03 Task 2`  （1 处）
- `backend/tests/unit/test_stages_dedup.py:1` — """stages/dedup.py 阶段测试。

#### `Plan 03 Task 3`  （1 处）
- `backend/tests/unit/test_stages_clean.py:1` — """stages/clean.py 阶段测试。

#### `Plan 03 Task 4`  （1 处）
- `backend/tests/unit/test_stages_crawl.py:1` — """stages/crawl.py 阶段测试。

#### `Plan 03 Task 5`  （1 处）
- `backend/tests/unit/test_stages_import.py:1` — """stages/import_.py 阶段测试 + SSOT 可观测化测试。

#### `Plan 03 Task 6`  （1 处）
- `backend/tests/unit/test_stages_graph_sync.py:1` — """stages/graph_sync.py 阶段测试。

#### `Plan 03 Task 7`  （2 处）
- `backend/tests/unit/test_layer_boundary.py:50` — # pipeline 按领域拆 6 子路由，逐一纳入层边界守卫
- `backend/tests/unit/test_pipeline_routes_split.py:1` — """APIRouter 子路由分片验证。

#### `Plan 03 Task 8`  （5 处）
- `frontend/src/components/pipeline/QualityPanel.vue:3` — * PipelineMonitor 数据质量面板（ 实际迁移）。
- `frontend/src/composables/usePipelineMonitor.ts:2` — * 数据流水线监控页 composable（ 拆分后瘦身 < 400 行）。
- `frontend/src/composables/useSchedules.ts:2` — * 定时调度 CRUD composable（ 实际迁移）。
- `frontend/src/composables/useTriggerPipeline.ts:2` — * 触发/取消/重试/续跑/强制操作 composable（ 实际迁移）。
- `frontend/src/pages/PipelineMonitor.vue:3` — * 数据流水线监控页 — 拆子组件后瘦身 < 600 行。

#### `Plan 03 Task 9`  （2 处）
- `frontend/src/components/PipelineStageCard.vue:15` — // ( T6): 阶段描述 — 含作用 + 依赖 + 状态含义三要素
- `frontend/src/components/PipelineStageCard.vue:153` — // ( T6): 拼装三要素 hover 文本

#### `Plan 03 Task 10`  （3 处）
- `frontend/src/stores/pipelineRun.ts:160` — // 子步骤事件订阅 state
- `frontend/src/stores/pipelineRun.ts:320` — // 订阅 sub_step 子步骤事件
- `frontend/src/stores/pipelineRun.ts:449` — // 子步骤事件订阅 state

#### `Plan 03 Task 11`  （3 处）
- `backend/app/core/pipeline/cron_scheduler.py:37` — # 5 字段值域常量
- `backend/tests/unit/test_cron_validation.py:1` — """Cron 校验完整测试。
- `frontend/src/utils/cronValidator.ts:1` — // Cron 表达式完整校验工具.

#### `Plan 03 Task 12`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:2` — * PipelineMonitor.vue 测试套件。

#### `Plan 01-02 Task 1`  （1 处）
- `backend/tests/unit/test_graph_overview_heuristics.py:197` — # 6. (M1): _classify_industry 纯函数测试

#### `Plan 01-03 Task 1`  （1 处）
- `frontend/src/composables/graph3d/useGraph3DLOD.ts:5` — * 2026-08-13: ( 全景图谱) — 镜像 useGraphLOD.ts

#### `Plan 01-03 Task 2`  （1 处）
- `frontend/src/composables/graph3d/useGraph3DClustering.ts:10` — * 2026-08-13: ( 全景图谱) — 镜像 2D useGraphClustering

#### `Plan 01-03 Task 4`  （1 处）
- `frontend/src/components/__tests__/Graph3D.spec.ts:4` — * 2026-08-13: (M1 全景图谱)

#### `Plan 01-04 Task 1`  （1 处）
- `frontend/src/composables/graph3d/useGraph3DLifecycle.ts:4` — * 2026-08-13: ( 全景图谱) — Graph3D.vue 单体拆分

#### `Plan 01-04 Task 2`  （2 处）
- `frontend/src/composables/graph3d/forceConfig.ts:4` — * 2026-08-13: ( 全景图谱) — 抽 Graph3D.vue:240-280
- `frontend/src/composables/graph3d/useGraph3DFps.ts:4` — * 2026-08-13: ( 全景图谱) — 抽 Graph3D.vue:324-331

### 编号族 `Task`

#### `Task 0`  （1 处）
- `backend/tests/unit/test_pipeline_t5_fix.py:145` — """预备：reconcile_on_sync 配置已存在（一起落地以减少提交次数）。"""

#### `Task 1`  （6 处）
- `backend/alembic/versions/024_data_source_metrics.py:20` — # 1. data_source_metrics 表
- `backend/app/core/pipeline/stages/__init__.py:12` — """Timeseries 阶段 — 已迁出。"""
- `backend/app/models/data_source_metric.py:1` — """DataSourceMetric model — tracks each source's crawl results.
- `backend/tests/unit/test_graph_write_metrics.py:103` — # max 语义（落地，回归锁定）——不允许回归为累加
- `backend/tests/unit/test_outbox_retry_worker.py:385` — # ── 幂等性: source_count max 语义（graph_writer 侧，波序前置落地）─────
- `backend/tests/unit/test_stages_common.py:74` — """timeseries 已迁出 — 不应是 _not_migrated 占位（完成标志）。"""

#### `Task 2`  （4 处）
- `backend/app/core/pipeline/stages/__init__.py:19` — """Dedup 阶段 — 已迁出。"""
- `backend/app/core/pipeline/stages/dedup.py:1` — """Pipeline dedup 阶段。
- `backend/tests/unit/test_outbox_retry_worker.py:207` — # canonical_ids_list 从 PG 重新解析并传入（前置：canonical_id 必传）
- `backend/tests/unit/test_stages_common.py:101` — """dedup 已迁出 — 完成标志。"""

#### `Task 3`  （7 处）
- `backend/app/core/pipeline/stages/__init__.py:26` — """Clean 阶段 — 已迁出。"""
- `backend/app/core/pipeline/stages/clean.py:1` — """Pipeline clean 阶段。
- `backend/tests/unit/test_pipeline_t5_fix.py:43` — # executor.py 含 execute_clean；+: stages/clean.py 含 execute_clean
- `backend/tests/unit/test_stages_common.py:112` — """clean 已迁出 — 完成标志。"""
- `evaluation/ingestion_consistency.py:238` — # 指标 1: PG approved PSR 边数（复用 /admin/reconcile-neo4j 同款 SQL)
- `frontend/src/components/Graph3D.vue:4` — * 01-03: 接入 useGraph3DLOD + useGraph3DClustering (镜像 2D
- `frontend/src/components/Graph3D.vue:7` — * 01-04: 接入 useGraph3DLifecycle + useGraph3DFps + DEFAULT_FORCE_CONFIG

#### `Task 4`  （5 处）
- `backend/alembic/versions/024_data_source_metrics.py:48` — # 2. data_sources.last_successful_crawl_at (Fix M4)
- `backend/app/core/pipeline/stages/__init__.py:33` — """Crawl 阶段 — 已迁出。"""
- `backend/app/core/pipeline/stages/crawl.py:1` — """Pipeline crawl 阶段。
- `backend/tests/unit/test_stages_common.py:123` — """crawl 已迁出 — 完成标志（签名带 run_type）。
- `backend/tests/unit/test_stages_crawl.py:48` — """stages.execute_crawl 必须是真实现（完成标志）。"""

#### `Task 5`  （4 处）
- `backend/app/core/pipeline/stages/__init__.py:40` — """Import 阶段 — 已迁出。"""
- `backend/app/core/pipeline/stages/import_.py:1` — """Pipeline import 阶段。
- `backend/tests/unit/test_stages_common.py:147` — """import 已迁出 — 完成标志。"""
- `backend/tests/unit/test_stages_import.py:38` — """stages.execute_import 必须是真实现（完成标志）。"""

#### `Task 6`  （4 处）
- `backend/app/core/pipeline/stages/__init__.py:47` — """Graph_sync 阶段 — 已迁出。"""
- `backend/app/core/pipeline/stages/graph_sync.py:1` — """Pipeline graph_sync 阶段。
- `backend/tests/unit/test_pipeline_t5_fix.py:145` — """预备：reconcile_on_sync 配置已存在（一起落地以减少提交次数）。"""
- `backend/tests/unit/test_stages_graph_sync.py:52` — """stages.execute_graph_sync 必须是真实现（完成标志）。"""

#### `Task 7`  （9 处）
- `backend/app/api/v1/pipeline/config_routes.py:1` — """Pipeline 配置子路由（拆分）。
- `backend/app/api/v1/pipeline/events_routes.py:1` — """Pipeline events 子路由（拆分起步）。
- `backend/app/api/v1/pipeline/routes.py:1` — """数据流水线监控 API — 子路由聚合入口。
- `backend/app/api/v1/pipeline/runs_routes.py:1` — """Pipeline 运行历史子路由（拆分）。
- `backend/app/api/v1/pipeline/schedule_routes.py:1` — """Pipeline 定时调度子路由（拆分）。
- `backend/app/api/v1/pipeline/status_routes.py:1` — """Pipeline 状态/概览子路由（拆分）。
- `backend/app/api/v1/pipeline/trigger_routes.py:1` — """Pipeline 操作类子路由（拆分）。
- `backend/tests/unit/test_graph_write_metrics.py:103` — # max 语义（落地，回归锁定）——不允许回归为累加
- `backend/tests/unit/test_layer_boundary.py:63` — # 纯聚合入口：routes.py 仅 include_router 子路由，无业务逻辑，

#### `Task 10`  （1 处）
- `backend/app/core/pipeline/stages/common.py:23` — """SSE 阶段进度事件结构（契约文档化将基于此扩展）。"""

#### `Task 0-2`  （1 处）
- `backend/tests/unit/test_pipeline_t5_fix.py:43` — # executor.py 含 execute_clean；+: stages/clean.py 含 execute_clean

### 编号族 `P`

#### `P0-1`  （9 处）
- `backend/app/core/pipeline/stages/graph_sync.py:29` — # ── Graph Write Outbox helpers (; 原 executor.py, 随阶段迁入) ──
- `backend/app/core/pipeline/stages/import_.py:120` — # 进度事件同时写 Redis(SSE) + DB 快照 —— 轮询/刷新也能看到实时进度
- `backend/app/core/pipeline/stages/import_.py:282` — # 同事件写 DB 快照，轮询/刷新也可见实时进度。
- `backend/app/core/pipeline/stages/import_.py:325` — # 完成事件写 DB 快照 + 报告"本次 X / 剩余 Z 待续"
- `backend/tests/unit/test_pipeline_crawl_integrity.py:1` — """爬虫多源数据完整性回归测试。"""
- `backend/tests/unit/test_pipeline_crawl_integrity.py:13` — # ── / 辅助：适配器能力与注册表 ──
- `backend/tests/unit/test_pipeline_crawl_integrity.py:38` — """核心：无 platform/source_site 的源在 _get_crawl_configs 被跳过而非回退 v2ex。"""
- `backend/tests/unit/test_stage3_outbox.py:1` — """fix: outbox regression test for run_batch_extract_jd.
- `evaluation/run_match_baseline.py:1` — """人岗匹配准确率评测 runner — 赛项实用价值指标。

#### `P0-2`  （9 处）
- `backend/app/api/v1/pipeline/trigger_routes.py:445` — # ──: Crawler completion Webhook (fix) ──
- `backend/tests/unit/test_pipeline_crawl_integrity.py:1` — """爬虫多源数据完整性回归测试。"""
- `backend/tests/unit/test_pipeline_crawl_integrity.py:92` — # ── 归零 ──
- `backend/tests/unit/test_pipeline_crawl_integrity.py:97` — """jd_raw 无行的 crawler 活动源记录数归零；有行源保持聚合值。"""
- `evaluation/run_resume_eval.py:1` — """简历提取准确率评测 runner — 赛项实用价值指标。
- `frontend/src/components/PipelineDag.vue:63` — // 2026-08-21 : 作业身份 —— 从任一 stage 取当前 run 标识（后端 /stages
- `frontend/src/components/PipelineDag.vue:326` — /* 2026-08-21 : 作业身份 + 剩余待续 */
- `frontend/src/pages/PipelineMonitor.vue:79` — // 2026-08-21 : DAG「继续处理剩余 N 条」→ 断点续跑当前 run
- `frontend/src/stores/pipelineRun.ts:46` — // 2026-08-21 : 作业身份 —— 后端 /stages 返回当前 run 标识，

#### `P0-3`  （5 处）
- `backend/alembic/env.py:20` — # fix: `from app.models import Base` triggers __init__.py which imports ALL
- `backend/app/api/v1/datasource.py:62` — """数据源是否有可用爬虫适配器 —— 后端 spider 注册表为唯一事实源。
- `backend/tests/integration/test_pipeline_single_source.py:30` — # _adapter_capability guard (added in commit 0456371b) accepts
- `backend/tests/unit/test_pipeline_crawl_integrity.py:13` — # ── / 辅助：适配器能力与注册表 ──
- `backend/tests/unit/test_pipeline_crawl_integrity.py:24` — """_adapter_capability：无 platform → 无适配器；已注册 platform → 有适配器。"""

#### `P0-4`  （2 处）
- `backend/tests/integration/test_pipeline_single_source.py:30` — # _adapter_capability guard (added in commit 0456371b) accepts
- `backend/tests/unit/test_pipeline_crawl_integrity.py:1` — """爬虫多源数据完整性回归测试。"""

#### `P1-2`  （1 处）
- `frontend/src/composables/__tests__/useSSE.test.ts:301` — // ── 10. Polling unwraps { events: [...] } envelope (fix) ──

#### `P1-3`  （1 处）
- `backend/app/core/pipeline/engine.py:162` — # fix (functional-review 2026-08-13): 完成分支此前内联

#### `P1-4`  （2 处）
- `backend/app/core/pipeline/stages/import_.py:325` — # 完成事件写 DB 快照 + 报告"本次 X / 剩余 Z 待续"
- `backend/app/core/pipeline/stages/import_.py:377` — # 报告剩余待续数，让"完成但没做完"一目了然

#### `P1-5`  （1 处）
- `backend/tests/unit/test_stage3_api.py:78` — # fix (functional-review 2026-08-13): pending_review 改从

#### `P1-6`  （1 处）
- `backend/app/api/v1/admin_graph_nodes.py:28` — # fix: 透传 element_id，前端写操作可用（服务端已改双匹配）

#### `P1-7`  （2 处）
- `backend/tests/unit/test_datasource_api.py:595` — # fix (functional-review 2026-08-13): 单源同步必须透传 selected_sources，
- `backend/tests/unit/test_pipeline_crawl_integrity.py:1` — """爬虫多源数据完整性回归测试。"""

#### `P1-9`  （1 处）
- `backend/tests/unit/test_position_visibility.py:1` — """(functional-review 2026-08-13): 岗位可见性策略 —— 非 admin 无法查看未发布岗位。

#### `P3-5`  （1 处）
- `frontend/vite.config.ts:49` — // fix: G6 v5 is ~1.4MB minified, which exceeds the default 500KB warning.

#### `P0-10`  （2 处）
- `frontend/src/api/__tests__/request.spec.ts:4` — * W1-T3 regression (path mismatch).
- `frontend/src/config/__tests__/apiBase.spec.ts:5` — * W1-T3 regression (path mismatch).

#### `P1-13`  （1 处）
- `backend/tests/unit/test_pipeline_consistency_counts.py:1` — """(functional-review 2026-08-13): pipeline_consistency 一致性计数非占位。

#### `P1-14`  （2 处）
- `backend/app/api/v1/admin.py:610` — # fix (functional-review 2026-08-13): 技能审核通过此前只改 PG 状态，
- `backend/app/api/v1/admin.py:655` — # fix (functional-review 2026-08-13): 技能驳回同步 Neo4j

### 编号族 `SEC`

#### `SEC-01`  （3 处）
- `backend/tests/unit/test_auth_security.py:1` — """Tests for (PyJWT), (bcrypt), (JWT claims)."""
- `backend/tests/unit/test_auth_security.py:34` — # ──: PyJWT encode/decode ──
- `backend/tests/unit/test_auth_security.py:38` — """Replace hand-written HMAC+base64 with PyJWT."""

#### `SEC-02`  （5 处）
- `backend/tests/unit/test_auth_security.py:1` — """Tests for (PyJWT), (bcrypt), (JWT claims)."""
- `backend/tests/unit/test_auth_security.py:80` — # ──: bcrypt password verification ──
- `backend/tests/unit/test_auth_security.py:84` — """Replace plaintext password comparison with bcrypt.checkpw."""
- `backend/tests/unit/test_auth_security.py:93` — """evolution: plaintext password fallback was REMOVED in Phase DB-AUTH.
- `backend/tests/unit/test_config.py:137` — """C3: SECRET_KEY < 32 chars in production must RuntimeError (fix)."""

#### `SEC-03`  （3 处）
- `backend/tests/unit/test_auth_security.py:1` — """Tests for (PyJWT), (bcrypt), (JWT claims)."""
- `backend/tests/unit/test_auth_security.py:116` — # ──: JWT claims (aud/iss/nbf/jti) ──
- `backend/tests/unit/test_auth_security.py:120` — """Add aud/iss/nbf/jti claims to token issuance."""

#### `SEC-04`  （9 处）
- `backend/app/api/v1/loop.py:91` — # Could be "not found" or "not authorized" — log the attempt
- `backend/app/core/pipeline/loop/status.py:44` — # IDOR guard — non-admin users only see their own runs
- `backend/app/core/pipeline/loop/status.py:109` — # IDOR guard — non-admin users only see their own runs
- `backend/tests/unit/test_config.py:154` — """C2: APP_DEBUG=true in production must RuntimeError (fix)."""
- `backend/tests/unit/test_loop_idor.py:1` — """Tests for: loop_results IDOR complete fix."""
- `backend/tests/unit/test_loop_idor.py:25` — """run_loop creates record with user_id."""
- `backend/tests/unit/test_loop_idor.py:64` — """loop_status ownership check."""
- `backend/tests/unit/test_loop_idor.py:122` — """loop_history filters by user_id."""
- `backend/tests/unit/test_loop_idor.py:180` — """Backward compatibility with default params."""

#### `SEC-05`  （9 处）
- `backend/app/models/evolution_models.py:131` — # 技术说明：nullable=True兼容首次快照，index加速关联查询，FK SET NULL
- `backend/app/models/evolution_models.py:136` — # 技术说明：nullable=True兼容最新快照，index加速关联查询，FK SET NULL
- `backend/app/models/extraction_models.py:133` — # 技术说明：nullable=True允许独立评估，index加速关联查询，FK SET NULL
- `backend/app/models/extraction_models.py:179` — # 技术说明：建立索引支持按职位快速查询所需技能，FK CASCADE
- `backend/app/models/extraction_models.py:184` — # 技术说明：建立索引支持按技能快速查询相关职位，FK CASCADE
- `backend/app/models/learning_models.py:99` — # 技术说明：建立索引支持按计划快速查询所有技能进度，FK CASCADE
- `backend/tests/unit/test_settings_guard.py:1` — """Tests for (FK constraints) and (Settings runtime guard)."""
- `backend/tests/unit/test_settings_guard.py:9` — # ──: FK constraints (ORM-level verification) ──
- `backend/tests/unit/test_settings_guard.py:13` — """Verify ForeignKey declarations exist in ORM models."""

#### `SEC-06`  （8 处）
- `backend/app/schemas/pipeline.py:207` — """Update pipeline configuration (: all fields have range constraints)."""
- `backend/tests/unit/test_settings_guard.py:1` — """Tests for (FK constraints) and (Settings runtime guard)."""
- `backend/tests/unit/test_settings_guard.py:69` — # ──: Settings safe_update guard ──
- `backend/tests/unit/test_settings_guard.py:73` — """Settings.safe_update whitelist + validation + audit."""
- `backend/tests/unit/test_settings_guard.py:149` — # ──: PipelineConfigUpdateRequest constraints ──
- `backend/tests/unit/test_settings_guard.py:153` — """PipelineConfigUpdateRequest Field constraints."""
- `backend/tests/unit/test_settings_guard.py:206` — # ──: _SCHEMA_TO_SETTINGS mapping ──
- `backend/tests/unit/test_settings_guard.py:210` — """Schema field names map correctly to Settings attribute names."""

### 编号族 `BL`

#### `BL-01`  （5 处）
- `backend/app/services/judge_service.py:233` — # both empty → skip (return 0 so it doesn't inflate avg)
- `backend/tests/unit/test_depth_analysis_fixes.py:1` — """Tests for bug fixes from depth-analysis-report."""
- `backend/tests/unit/test_depth_analysis_fixes.py:13` — # ──: Judge F1 empty-set returns 0.0 not 1.0 ──
- `backend/tests/unit/test_depth_analysis_fixes.py:17` — """Both golden and system having no skills should return F1=0, not F1=1."""
- `backend/tests/unit/test_depth_analysis_fixes.py:24` — # fix: empty vs empty should be F1=0.0, not 1.0

#### `BL-02`  （4 处）
- `backend/app/core/extraction/jd_extract.py:274` — # Complete fallback for ALL fields, not just a subset
- `backend/tests/unit/test_depth_analysis_fixes.py:1` — """Tests for bug fixes from depth-analysis-report."""
- `backend/tests/unit/test_depth_analysis_fixes.py:132` — # ──: Pydantic fallback completeness ──
- `backend/tests/unit/test_depth_analysis_fixes.py:136` — """When Pydantic validation fails, fallback should cover ALL fields."""

#### `BL-04`  （1 处）
- `backend/app/core/learning/path_engine.py:332` — # Cycle detected — use Tarjan's SCC to compress cycles

#### `BL-07`  （4 处）
- `backend/app/core/evolution/emergence_finder.py:223` — # Insufficient history — use Wilson score interval
- `backend/app/core/evolution/emergence_finder.py:226` — # when Wilson lower-bound exceeds 0.3 — that is the
- `backend/tests/unit/test_evolution_emergence_path.py:80` — """Too few data points → stable with note (: Wilson fallback)."""
- `backend/tests/unit/test_evolution_emergence_path.py:87` — # note changed from "insufficient_history" to "insufficient_history_wilson_fallback"

#### `BL-08`  （5 处）
- `backend/app/core/extraction/jd_extract.py:325` — # raise min length to 4 to prevent over-stripping
- `backend/app/core/extraction/jd_extract.py:333` — # prevents over-stripping like "分布式系统架构"→"分布式"
- `backend/tests/unit/test_depth_analysis_fixes.py:1` — """Tests for bug fixes from depth-analysis-report."""
- `backend/tests/unit/test_depth_analysis_fixes.py:58` — # ──: Chinese suffix cleaning min length ──
- `backend/tests/unit/test_depth_analysis_fixes.py:62` — """_clean_skill_name should not over-strip to < 4 chars."""

#### `BL-11`  （5 处）
- `backend/app/services/judge_service.py:309` — # Skip missing samples instead of treating as F1=0
- `backend/tests/unit/test_depth_analysis_fixes.py:1` — """Tests for bug fixes from depth-analysis-report."""
- `backend/tests/unit/test_depth_analysis_fixes.py:30` — # ──: Batch eval skips missing system samples ──
- `backend/tests/unit/test_depth_analysis_fixes.py:34` — """Missing system samples should be skipped, not counted as F1=0."""
- `backend/tests/unit/test_depth_analysis_fixes.py:53` — # g2 is skipped (not in system), so only g1 is evaluated

#### `BL-13`  （5 处）
- `backend/app/core/matching/cache.py:64` — # per-key TTL for profile cache (avoids cache avalanche)
- `backend/app/core/matching/cache.py:100` — """设置岗位技能画像缓存（: per-key TTL）。
- `backend/tests/unit/test_depth_analysis_fixes.py:1` — """Tests for bug fixes from depth-analysis-report."""
- `backend/tests/unit/test_depth_analysis_fixes.py:87` — # ──: Per-key TTL for profile cache ──
- `backend/tests/unit/test_depth_analysis_fixes.py:91` — """Profile cache should use per-key TTL, not global expiry."""

#### `BL-15`  （1 处）
- `backend/app/core/evolution/emergence_finder.py:101` — # Domain keywords loaded from YAML config for runtime updates.

#### `BL-16`  （3 处）
- `backend/tests/unit/test_depth_analysis_fixes.py:1` — """Tests for bug fixes from depth-analysis-report."""
- `backend/tests/unit/test_depth_analysis_fixes.py:119` — # ── v4 Prompt is active ──
- `backend/tests/unit/test_depth_analysis_fixes.py:123` — """jd_extraction should default to v4 (recall-optimized)."""

### 编号族 `批`

#### `批0`  （10 处）
- `backend/app/api/v1/admin.py:394` — """单岗位重抽取（审核队列批量动作）。
- `backend/app/models/extraction_models.py:351` — # 2026-08-28 (真相源): 岗位质量标记（no_skills/unclassified/non_it/NULL=ok），
- `backend/app/models/extraction_models.py:354` — # 2026-08-28 (真相源): 定时重试时间戳（幂等，每日只重试一次）
- `backend/app/services/admin_audit_service.py:93` — """查岗位 quality_hint（真相源辅助）。"""
- `backend/app/services/admin_audit_service.py:178` — # 2026-08-28 (真相源, Critic MAJOR-A): 审核动作不复活隐藏岗位。
- `backend/app/services/graph_projector.py:328` — # 2026-08-28 (真相源): 空技能岗位不投影（防剪枝→回填振荡）
- `backend/app/services/graph_sync.py:131` — # 2026-08-28 (真相源): 隐藏岗位（no_skills/non_it）不建 Position 节点，
- `backend/app/services/position_filter.py:1` — """position_filter — 岗位是否入图/展示的唯一判定（真相源, 2026-08-28）。
- `backend/app/tasks/stage3_services.py:424` — # 2026-08-28 (真相源): 隐藏岗位（no_skills/non_it）审核通过也不入图，
- `backend/tests/unit/test_review_workflow.py:492` — # position_filter (真相源: is_graph_eligible / has_approved_skill)

#### `批1`  （2 处）
- `backend/app/api/v1/admin.py:394` — """单岗位重抽取（审核队列批量动作）。
- `backend/app/api/v1/admin.py:480` — # 2026-08-28 (批量重抽取): 管理员在审核队列批量触发

#### `批2`  （7 处）
- `backend/app/api/v1/quality.py:602` — # ── 数据质量区 (可持续, 2026-08-28) ──
- `backend/app/tasks/celery_app.py:477` — # 2026-08-28 (可持续): 每日重试空技能岗位抽取（last_retry_at 幂等 + Redis 锁防并发）
- `backend/app/tasks/celery_app.py:595` — """每日重试空技能岗位抽取（可持续, 2026-08-28）。
- `backend/tests/unit/test_celery_stage3_tasks.py:52` — # retry_no_skill_positions (可持续, 2026-08-28)
- `frontend/src/pages/QualityDashboard.vue:905` — /* 岗位数据质量（2026-08-28） */
- `frontend/src/stores/quality.ts:84` — /** 岗位数据质量计数（GET /quality/data-quality，2026-08-28） */
- `frontend/src/stores/quality.ts:228` — // ── 岗位数据质量计数（2026-08-28）──

#### `批3`  （2 处）
- `backend/app/core/dashboard/dashboard_service.py:147` — # 2026-08-28 (三列口径, 共识计划 AC7): 图内+隐藏=PG全量
- `backend/app/schemas/dashboard.py:33` — # 2026-08-28 (三列口径): 图内/全量/隐藏岗位数（图内+隐藏=全量）

#### `批 0`  （1 处）
- `backend/app/core/pipeline/stages/import_.py:201` — # 200 条必然撞 hard limit 被 SIGKILL → 阶段永远卡 running、本成功。

#### `批 100`  （1 处）
- `frontend/src/pages/Admin.vue:168` — // 节点（每，直到 total），塞入 selection 供批量通过。

### 编号族 `NEW`

#### `NEW-01`  （3 处）
- `backend/app/api/v1/admin_data_truth.py:30` — # /admin/* 端点必须叠加 require_admin，
- `backend/tests/unit/test_admin_data_truth.py:1` — """admin_data_truth 端点门禁测试。
- `backend/tests/unit/test_admin_data_truth.py:74` — """普通登录用户访问 /admin/data-truth 必须 403（回归）。"""

#### `NEW-02`  （1 处）
- `backend/tests/unit/test_learning_api.py:294` — """回归：list 与 create 必须同口径取 user_id（sub=username）。

#### `NEW-03`  （1 处）
- `backend/tests/unit/test_prerequisite_map.py:1` — """ensure_prerequisite_map 单元测试。

#### `NEW-05`  （1 处）
- `backend/tests/unit/test_executor_dedup_count.py:1` — """execute_dedup 回归测试。

#### `NEW-06`  （4 处）
- `backend/alembic/versions/027_add_simhash_to_jd_raw.py:1` — """Add simhash column to jd_raw for near-duplicate detection.
- `crawler/persistence/models.py:60` — # 拆列方案——content_hash 守精确去重(UNIQUE),
- `crawler/persistence/models.py:73` — # 近似去重查询路径索引
- `crawler/pipelines/incremental.py:126` — # 拆列: content_hash 用 sha256 守精确去重(UNIQUE),

#### `NEW-07`  （1 处）
- `backend/app/core/pipeline/stages/crawl.py:210` — # 复用本模块的 build_spider_registry (注册)

#### `NEW-11`  （1 处）
- `backend/tests/unit/test_judge_schema.py:81` — """F1 质量门禁唯一常量 — settings.eval_f1_gate，全链引用."""

#### `NEW-14`  （1 处）
- `backend/tests/unit/test_models.py:130` — """全部 ORM 模型必须在 models/__init__ 注册（Alembic metadata 完整性）。"""

#### `NEW-21`  （2 处）
- `backend/tests/unit/test_learning_api.py:651` — # 先属主查询（plan.user_id=_MOCK_USER['sub']='dev'），再 progress 查询
- `backend/tests/unit/test_learning_api.py:726` — """回归：他人 plan_id 必须 403（IDOR 防护）。"""

#### `NEW-22`  （2 处）
- `crawler/tests/test_persistence.py:10` — # 本文件是 live-DB 集成测试（需 5433 真 Postgres），但 crawler/tests/conftest.py
- `crawler/tests/test_persistence.py:13` — # 测试移出 mock conftest 作用域（或 conftest 按需 mock），跟踪见计划书附录E。

#### `NEW-P0`  （2 处）
- `backend/app/config.py:136` — # dormant. Defaulting this to False means fresh dev clones
- `backend/tests/unit/test_config.py:129` — # (AUDIT_VERIFICATION §1.4 C2–C4) regression coverage.

#### `NEW-P2`  （1 处）
- `backend/app/config.py:42` — # fix : 浏览器跨域请求的 Origin 永远是人类可

#### `NEW-P1a`  （2 处）
- `backend/app/config.py:539` — # (AUDIT_VERIFICATION C5): 生产严禁自动播种弱管理员。
- `backend/tests/unit/test_config.py:192` — """C5: BOOTSTRAP_SEED_ADMIN=true in production must RuntimeError.

### 编号族 `LOOP`

#### `LOOP-02`  （4 处）
- `backend/app/dependencies.py:314` — """SSE-friendly auth: accept token via query param OR Authorization header.
- `frontend/src/composables/useSSE.ts:134` — // Append JWT token as query parameter for SSE auth
- `frontend/src/composables/useSSE.ts:249` — // Add Authorization header for polling fetch auth
- `frontend/src/stores/jobseeker.ts:120` — // Add Authorization header + fix hardcoded URL

#### `LOOP-03`  （1 处）
- `frontend/src/stores/learningPlan.ts:164` — /** 从匹配结果构造 CreatePlanRequest 请求体

#### `LOOP-04`  （1 处）
- `frontend/src/pages/MatchDiagnosis.vue:316` — // 创建学习计划并跳转学习中心

#### `LOOP-05`  （4 处）
- `backend/app/api/v1/extract.py:176` — """Write extraction result to PostgreSQL PositionRecord + SkillRecord.
- `backend/app/api/v1/extract.py:240` — # Write extraction to PostgreSQL (non-blocking: failure won't break the response)
- `backend/app/api/v1/extract.py:291` — # Write extraction to PostgreSQL
- `backend/app/repositories/extract_repo.py:91` — """Write extraction result to PostgreSQL PositionRecord + SkillRecord.

#### `LOOP-06`  （3 处）
- `frontend/src/stores/evolution.ts:78` — // Emerging alert type for evolution alerts
- `frontend/src/stores/evolution.ts:125` — // Emerging alerts state
- `frontend/src/stores/evolution.ts:226` — // Fetch emerging skill alerts

#### `LOOP-07`  （5 处）
- `backend/app/api/v1/admin.py:262` — """Approve a review queue item and sync to Neo4j."""
- `backend/app/api/v1/admin.py:278` — """Reject a review queue item and sync to Neo4j."""
- `backend/app/services/admin_audit_service.py:91` — # Neo4j sync on approve/reject
- `backend/app/services/admin_audit_service.py:431` — """Approve a review-queue item and sync to skill/position tables + Neo4j.
- `backend/app/services/admin_audit_service.py:491` — """Reject a review-queue item and sync to Neo4j."""

#### `LOOP-08`  （1 处）
- `frontend/src/composables/usePipelineMonitor.ts:420` — // User role (: admin check for Pipeline management controls)

#### `LOOP-09`  （2 处）
- `backend/app/core/pipeline/loop_orchestrator.py:139` — # match diagnosis (: skip if no effective target_position)
- `backend/app/core/pipeline/loop_orchestrator.py:155` — # learning path (: skip if no target or match skipped)

#### `LOOP-12`  （1 处）
- `backend/app/api/v1/evolution.py:103` — """获取指定技能或岗位的演化变更记录。

### 编号族 `BUG`

#### `BUG-2`  （1 处）
- `backend/tests/unit/test_review_workflow.py:385` — # fix: EvolutionChangelog low-trust pending count (§5.2)

#### `BUG-5`  （1 处）
- `frontend/src/components/EvolutionReviewPanel.vue:3` — * EvolutionReviewPanel — + E21 + E22 fix.

#### `BUG-6`  （1 处）
- `backend/app/core/evolution/trust_scorer.py:53` — # fix: single threshold for "low trust → needs human review".

#### `BUG-8`  （2 处）
- `backend/tests/unit/test_admin_graph_service.py:189` — # fix: `id` is the stamped canonical_id (UUID) — the Neo4j
- `backend/tests/unit/test_admin_graph_service.py:405` — # fix: create_node stamps a fresh canonical_id UUID

#### `BUG-9`  （1 处）
- `backend/tests/unit/test_admin_graph_service.py:403` — # fix: create_node stamps default review_status=pending

#### `BUG-14`  （1 处）
- `backend/app/api/v1/admin_prompts.py:52` — """fix: compute `serving_version` and `serving_source`.

#### `BUG-15`  （1 处）
- `backend/app/api/v1/admin_data_truth.py:130` — # fix: actually invoke the dashboard aggregation service instead of

#### `BUG-16`  （3 处）
- `backend/app/core/pipeline/cron_scheduler.py:170` — # fix: name-based dispatch
- `backend/app/core/pipeline/cron_scheduler.py:203` — """fix: extract reconcile logic so both cron and the manual endpoint
- `backend/app/tasks/celery_app.py:215` — """fix: Celery task for daily PG↔Neo4j reconcile.

#### `BUG-18`  （1 处）
- `backend/app/api/v1/admin.py:190` — # fix: tag reconcile events with their scope so

#### `BUG-003`  （1 处）
- `frontend/src/stores/user.ts:138` — // clear cached per-user data in every store so

#### `BUG-004`  （1 处）
- `frontend/src/pages/ExtractJD.vue:86` — // clear any prior progress interval before

#### `BUG-005`  （1 处）
- `frontend/src/components/AdminOverview.vue:27` — // surface load failures so the user can retry

#### `BUG-006`  （2 处）
- `frontend/src/pages/MatchDiagnosis.vue:249` — // 优化: 请求失败(result 为 null)才拦截;岗位无画像(空结果但带
- `frontend/src/pages/__tests__/MatchDiagnosis.spec.ts:249` — // 2026-08-23 优化: 请求成功(非 null)即使结果为空也跳 step 3,

#### `BUG-007`  （1 处）
- `frontend/src/components/GraphSearchBar.vue:15` — // capture the blur-hide timer so we can cancel

### 编号族 `PIPE`

#### `PIPE-02`  （2 处）
- `backend/tests/unit/test_proxy_breaker.py:1` — """验收：熔断行为契约。"""
- `crawler/middleware/proxy_middleware.py:1` — """PROXY_LIST 代理池 + 失败熔断中间件 )

#### `PIPE-03`  （5 处）
- `backend/app/core/pipeline/bootstrap.py:1` — """(c): celery-worker 启动一次性 bootstrap。
- `backend/tests/unit/test_pipeline_bootstrap.py:1` — """(c): bootstrap 行为契约测试。"""
- `crawler/pipeline_bridge.py:1` — """(b): CLI 触发 pipeline 的薄包装。
- `crawler/run.py:86` — """(b): CLI 子命令触发一次完整 pipeline run."""
- `crawler/run.py:130` — # (b): CLI 触发完整 pipeline run

#### `PIPE-04`  （1 处）
- `tests/e2e/conftest_e2e.py:1` — """E2E 测试 fixtures。

#### `PIPE-P0`  （1 处）
- `scripts/verify_pipe_p0.py:1` — """verify_pipe_p0.py — 修复验证脚本

#### `PIPE-P0-1`  （1 处）
- `scripts/verify_pipe_p0.py:33` — """Celery event loop 错(stage 完成 + DAG 推进必须在同一 async 上下文)。"""

#### `PIPE-P0-2`  （2 处）
- `scripts/verify_pipe_p0.py:85` — """jd_raw 表已通过 Alembic 迁移定义。"""
- `scripts/verify_pipe_p0.py:133` — """辅助验证: crawler/persistence/database.py 应连 starmap PostgreSQL(非 SQLite)。"""

#### `PIPE-P0-3`  （1 处）
- `scripts/verify_pipe_p0.py:113` — """graph_sync 阶段在 orchestrator 中已定义。"""

### 编号族 `C`

#### `C-3`  （4 处）
- `frontend/src/components/Graph3D.vue:210` — // 01-04: 抽 lifecycle / FPS / force config 到 composables (单文件拆分)
- `frontend/src/components/GraphFilterPanel.vue:5` — * Sprint: 集中 domain/tech_stack/level radio、layout toggle、
- `frontend/src/composables/graph3d/index.ts:6` — * - 01-04: useGraph3DLifecycle + useGraph3DFps + forceConfig (单文件拆分)
- `frontend/src/composables/graph3d/useGraph3DLifecycle.ts:4` — * 2026-08-13: ( 全景图谱) — Graph3D.vue 单体拆分

#### `C-4`  （1 处）
- `backend/tests/unit/test_prompt_version_persistence.py:1` — """持久化/启动合并单测 ——: PromptVersion 表 + apply_custom_prompt_versions。

#### `C-5`  （8 处）
- `backend/app/tasks/stage3_services.py:715` — # 入口闭环: POST /evolution/analyze 与 6h beat 共用本入口 (celery_app.py:63-73).
- `backend/tests/unit/test_datasource_crud_smoke.py:1` — """P1.3 smoke: datasource CRUD 路由契约锁定（覆盖缺口）。
- `backend/tests/unit/test_graph_overview_heuristics.py:1` — """+ (M1) closure: graph_overview / dashboard 启发式补测（债务消除）。
- `backend/tests/unit/test_graph_overview_heuristics.py:1` — """+ (M1) closure: graph_overview / dashboard 启发式补测（债务消除）。
- `backend/tests/unit/test_graph_overview_heuristics.py:193` — #   合计 13 ≥ 5 启发式用例（债务消除）✅
- `backend/tests/unit/test_graph_overview_heuristics.py:199` — # 14 大行业桶；债务消除 — 此前 0 测试覆盖。
- `backend/tests/unit/test_graph_services.py:720` — # ── graph_overview: fetch_overview_by_heat (M1 closure) ─
- `backend/tests/unit/test_graph_services.py:820` — # ── graph_service: fetch_overview_by_domain (M1 closure) ─

### 编号族 `UX`

#### `UX-02`  （8 处）
- `frontend/src/components/Graph3D.vue:174` — // 节点降噪 LOD + cluster 折叠 — 镜像 2D useGraphLOD + useGraphClustering
- `frontend/src/components/Graph3D.vue:189` — // maxNodes 优先 (background mode);否则 cluster 折叠
- `frontend/src/components/Graph3D.vue:475` — // start autoRotate if prop is set (e.g. Login background)
- `frontend/src/pages/Login.vue:3` — * 登录页面 — Phase DB-AUTH 双 token 登录 + 3D 背景
- `frontend/src/pages/Login.vue:8` — * - : Graph3D auto-rotate 背景 (opacity=0.25, maxNodes=150)
- `frontend/src/pages/Login.vue:31` — // 3D background data — use useGraph3DData for proper color/label mapping
- `frontend/src/pages/Login.vue:84` — // transition animation — opacity 0.25→1.0 (300ms)
- `frontend/src/pages/Login.vue:195` — /*3D background layer */

#### `UX-03`  （3 处）
- `frontend/src/components/Graph3D.vue:345` — // Set initial z-coordinates for Skill nodes by proficiency tier
- `frontend/src/components/Graph3D.vue:439` — // Set initial z for new Skill nodes (those without inherited positions)
- `frontend/src/composables/useNodeThreeObject.ts:32` — // ──: Proficiency → z-axis layer mapping ──

#### `UX-04`  （2 处）
- `frontend/src/stores/__tests__/evolution.test.ts:160` — // fetchChangelog identifier parameter tests
- `frontend/src/stores/evolution.ts:204` — // Renamed parameter — backend 'identifier' accepts both position and skill names

### 编号族 `IC`

#### `IC-01`  （1 处）
- `evaluation/run_baseline.py:249` — # 第二道门禁 — ingestion gate（入库完整性，..07 回归守护）。

#### `IC-05`  （3 处）
- `backend/app/api/v1/admin.py:143` — # PG 侧只统计 approved 岗位的 PSR（Neo4j 只投影 approved）
- `backend/tests/unit/test_admin_endpoints.py:856` — """ReconcileResult 含 REQUIRES 边对账字段（可观测）。"""
- `backend/tests/unit/test_reconcile_requires_edges.py:1` — """— /admin/reconcile-neo4j REQUIRES 边对账  + skills_synced bug.

#### `IC-06`  （2 处）
- `backend/tests/unit/test_graph_write_metrics.py:1` — """— source_count max 语义探针与回归测试.
- `backend/tests/unit/test_outbox_retry_worker.py:386` — # 断言 merge_skill 查询含 max 语义，重复 merge 不累加（不膨胀）。

#### `IC-07`  （5 处）
- `backend/scripts/kpi_audit.py:37` — """对 status_aggregator 聚合输出做运行时口径断言（防跨页漂移）。
- `backend/scripts/kpi_audit.py:154` — # 三段 KPI 唯一事实源 status_aggregator.py
- `backend/tests/unit/test_eval_ingestion_metrics.py:161` — """KPI 口径运行时断言失败 → 门禁同样 FAIL（并入 ingestion gate）。"""
- `evaluation/ingestion_consistency.py:230` — # 1) KPI 口径运行时断言（唯一事实源 status_aggregator.py)
- `frontend/src/composables/__tests__/usePipelineMonitor.kpi.spec.ts:2` — * usePipelineMonitor KPI 三段口径测试(防跨页漂移）。

### 编号族 `DC`

#### `DC-01`  （3 处）
- `backend/alembic/versions/039_seed_daily_reconcile_schedule.py:1` — """Seed daily_reconcile schedule row.
- `backend/tests/integration/test_daily_reconcile_full.py:1` — """— 每日对账 cron 集成测试。
- `backend/tests/unit/test_cron_scheduler.py:181` — """daily_reconcile name 分发到 reconcile_graph_task.delay。

#### `DC-02`  （1 处）
- `backend/tests/unit/test_outbox_retry_worker.py:1` — """Outbox retry worker tests.

#### `DC-03`  （2 处）
- `backend/tests/integration/test_daily_reconcile_full.py:1` — """— 每日对账 cron 集成测试。
- `backend/tests/integration/test_daily_reconcile_full.py:110` — # audit detail 含节点 + 边 diff

#### `DC-04`  （3 处）
- `backend/tests/unit/test_datasource_api.py:359` — """PATCH status='inactive' 被接受（替代 DELETE 独占软删）。"""
- `backend/tests/unit/test_datasource_api.py:642` — """新源不能直接建为停用 → Literal 拒绝 (422)。"""
- `backend/tests/unit/test_datasource_api.py:664` — """共享 DataSourceStatus 覆盖 'inactive' 且被 schema 引用。"""

#### `DC-05`  （1 处）
- `backend/tests/unit/test_graph_requires_spec.py:1` — """— REQUIRES 边属性契约收敛tests.

### 编号族 `FLOW`

#### `FLOW-03`  （6 处）
- `frontend/src/pages/LearningCenter.vue:120` — // extract skill names from structured parsedSkills
- `frontend/src/pages/MatchDiagnosis.vue:130` — // store structured skills with default proficiency
- `frontend/src/pages/MatchDiagnosis.vue:175` — // parsedSkills is now ParsedSkill[] with real proficiency
- `frontend/src/pages/MatchDiagnosis.vue:214` — // extract skill names from structured parsedSkills
- `frontend/src/stores/learningPlan.ts:261` — // 同步已掌握技能到用户技能列表，重新匹配可反映进步
- `frontend/src/stores/user.ts:157` — // ── Resume-related state —: structured skills with proficiency ──

#### `FLOW-02-S2`  （2 处）
- `frontend/src/pages/LearningCenter.vue:113` — // 一键重新匹配 —— 使用更新后的 parsedSkills 对当前岗位重新执行匹配
- `frontend/src/pages/MatchDiagnosis.vue:80` — // 重新匹配跳转 —— 从 LearningCenter 携带 rematch 查询参数

#### `FLOW-02-S3`  （2 处）
- `frontend/src/components/GapAnalysisReport.vue:27` — // 分数差值卡片 —— 对比当前匹配分数与历史最近一次同岗位匹配分数
- `frontend/src/components/GapAnalysisReport.vue:419` — /*分数差值卡片 */

### 编号族 `API`

#### `API-03`  （2 处）
- `backend/tests/unit/test_loop_api.py:59` — # empty target_position is coerced to None (optional), not rejected
- `backend/tests/unit/test_loop_service.py:267` — # empty target_position is coerced to None (optional), not rejected

#### `API-05`  （2 处）
- `backend/app/api/v1/dashboard.py:118` — # 在连接断开时释放 SSE 连接计数
- `backend/tests/unit/test_dependencies.py:207` — """SSE per-IP and global connection limits.

#### `API-06`  （4 处）
- `backend/app/api/v1/extract.py:264` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）
- `backend/app/api/v1/pipeline/trigger_routes.py:357` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）
- `backend/app/api/v1/pipeline/trigger_routes.py:404` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）
- `backend/app/api/v1/resume.py:28` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）

### 编号族 `DATA`

#### `DATA-01`  （1 处）
- `backend/tests/unit/test_depth_analysis_fixes.py:139` — """P0: Chinese name patterns should be redacted."""

#### `DATA-02`  （3 处）
- `backend/tests/unit/test_config.py:244` — # W1-T7 regression (03): prod must enforce transport encryption
- `backend/tests/unit/test_config.py:297` — """prod rejects Neo4j URIs without TLS scheme."""
- `backend/tests/unit/test_config.py:321` — """prod accepts any bolt+s / neo4j+s / bolt+ssc scheme."""

#### `DATA-03`  （2 处）
- `backend/tests/unit/test_config.py:252` — """prod rejects Postgres sslmode < require (allow/prefer/disable)."""
- `backend/tests/unit/test_config.py:273` — """prod accepts require/verify-ca/verify-full."""

#### `DATA-04`  （1 处）
- `backend/tests/unit/test_config.py:170` — """C4: REDIS_URI without `:password@` in production must RuntimeError (fix).

#### `DATA-05`  （1 处）
- `backend/app/services/auth_service.py:929` — # fix: 软删除时同时匿名化 PII（邮箱、登录 IP）

### 编号族 `SSE`

#### `SSE-04`  （4 处）
- `frontend/src/stores/pipelineRun.ts:164` — // 3 个新事件类型 state
- `frontend/src/stores/pipelineRun.ts:360` — // 3 个新事件 handler
- `frontend/src/stores/pipelineRun.ts:452` — // /05 新增 state
- `frontend/src/stores/pipelineRun.ts:466` — // /05 新增 actions

#### `SSE-05`  （3 处）
- `frontend/src/composables/usePipelineMonitor.ts:106` — // Use API_BASE from apiBase.ts SSoT
- `frontend/src/stores/pipelineRun.ts:164` — // 3 个新事件类型 state
- `frontend/src/stores/pipelineRun.ts:360` — // 3 个新事件 handler

### 编号族 `DEV`

#### `DEV-01`  （3 处）
- `backend/app/api/v1/evolution.py:565` — """§7.6 因果推理轻量版: 技能-岗位关联显著性 (Fisher 精确检验)。"""
- `backend/app/core/evolution/causal_inference.py:1` — """§7.6 因果推理轻量版 — 技能-岗位关联统计显著性 (P0)。
- `backend/tests/unit/test_causal_inference.py:1` — """§7.6 因果推理轻量版测试。

#### `DEV-14`  （3 处）
- `backend/alembic/versions/028_add_source_trust_config.py:1` — """Add source_trust_config table (§4.2).
- `backend/app/models/pipeline_models.py:338` — """数据源信任度配置 (§4.2)。
- `backend/app/services/trust_config_service.py:1` — """source_trust_config 幂等播种。

### 编号族 `PERF`

#### `PERF-01`  （1 处）
- `backend/app/api/v1/quality.py:327` — # 2026-08-29 : quality dashboard 无缓存 —— 每次请求 27 次串行 DB 往返

#### `PERF-02`  （2 处）
- `backend/app/services/graph_service.py:66` — # 2026-08-29 : 原实现 MATCH 全量拉取所有 Position 到 Python 做
- `backend/tests/unit/test_graph_service_coverage.py:125` — # 2026-08-31 : _resolve_position_name 从全图扫描改为

#### `PERF-03`  （1 处）
- `backend/app/api/v1/graph.py:123` — # 2026-08-29 : overview 每次请求全量重查 Neo4j(实测 domain 2.7s)。

#### `PERF-04`  （1 处）
- `backend/alembic/versions/042_add_perf_indexes.py:1` — """Add performance indexes for COUNT/filter hot columns (2026-08-29).

#### `PERF-06`  （1 处）
- `backend/app/services/redis_cache.py:1` — """Redis 缓存助手 (2026-08-31).

### 编号族 `INJ`

#### `INJ-03`  （1 处）
- `backend/app/services/auth_service.py:38` — # fix: 转义 SQL LIKE 通配符，防止通配符注入

#### `INJ-04`  （1 处）
- `backend/app/services/graph_service.py:149` — # depth is int, clamped to [1,5] by API validator + max/min guard.

#### `INJ-05`  （4 处）
- `backend/app/api/v1/extract.py:264` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）
- `backend/app/api/v1/pipeline/trigger_routes.py:357` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）
- `backend/app/api/v1/pipeline/trigger_routes.py:404` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）
- `backend/app/api/v1/resume.py:28` — # 统一校验（扩展名 + MIME + 大小 + 魔术字节）

### 编号族 `AP`

#### `AP-07`  （5 处）
- `backend/app/core/dashboard/sse_broadcaster.py:52` — # Active SSE connection counter (process-local)
- `backend/app/core/dashboard/sse_broadcaster.py:149` — # Enforce connection limit
- `backend/tests/unit/test_ap07_fe02.py:1` — """Tests for (SSE client limit) and (A/B test results)."""
- `backend/tests/unit/test_ap07_fe02.py:12` — # ──: SSE connection limit ──
- `backend/tests/unit/test_ap07_fe02.py:16` — """SSE event_stream should enforce MAX_SSE_CLIENTS limit."""

#### `AP-10`  （1 处）
- `backend/app/core/llm/cost_tracker.py:93` — # prod env serializes to JSON; dev env prints pretty.

### 编号族 `AUTH`

#### `AUTH-04`  （6 处）
- `backend/tests/unit/test_config.py:233` — # 生产 CORS 必须覆盖默认值
- `backend/tests/unit/test_config.py:264` — # 提供 CORS 避免提前被 CORS 断言拦截
- `backend/tests/unit/test_config.py:284` — # 生产 CORS 必须覆盖默认值
- `backend/tests/unit/test_config.py:309` — # 提供 CORS 避免提前被 CORS 断言拦截
- `backend/tests/unit/test_config.py:332` — # 生产 CORS 必须覆盖默认值
- `backend/tests/unit/test_cors_config.py:83` — # This is the test the audit originally implied (CORS smell):

### 编号族 `ALIGN`

#### `ALIGN-08`  （5 处）
- `backend/tests/unit/test_eval_bootstrap_ci.py:1` — """§14.5 落地：bootstrap 95% CI（§14.5）正确性 + 守卫。
- `evaluation/judge_eval.py:72` — # 95% bootstrap CI（n=1000 重采样，纯 stdlib，无依赖）。：§14.5 置信区间报告落地。
- `evaluation/judge_eval.py:279` — # §14.5 bootstrap 95% CI（per-sample 重采样，1000 次）
- `evaluation/judge_eval.py:313` — # §14.5 置信区间报告（bootstrap 1000 次 95% CI）
- `evaluation/run_real_eval.py:365` — # §14.5 置信区间（bootstrap 1000 次 95% CI）

#### `ALIGN-09`  （1 处）
- `backend/tests/unit/test_resume_format_abnormal.py:1` — """§10.1 落地：简历格式异常样本测试（加密/损坏/超长/扩展名/MIME/空）。

### 编号族 `TC`

#### `TC-1`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:53` — // 渲染 (smoke)

#### `TC-2`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:59` — // 触发按钮可见

#### `TC-3`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:65` — // 空态文案（无数据时）由 DAG 区渲染

#### `TC-4`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:72` — // Cron 校验工具契约

#### `TC-5`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:106` — // 失败阶段处理

#### `TC-6`  （1 处）
- `frontend/src/pages/__tests__/PipelineMonitor.spec.ts:112` — // SSE 断连时 UI 降级

### 编号族 `FE`

#### `FE-01`  （1 处）
- `backend/tests/unit/test_depth_analysis_fixes.py:119` — # ── v4 Prompt is active ──

#### `FE-02`  （3 处）
- `backend/tests/unit/test_ap07_fe02.py:1` — """Tests for (SSE client limit) and (A/B test results)."""
- `backend/tests/unit/test_ap07_fe02.py:53` — # ──: A/B test results endpoint ──
- `backend/tests/unit/test_ap07_fe02.py:57` — """A/B test result recording and aggregation."""

#### `FE-04`  （1 处）
- `backend/app/api/v1/match.py:196` — """Reverse match — given user skills, recommend suitable positions.

### 编号族 `DF`

#### `DF-01`  （1 处）
- `backend/tests/unit/test_outbox_retry_worker.py:1` — """Outbox retry worker tests.

#### `DF-03`  （1 处）
- `backend/tests/unit/test_eval_ingestion_metrics.py:1` — """— ingestion_consistency 6 项入库完整性指标单测。

#### `DF-04`  （2 处）
- `backend/tests/unit/test_evolution_write_back.py:108` — """approved 行 trust<0.6 直接放行写回 PSR。"""
- `backend/tests/unit/test_trust_scorer.py:88` — """单源 cold-start trust 数值固化（文档锚点）。

#### `DF-05`  （1 处）
- `backend/tests/unit/test_entity_trust.py:108` — """ 回归锁定：EntityTrustScorer 不参与写回闸门。

### 编号族 `IS`

#### `IS-01`  （1 处）
- `backend/tests/unit/test_graph_write_metrics.py:1` — """— source_count max 语义探针与回归测试.

#### `IS-03`  （2 处）
- `backend/alembic/versions/039_seed_daily_reconcile_schedule.py:1` — """Seed daily_reconcile schedule row.
- `backend/tests/integration/test_daily_reconcile_full.py:1` — """— 每日对账 cron 集成测试。

#### `IS-04`  （1 处）
- `backend/tests/unit/test_eval_ingestion_metrics.py:1` — """— ingestion_consistency 6 项入库完整性指标单测。

### 编号族 `CRON`

#### `CRON-01`  （1 处）
- `backend/app/core/pipeline/cron_scheduler.py:1` — """Cron scheduler module.

#### `CRON-02`  （1 处）
- `backend/app/api/v1/pipeline/schedule_routes.py:38` — """创建定时调度（: 创建时计算 next_run_at）。"""

#### `CRON-04`  （1 处）
- `backend/app/tasks/celery_app.py:300` — """读取 schedule 并触发 pipeline。

#### `CRON-05`  （1 处）
- `backend/app/core/pipeline/cron_scheduler.py:1` — """Cron scheduler module.

### 编号族 `DEF`

#### `DEF-001`  （2 处）
- `backend/tests/unit/test_resume_service.py:350` — # ──: Redis 内容哈希缓存 ──
- `frontend/src/stores/resume.ts:41` — // 否则前端 60s 提前掐断导致 PDF 简历解析必然失败。

#### `DEF-002`  （2 处）
- `frontend/src/stores/__tests__/learningCombined.test.ts:4` — * regression guard: the combined store previously returned a plain
- `frontend/src/stores/learning.ts:26` — * fix: 此前直接 `batchResults: rec.batchResults` 会把 Pinia ref 解包成

### 编号族 `MAJOR`

#### `MAJOR-3`  （2 处）
- `backend/app/api/v1/admin.py:394` — """单岗位重抽取（审核队列批量动作）。
- `backend/app/api/v1/admin.py:480` — # 2026-08-28 (批量重抽取): 管理员在审核队列批量触发

### 编号族 `SOURCE`

#### `SOURCE-02`  （1 处）
- `backend/app/core/pipeline/stages/dedup.py:197` — # execute_dedup 后更新 duplicate_rate (UAT 修复)

#### `SOURCE-03`  （1 处）
- `backend/app/core/pipeline/stages/import_.py:356` — # execute_import 后更新 valid_records (UAT 修复)

### 编号族 `AUTHZ`

#### `AUTHZ-01`  （1 处）
- `backend/app/dependencies.py:218` — """要求 admin 角色 (修复)。

#### `AUTHZ-05`  （1 处）
- `backend/tests/unit/test_pipeline_api.py:215` — # fix: dev-token 返回 admin 需要 dev_anon_admin=True

### 编号族 `T`

#### `T-08-05`  （1 处）
- `backend/app/main.py:636` — # llm_keys: 仅返回布尔，永不返回 key 值（信息泄露防护）

#### `T-10-11`  （1 处）
- `frontend/src/components/EvolutionChangelogDrawer.vue:47` — // not user-controllable.

### 编号族 `CFG`

#### `CFG-02`  （2 处）
- `backend/tests/unit/test_config.py:90` — """开发环境 DB 密码为占位值时输出 WARNING（含字段名）。"""
- `backend/tests/unit/test_config.py:111` — """生产环境 DB 密码为占位值时 raise RuntimeError。"""

### 编号族 `M`

#### `M13`  （1 处）
- `backend/tests/unit/test_run_match.py:533` — """Empty required list returns cii=0.0 (fix: no explicit requirements → no quantifiable inflation)."""

#### `M1b`  （1 处）
- `backend/tests/unit/test_stage3_outbox.py:74` — # 门控: 默认 approved（保持既有 outbox 测试语义），

### 编号族 `CR`

#### `CR-06`  （2 处）
- `crawler/spiders/v2ex_remote.py:28` — # 走 compliance.fetch（robots 检查 + QPS≤1 + compliance_log），
- `crawler/tests/test_spider_compliance_wiring.py:1` — """/ 回归：本地 spider 必须经由 crawler.compliance.fetch。

### 编号族 `US`

#### `US-3`  （2 处）
- `frontend/src/pages/PositionList.vue:52` — // 行业列表从后端 /positions/industries 获取全量，而非仅当前页
- `frontend/src/stores/jd.ts:141` — /** Fetch all distinct industries from backend (: 完整行业列表) */

### 编号族 `CANCEL`

#### `CANCEL-02`  （2 处）
- `frontend/src/stores/pipelineRun.ts:387` — // cancelRun action
- `frontend/src/stores/pipelineRun.ts:470` — //

### 编号族 `AC`

#### `AC-1`  （1 处）
- `scripts/measure_pipeline_performance.py:1` — """Pipeline 性能测试脚本。

#### `AC-6`  （1 处）
- `scripts/measure_pipeline_accuracy.py:1` — """Pipeline 推荐准确率测量脚本。

### 编号族 `ADMIN`

#### `ADMIN-02`  （1 处）
- `backend/app/api/v1/admin.py:292` — """Update name and/or trust of a review queue item (save loop)."""

### 编号族 `EV`

#### `EV-02`  （1 处）
- `backend/app/api/v1/evolution.py:368` — # respect the status parameter

### 编号族 `POLL`

#### `POLL-01`  （1 处）
- `backend/app/api/v1/pipeline/events_routes.py:56` — """SSE polling fallback — 返回最近事件数组。

### 编号族 `F`

#### `F-01`  （1 处）
- `backend/app/core/extraction/industry_gate.py:1` — """industry_gate — 岗位行业分类门禁。

### 编号族 `RECALL`

#### `RECALL-01`  （1 处）
- `backend/app/core/extraction/prompt.py:364` — # 2026-08-25 : resume v2 — 对齐 JD v4 的完整性要求。

### 编号族 `data`

#### `data-001`  （1 处）
- `backend/app/core/extraction/prompt.py:365` — # 评估实测 recall 0.60-0.78 (resume-/ resume-test-001), LLM 漏掉

### 编号族 `SYNC`

#### `SYNC-02`  （1 处）
- `backend/app/core/pipeline/loop/steps/graph_update.py:69` — # Pass extraction_data for DB-query + graph_writer mode

### 编号族 `MINOR`

#### `MINOR-4`  （1 处）
- `backend/app/schemas/dashboard.py:33` — # 2026-08-28 (三列口径): 图内/全量/隐藏岗位数（图内+隐藏=全量）

### 编号族 `LOG`

#### `LOG-05`  （1 处）
- `backend/app/utils/audit.py:1` — """安全审计日志 (修复)。

### 编号族 `ALIGNE`

#### `ALIGNE-09`  （1 处）
- `backend/tests/unit/test_resume_format_abnormal.py:153` — # 缺口"加密/损坏简历"覆盖说明：
