# Phase 6: 架构重构 - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

收尾架构重构：复用已有的 `frontend/src/components/Graph2D.vue`(667 行) 与 `Graph3D.vue`(779 行)，让 Home.vue 从 821 行缩到 ≤350 行；新建 `backend/app/db/session.py` 统一管理 async session，消除 `executor.py` 中 6 处内联 `create_async_engine` 与 `data_fusion.py` 中的 SimHash 重复实现；将 `frontend/src/stores/pipeline.ts` 与 `loop.ts` 合并为单一 pipeline store；将无主路径调用者的 `resume_eval.py` 函数迁入 `evaluation/judge_eval.py`。**不涉及**功能新增（DEC-001）、不改 API contract（DEC-004）、不重写已有架构（DEC-003），仅为可维护性导向的清理。

前置阶段已实现（**不在本阶段重做**）：
- ✅ `frontend/src/components/Graph2D.vue` 已封装 G6 渲染（HOME-SPLIT-01~04 部分就绪）
- ✅ `frontend/src/components/Graph3D.vue` 已封装 3D 渲染
- ✅ `backend/app/api/v1/pipeline/` 已拆分为 routes.py(539) + schemas.py(184) + serializers.py(57)（PIPE-SPLIT-01 就绪）
- ✅ `backend/app/core/pipeline/simhash.py` 已存在（90 行）作为 SimHash canon
- ✅ `backend/app/utils/async_helpers.py` 已存在，executor.py 已合并 `_run_async`（DEDUP-01 部分就绪）
- ✅ `backend/app/api/v1/graph.py` 6 个死端点已删除（CLEANUP-01 P5 完成）
- ✅ `composables/useGraphColors.ts` 已删除（COLOR-02 P5 完成）

本阶段 4 个真正灰色地带（仅实现细节，不重做）：
1. Home.vue 821→≤350 行的拆分粒度（template/composable/store）
2. Shared session 在 db/session.py 的 API 形态（factory vs global）
3. data_fusion.py 中 SimHash 重复的处理（同义函数 vs 删除）
4. pipeline.ts + loop.ts 合并方向与兼容策略

</domain>

<decisions>
## Implementation Decisions

### G1 Home.vue 拆分粒度（D-01~03）
- **D-01:** **复用 Graph2D.vue（667 行）+ Graph3D.vue（779 行）作为子组件**——Home.vue 的 `<Graph2D>` / `<Graph3D>` 标签已被识别为外部组件，Home.vue 仅持有 store 桥接、事件委托、toolbar 联动、模式切换（2D/3D/EVO）三段逻辑
- **D-02:** **抽离 composables（不是子组件）**——把 `useGraphToolbarState` / `useHomeLayout` / `useEvolutionPanel` 等业务 hooks 抽出到 `frontend/src/composables/home/`，组件树保持 Home.vue 单层 + 已有 Graph2D/Graph3D 子组件
- **D-03:** **目标 ≤350 行**——以 `wc -l Home.vue` 硬指标验证，ROADMAP 写的 1316 是早期估算过时数据，应以 821 行作为"重构前"基线

### G2 Shared Session 实现（D-04~07）
- **D-04:** **新建 `backend/app/db/session.py`**——暴露 `get_async_engine()` 单例（lru_cache 包装）+ `get_session_factory()` 工厂 + `async_session_scope()` 上下文管理器
- **D-05:** **executor.py 6 处 `create_async_engine` 全部替换**——直接 `from app.db.session import get_async_engine, get_session_factory`，移除局部引擎创建
- **D-06:** **Celery 任务也使用同一工厂**——`backend/app/tasks/celery_app.py` 改用 `get_async_engine()`，确保 worker 与 FastAPI 共享连接池配置
- **D-07:** **保留 `pool_pre_ping=True`**——Phase 4 已验证长连接稳定性，迁移后保持

### G3 SimHash 重复处理（D-08~10）
- **D-08:** **保留 data_fusion.py 中的重复实现为薄包装**——`data_fusion._simhash` / `compute_simhash` 改为 `from app.core.pipeline.simhash import _simhash, compute_simhash` 转发 + 同义重命名（如 `compute_simhash = simhash.compute_simhash`），避免 break 调用方
- **D-09:** **simhash.py 作为 canon 唯一实现**——所有新代码引用 `from app.core.pipeline.simhash import ...`，老代码逐步迁移
- **D-10:** **不删除 data_fusion.py**——它还承担 dedup 主逻辑（`remove_near_duplicates`），仅 SimHash 部分去重；迁延到 Phase 7+ 再考虑整文件去重

### G4 Pipeline Store 合并（D-11~13）
- **D-11:** **合并为单一 `frontend/src/stores/pipeline.ts`**——将 `loop.ts` 中的 `runRequestStage` / `runRequestLoop` / `runRequestRetrieval` 三个子 namespace 迁入 pipeline.ts
- **D-12:** **保留 `loop.ts` 兼容层**——`loop.ts` 暂时保留为 re-export（`export * from './pipeline'`），给已有调用方 1 个 phase 缓冲期
- **D-13:** **Phase 6 不删除 loop.ts**——仅迁移实现 + 加 deprecation 注释；删除作为 Phase 7+ 任务

### G5 resume_eval 处理（D-14~15）
- **D-14:** **若 `resume_eval.py` 无主路径调用者（仅 evaluation 包内使用）**——迁入 `evaluation/judge_eval.py` 同模块，函数保留为 module-level function
- **D-15:** **若 resume_eval.py 被主路径 import**——保留原位，只加 `app/core/extraction/resume_eval.py` → 推荐调用方使用 evaluation

### Claude's Discretion
- Home.vue 中如发现可抽取的子组件（如独立的 `EvolutionPanel.vue` 或 `LayerToolbar.vue`），具体边界由 Claude 决定
- 拆分中是否同时调整 `<style>` 与 `<template>` 行数比例（如要求 template ≥ 60%）
- `db/session.py` 中是否暴露 FastAPI dependency `get_db_session()` 供路由层使用（建议暴露，便于后续迁移）
- `data_fusion.py` 中其余函数（`_tokenize` 等）是否也迁向 simhash.py 同模块；建议仅 SimHash 部分迁移，其余函数保留
- pipeline.ts 合并后 loop.ts 兼容层的过期时间（建议在 README 中写"将在 Phase 7 删除"）

### 验证指标（D-16~17，硬性）
- **D-16:** **`wc -l frontend/src/pages/Home.vue` ≤ 350**——plan 完成时直接验证
- **D-17:** **CI 工具链全绿**——`vue-tsc --noEmit && eslint . && ruff check backend/ && pytest tests/`，包含现有 e2e smoke 不退化

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策
- `.planning/PROJECT.md` — 项目定义、5大功能+2创新点、DEC-001~006
- `.planning/REQUIREMENTS.md` §Phase 6 — 12 个需求 (HOME-SPLIT-01~04, PIPE-SPLIT-01~04, DEDUP-01~03)
- `.planning/ROADMAP.md` §Phase 6 — 成功标准（Home≤350、pipeline 三文件≤300、create_async_engine 1 处、run_async 1 处、工具链全绿）
- `.planning/STATE.md` — 当前状态（Home.vue=821 行 baseline，非 1316）、DEC-010 颜色迁移

### 前序阶段决策（不重做）
- `.planning/phases/01-core-bugfix/01-CONTEXT.md` — DEC-P1-01~03
- `.planning/phases/04-dataflow/04-CONTEXT.md` — Phase 4 数据流贯通决策 D-01~15
- `.planning/phases/05-style-unify/05-CONTEXT.md` — Phase 5 颜色统一决策 D-01~14（了解设计 token 边界）

### 前端（部分就绪，需复用）
- `frontend/src/pages/Home.vue` (821 行，重构前 baseline) — D-01~03 拆分目标
- `frontend/src/components/Graph2D.vue` (667 行) — D-01 复用入口
- `frontend/src/components/Graph3D.vue` (779 行) — D-01 复用入口
- `frontend/src/stores/pipeline.ts` — D-11 合并目标
- `frontend/src/stores/loop.ts` — D-12 兼容层来源
- `frontend/src/composables/` — D-02 抽取 composables 的目标目录

### 后端（部分就绪，需清理）
- `backend/app/api/v1/pipeline/` — D-PIPE-SPLIT 已完成，本阶段不动
- `backend/app/api/v1/pipeline/routes.py` (539 行) — 接近上限但 PIPE-SPLIT-01 已拆，无须再动
- `backend/app/core/pipeline/executor.py` — D-05 6 处 create_async_engine 替换目标
- `backend/app/core/pipeline/simhash.py` (90 行) — D-08 SimHash canon
- `backend/app/core/pipeline/data_fusion.py` (249 行) — D-08 SimHash 重复源
- `backend/app/services/dedup_service.py` — SimHash 第三个调用点（D-09 验证）
- `backend/app/utils/async_helpers.py` — DEDUP-01 部分已就绪
- `backend/app/tasks/celery_app.py` — D-06 Celery 复用统一引擎
- `backend/app/core/extraction/resume_eval.py` — D-14~15 处理目标
- `backend/app/db/` — D-04 新建 session.py 的目标目录

### 测试与验证
- `tests/e2e/smoke_test.py` — D-17 CI 工具链验证入口
- `tests/conftest.py` — pytest fixtures 复用
- `pyproject.toml` (ruff 配置) / `package.json` (eslint 配置) — D-17 必须通过

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/components/Graph2D.vue`（G6 渲染封装，667 行）—— D-01 Home.vue 直接 `<Graph2D>` 引用，作为子组件
- `frontend/src/components/Graph3D.vue`（3D 渲染封装，779 行）—— 同上
- `backend/app/core/pipeline/simhash.py`（90 行 `_simhash` + `compute_simhash` + `hamming_distance`）—— D-08~09 SimHash canon
- `backend/app/utils/async_helpers.py`（`run_async` 已统一）—— D-06 直接复用
- `backend/app/api/v1/pipeline/{routes,schemas,serializers}.py`（PIPE-SPLIT-01 已完成）—— 本阶段跳过

### Established Patterns
- Home.vue 当前以 `<Graph2D>` / `<Graph3D>` 子组件标签显示调用，拆分时此 pattern 自然继承
- executor.py 内 `from app.utils.async_helpers import run_async` —— D-05 同样 import 风格引入 `get_async_engine`
- `pipeline_runs.run_id` 表贯穿——D-06 Celery 复用共享 session 时不要破坏 run_id 关联
- Element Plus + 设计 token 体系——Home.vue 拆分后样式保持 `<style scoped>` 一致

### Integration Points
- `frontend/src/pages/Home.vue` —— D-01~03 拆分主体，目标 ≤350 行
- `frontend/src/stores/loop.ts` —— D-12 标记 deprecated 后透传 pipeline.ts
- `backend/app/db/session.py` —— D-04 新建文件
- `backend/app/core/pipeline/executor.py` —— D-05 替换 6 处 `create_async_engine` 调用
- `backend/app/tasks/celery_app.py` —— D-06 替换同步任务入口的 engine 创建
- `backend/app/core/pipeline/data_fusion.py` —— D-08 SimHash 部分改为薄包装转发
- `backend/app/core/extraction/resume_eval.py` —— D-14~15 按调用者情况处理

</code_context>

<specifics>
## Specific Ideas

- D-03：ROADMAP 写 Home.vue "1316→350" 是早期估算 baseline；当前 821 行已说明 Graph2D/Graph3D 早期拆分已部分完成，Phase 6 真正的目标是从 821→≤350
- D-04：建议 `db/session.py` 同时暴露 `@asynccontextmanager async def session_scope()` 与 FastAPI `Depends(get_db)` 两种入口，便于 FastAPI 路由复用（虽 Phase 6 不动路由层）
- D-08：data_fusion.py 中的 SimHash 重复实现可能是早期遗留未删除，建议用 `from app.core.pipeline.simhash import compute_simhash as _simhash` 一行替换实现，保留函数签名
- D-11：`loop.ts` 中三个 namespace 合并入 pipeline.ts 后，建议保留 namespace 结构（`usePipelineStore().loopStage` / `.loopRun` 等访问方式不变），仅文件合并
- D-17：硬指标验证入口可加一个 Phase 6 验收脚本 `tests/verify_phase6.py` 一键运行 5 项检查（Home 行数 + 4 项 grep 唯一性 + vue-tsc/eslint/ruff/pytest）

</specifics>

<deferred>
## Deferred Ideas

- **Phase 6 写一个快速验证脚本 `tests/verify_phase6.py`**——D-17 中提到可作 Phase 7+ 任务；如本 phase 觉得必要可一并交付
- **Graph2D.vue 667 行二次拆分**——已封装但仍较大；属 Phase 7+ 范围
- **Home.vue 拆分到 200 行以下**——Phase 6 目标 ≤350；进一步拆分属过度工程
- **Python 类型补全（mypy strict）**——超出 Phase 6 范围
- **loop.ts 实际删除（兼容层退役）**——D-13 推迟到 Phase 7+
- **data_fusion.py 整文件删除**——D-10 仍承担 dedup 主逻辑，保留到 Phase 7+
- **FastAPI 路由改造使用 get_db dependency**——Phase 6 不动路由层
- **前端 E2E Playwright 验证 Home.vue 拆分后无回归**——超出 Phase 6 范围

</deferred>

---

*Phase: 06-arch-refactor*
*Context gathered: 2026-07-07*
