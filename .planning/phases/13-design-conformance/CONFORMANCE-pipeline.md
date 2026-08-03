# CONFORMANCE — Module 3: 数据流水线 (PipelineMonitor)

**Phase 13 · Wave 1 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/07-业务核心-pipeline.md`（降级原则、状态可观测）、`docs/architecture/pipeline.md`、M3/M5 强制规范 |
| was-analyzed | `docs/archive/pipeline-source-analysis.md` |
| is (live) | `frontend/src/pages/PipelineMonitor.vue` + `composables/usePipelineMonitor.ts` + `stores/pipelineRun.ts` + `/api/v1/pipeline/{status,stages,runs,events}` + `SSE /events` + PG `pipeline_runs` |

## 已修复 + 验证
- **[FIXED · M3 · HIGH]** `GET /api/v1/pipeline/stages` 旧逻辑 `ORDER BY started_at DESC LIMIT 1`：当最近 run 是 cancelled-zombie（如 `532d1754`，0 记录）时，API 返回其过期 in-flight 快照（`crawl|running, dedup|pending, …`），用户看到“正在运行”假象。**修复** `backend/app/api/v1/pipeline/routes.py::get_pipeline_stages`：改用优先级 `running > completed(records>0) > failed > cancelled(records>0) > latest cancelled（兜底）`，跳过纯 zombie。
  - **验证**（修复前→后）：返回 6 阶段（zombie 快照，crawl=running）→ **3 阶段**（`f6f1a055` completed，crawl=completed recs=46，dedup_clean=completed，import_sync=completed），无过期“running”。PipelineMonitor 的 DAG/KPI 渲染将自动反映真实完成态。
- **[CONFORM]** `last_crawl_at` 字段已就位（上一轮 M3 修复），KPI 卡片显示 “今日 0 / 历史累计 46 · 最近 07-24 09:32”，符合 M5 空态文案原则。
- **[CONFORM]** SSE `/pipeline/events` 允许自动重连（`useSSE` 指数退避 + 静默 token 刷新），与架构降级原则一致。
- **[CONFORM]** `usePipelineMonitor.ts` 的 `timelineStages` 已有 `consumed` 集合防重复消费（dedup_clean/import_sync → 标准 5 阶段名），DAG 正确显示 5 节点。

## 偏移 / 待办

### P0 — 设计书 vs 代码阶段数三端不统一

| 来源 | 阶段数 | 阶段名 |
|---|---|---|
| 设计书 mermaid (`docs/architecture/pipeline.md`) | **3** | `crawl → dedup_clean → import_sync` |
| 后端 `StageName` 枚举 | **6** | `crawl, dedup, clean, import, graph_sync, timeseries` |
| 后端 `STAGE_EXECUTORS` | **6** | 同上 |
| 后端模型 docstring | **5** | `crawl → dedup → clean → import → graph_sync` |
| 前端 `ALL_STAGE_NAMES` | **5** | `crawl, dedup, clean, import, graph_sync` |

设计书声明”调度事实以 `STAGE_EXECUTORS` 与 `StageName` 为准”，但设计书自身 mermaid 画 3 阶段，与代码 5-6 阶段矛盾。**修复**：更新设计书 mermaid + 阶段表匹配代码 5 阶段（代码是事实源，不改代码）。

### P1 — `dedup` 与 `clean` 并行执行违反设计书串行顺序

设计书 mermaid: `crawl → dedup_clean → import_sync`（串行）。
代码 `STAGE_DEPS`: `dedup: [crawl], clean: [crawl]`（**并行**）。
**影响**：`clean` 在 `dedup` 完成前处理 `raw` 记录，会清洗最终被标 `duplicate` 的记录——浪费计算。不影响数据正确性但浪费资源。
**修复**：`STAGE_DEPS` 中 `clean: [dedup]`（串行）。

### P1 — `JdStatus` 缺少 `cleaned` 状态

当前枚举：`raw, extracted, duplicate, failed`。`clean` 阶段处理后记录仍为 `raw`，无法区分”已清洗未提取”与”未清洗”。`clean` 部分失败时 `import` 处理未清洗记录。
**修复**：增加 `JdStatus.cleaned = “cleaned”` + Alembic 迁移；`import` 改读 `status=cleaned`。

### P1 — `import` 阶段标签不含 LLM 抽取

前端 `STAGE_LABELS.import = '数据入库'`，但 `execute_import` 执行 LLM 技能抽取 + PG 持久化。设计书 `import_sync` 描述为”LLM 抽取并持久化 PG，再同步图投影”。
**修复**：标签改为 `'LLM抽取+入库'`。

### P2 — `timeseries` 阶段前端静默丢弃

后端含 `TIMESERIES`（`OPTIONAL_STAGES`），但前端 `ALL_STAGE_NAMES` / `STAGE_LABELS` 不含。若 run 含 `timeseries` 阶段，`timelineStages` 静默丢弃。
**修复**：前端加 `timeseries: '时间序列'`，或后端从 `ALL_STAGES` 移除 `TIMESERIES`（设计书说”不应被误写为 ETL 必选阶段”）。

### P2 — `execute_import` 硬编码 `limit(100)`

每次 import 最多处理 100 条 JD。>100 条需多次 run。
**修复**：移除 `limit(100)` 或改为可配置参数。

### P2 — `execute_clean` 不变更 `JdStatus`

clean 阶段修改 `clean_text`/`job_title` 但不改 `status`（仍 `raw`），与 P1 `cleaned` 缺失问题关联。

### ~~P2 — M5 零数据边界~~ → **已闭环**

`/pipeline/data-quality` 零数据 `overall_score` 1.0→0.0 + `baseline_available=false`（本轮已修，见 `status_aggregator.py`）。

### ~~P2 — zombie-skip 回归测试~~ → **已闭环**

`test_zombie_skip.py` 7 个测试 + `_pick_best_run()` 纯函数（本轮已补）。

## 结论

核心功能（管理操作 / SSE / outbox / 僵尸跳过 / M5 守卫）与设计书一致。主要偏移在**阶段粒度**（设计书 3 阶段 vs 代码 5-6 阶段，需更新设计书）和**阶段间数据流**（dedup/clean 并行 + 缺 cleaned 状态 + import limit 100），建议 P1 修复串行 + cleaned 状态 + 标签，P2 修复 timeseries 对齐 + limit 移除。