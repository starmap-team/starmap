# Phase 3 RESEARCH — Pipeline Monitor 设计对齐 + 新用户引导

**Date:** 2026-07-28
**Method:** Serena 辅助三端审计 + 设计书比对 + 前端 UX 走查

## 1. 设计书 vs 代码阶段结构

| 来源 | 阶段 | DAG |
|---|---|---|
| `docs/architecture/pipeline.md` mermaid | 3: `crawl → dedup_clean → import_sync` | 串行 |
| 后端 `StageName` + `STAGE_EXECUTORS` | 6: `crawl, dedup, clean, import, graph_sync, timeseries` | dedup∥clean, 串行其余 |
| 后端模型 docstring | 5: 无 timeseries | 同代码 |
| 前端 `ALL_STAGE_NAMES` | 5: 无 timeseries | 同代码 |
| 前端 `STAGE_LABELS` | 5 个中文标签 | 同 |

**结论**: 设计书 mermaid 需更新为 5 阶段（代码是事实源）。设计书自身声明"以 StageName 为准"但 mermaid 画 3 阶段——自相矛盾。

## 2. dedup ∥ clean 并行问题

`STAGE_DEPS`: `dedup: [crawl], clean: [crawl]` → 并行。
设计书 mermaid: `crawl → dedup_clean` → 串行。

**影响**: clean 处理所有 `raw` 记录（含 dedup 将标记为 duplicate 的），浪费计算。不影响正确性（import 只读 `raw`=非重复），但浪费资源。

**Serena 验证**: `get_ready_stages` 确认 clean 在 crawl 完成后立即 ready，不等 dedup。

## 3. JdStatus 状态机缺陷

当前: `raw → extracted`（import 设置）, `raw → duplicate`（dedup 设置）。
**缺失**: 无 `cleaned` 状态。clean 阶段修改 `clean_text`/`job_title` 但不改 status。

**影响**: import 读 `status=raw`，无法区分"已清洗"与"未清洗"。clean 部分失败时 import 处理未清洗记录。

## 4. import 标签不含 LLM 抽取

前端 `STAGE_LABELS.import = '数据入库'`。
实际 `execute_import` 执行: LLM 技能抽取（`run_batch_extract_jd`）+ PG 持久化。
设计书 `import_sync` 描述: "LLM 抽取并持久化 PG，再同步图投影"。

## 5. timeseries 前后端不对齐

后端 `StageName.TIMESERIES` 存在，`OPTIONAL_STAGES` 含它。
前端 `ALL_STAGE_NAMES` / `STAGE_LABELS` 不含。
`timelineStages` computed 静默丢弃 timeseries 阶段。

## 6. import limit(100)

`execute_import` 中 `s.query(JdRaw).filter(...).limit(100)`。
>100 条 JD 需多次 run 才能处理完。

## 7. 新用户引导现状

**已有**:
- `BusinessBanner` 描述 pipeline 全链路
- `PipelineGlossary` 术语词典（10+ 术语，含示例）
- "新手指引" 按钮打开 glossary drawer
- SSE 实时指示器
- 空态文案（"暂无数据"等）
- `el-tooltip` 帮助图标

**缺失**（新用户无法知晓如何使用）:
- 无"如何触发流水线"的步骤引导（触发按钮无 tooltip 说明前置条件）
- 无"如何查看运行结果"的引导（DAG 各阶段含义无内联说明）
- 无"如何处理失败"的引导（失败阶段的重试/恢复按钮无上下文说明）
- 无"如何配置定时调度"的引导（Cron 表达式输入无格式提示/示例）
- 无"如何理解数据质量指标"的引导（quality 面板各维度含义无 tooltip）
- DAG 各阶段卡片无 hover 说明（该阶段做什么、依赖什么）
- 触发对话框中 `selectedStages` 多选无说明（为什么可以选部分阶段）

## 8. 闭环可用性缺口

| 功能 | 设计书要求 | 当前状态 | 缺口 |
|---|---|---|---|
| 触发流水线 | 管理员可触发 | ✅ triggerPipeline | 无前置条件提示 |
| 取消运行 | 管理员可取消 | ✅ cancelRun | 无确认对话框说明影响 |
| 重试阶段 | 单阶段重试 | ✅ retryStage | 无"哪些阶段可重试"提示 |
| 恢复运行 | 恢复失败 run | ✅ resumeRun | 无"恢复 vs 重试"区别说明 |
| 处理卡死 | force-advance/reset | ✅ 两个端点 | 无"何时使用"说明 |
| SSE 实时 | 实时更新 | ✅ useSSE | 连接断开时无用户可见提示 |
| 轮询降级 | SSE 降级 | ✅ poll | 降级时无用户可见提示 |
| 定时调度 | Cron 配置 | ✅ CRUD | Cron 输入无格式校验/示例 |

## 9. 后端 API 端点清单（Serena 验证）

| 端点 | 方法 | 说明 | 设计书覆盖 |
|---|---|---|---|
| `/pipeline/status` | GET | 状态概览 | ✅ |
| `/pipeline/stages` | GET | 阶段实时状态 | ✅ |
| `/pipeline/runs` | GET | 运行历史 | ✅ |
| `/pipeline/runs/{id}` | GET | 单次详情 | ✅ |
| `/pipeline/trigger` | POST | 手动触发 | ✅ |
| `/pipeline/runs/{id}/cancel` | POST | 取消 | ✅ |
| `/pipeline/runs/{id}/retry` | POST | 重试阶段 | ✅ |
| `/pipeline/runs/{id}/resume` | POST | 恢复 | ✅ |
| `/pipeline/runs/{id}/force-advance` | POST | 强制推进 | ✅ |
| `/pipeline/runs/{id}/force-reset` | POST | 强制重置 | ✅ |
| `/pipeline/events` | GET(SSE) | 实时推送 | ✅ |
| `/pipeline/events-poll` | GET | 轮询降级 | ✅ |
| `/pipeline/data-quality` | GET | 数据质量 | ✅ |
| `/pipeline/datasources` | GET | 数据源列表 | ✅ |
| `/pipeline/schedules` | CRUD | 定时调度 | ✅ |
| `/pipeline/config` | GET/PUT | 配置 | ✅ |
| `/pipeline/analyze` | POST | 求职者分析 SSE | ✅ |

## 10. 测试覆盖现状

| 测试文件 | 用例数 | 覆盖 |
|---|---|---|
| `test_zombie_skip.py` | 7 | _pick_best_run 优先级 |
| `test_contract_regression.py` | 4 | M2/M4/M5/M6 契约 |
| `PipelineMonitor.spec.ts` | 1 | 冒烟渲染 |
| **缺失** | — | DAG 渲染、SSE 事件、空态、触发流程、失败处理、定时调度 |