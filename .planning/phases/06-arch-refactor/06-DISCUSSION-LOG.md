# Phase 6: 架构重构 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 06-arch-refactor
**Areas discussed:** Phase 6 范围、Home.vue 拆分粒度、SimHash 重复处理、共享 Session 实现、Pipeline Store 合并、resume_eval 去留、拆分节奏、验证手段

---

## G0 Phase 6 范围定位

| Option | Description | Selected |
|--------|-------------|----------|
| 聚焦剩余灰色地带 | 跳过已完成项（Graph2D/Graph3D/pipeline 三文件/simhash 模块），仅讨论剩余事项 | |
| 全量讨论所有 12 个需求 | 把所有需求纳入讨论范围，扩大覆盖 | ✓ |
| 只关注 Home.vue 拆分 + DEDUP | 只讨论最大块的两件事 | |

**User's choice:** 全量讨论所有 12 个需求（理由：保证 Phase 6 完整覆盖所有需求，便于规划阶段做 plan 切分）

---

## G1 Home.vue 拆分粒度

| Option | Description | Selected |
|--------|-------------|----------|
| Graph2D/Graph3D 已封装复用 | Home.vue 复用已存在的 Graph2D/Graph3D 子组件，把业务逻辑抽到 composables | ✓ |
| 拆分为多个小子组件 | 进一步把 GraphCanvas/FilterPanel/EvolutionPanel 拆出 | |
| 仅抽离 composable，不动结构 | 不改组件树，仅把 hooks 抽离 | |

**User's choice:** Graph2D/Graph3D 已封装复用（推荐）—— 复用 Phase 3-5 已有的 Graph2D/Graph3D 子组件，配合抽 composables 到 `frontend/src/composables/home/`

---

## G2 SimHash 重复处理

| Option | Description | Selected |
|--------|-------------|----------|
| data_fusion 中重复作为薄包装（保留函数签名） | data_fusion.py 中 SimHash 改为 import simhash.py + 同义重命名，保留调用兼容 | ✓ |
| data_fusion 整体删除 | 整体迁至 services，data_fusion.py 删 | |
| simhash.py 作为 canon，其他调用 deprecated | simhash.py 是规范，其他标 deprecation | |

**User's choice:** 保留 data_fusion 中的重复实现为薄包装——理由：data_fusion 还有 dedup 主逻辑（`remove_near_duplicates`），整体删除超出 Phase 6 范围；SimHash 部分通过同义重命名简化

---

## G3 共享 Session 实现

| Option | Description | Selected |
|--------|-------------|----------|
| 新建 db/session.py 共享引擎 + sessionmaker | 暴露 `get_async_engine()` lru_cache 单例 + factory + async context manager | ✓ |
| 在 FastAPI lifespan 中初始化全局引擎 | app.state.engine 启动时创建，复用同一实例 | |
| Celery 任务依赖注入 session_factory | 每个 Celery 任务接收 session_factory 参数 | |

**User's choice:** 新建 db/session.py（推荐）—— 同时暴露 FastAPI dependency `get_db()` 以便未来路由迁移

---

## G4 Pipeline Store 合并

| Option | Description | Selected |
|--------|-------------|----------|
| 合并为一个 pipeline store | 把 loop.ts 中的 3 个 namespace 迁入 pipeline.ts；loop.ts 留为 re-export 兼容层 | ✓ |
| 反方向合并 | loop.ts 吸收 pipeline.ts | |
| 保持独立，去重复 | 不合并文件，仅去重 action/state | |

**User's choice:** 合并到一个 pipeline store，loop.ts 作为兼容层保留 1 个 phase 缓冲期（理由：避免 break 已有调用方）

---

## G5 resume_eval 去留

| Option | Description | Selected |
|--------|-------------|----------|
| 迁移到 evaluation 模块 | 若无主路径调用者则迁入 evaluation/judge_eval.py | ✓ |
| 保留原位 + deprecation 警告 | 不迁移，加注释提醒 | |
| inline 进主调用者 | 检查调用点，可 inline 则 inline | |

**User's choice:** 迁移到 evaluation 模块（需先 grep 调用者决定）—— 若 resume_eval.py 仅在 evaluation 包内使用则迁移，否则保留原位

---

## G6 拆分节奏（plan 粒度）

| Option | Description | Selected |
|--------|-------------|----------|
| 2-3 个 plan | P1 Home.vue + P2 db/session 共享 + P3 SimHash/Store/resume_eval 收尾 | ✓ |
| 5 个 plan 粒度细 | 每个子领域独立 plan | |
| 2 个 plan 粗粒度 | Home.vue + db/session 一组；剩余清理一组 | |

**User's choice:** 2-3 个 plan（推荐）—— 平衡覆盖率与单 plan 复杂度

---

## G7 验证手段

| Option | Description | Selected |
|--------|-------------|----------|
| 硬指标 Home≤350 行 + ci 全绿 | wc -l Home.vue + vue-tsc + eslint + ruff + pytest | ✓ |
| 加可读性评估指标 | 额外加 store 调用比例、template/style 比例 | |
| 仅人工 review | 不加自动化验证 | |

**User's choice:** 硬指标（推荐）—— Home≤350 行硬指标 + 4 项 grep 唯一性 + 工具链全绿

---

## Claude's Discretion

- Home.vue 中可抽取的子组件具体边界（建议：仅当某段 template 逻辑独立可复用 >150 行才抽）
- 拆分中 `<style>` 与 `<template>` 行数比例（建议：template ≥ 60%）
- `db/session.py` 是否暴露 FastAPI dependency（建议暴露，便于未来路由迁移）
- `data_fusion.py` 其余函数是否也迁向 simhash.py（建议仅 SimHash 部分迁移）
- pipeline.ts 合并后 loop.ts 兼容层过期时间（建议在 README 注明 "将在 Phase 7 删除"）

## Deferred Ideas

- **Phase 6 写一个快速验证脚本 `tests/verify_phase6.py`**——如本 phase 觉得必要可一并交付（属 Phase 7+）
- **Graph2D.vue 667 行二次拆分**——属 Phase 7+
- **Home.vue 拆分到 200 行以下**——Phase 6 目标 ≤350
- **Python 类型补全（mypy strict）**——超出范围
- **loop.ts 实际删除（兼容层退役）**——推迟到 Phase 7+
- **data_fusion.py 整文件删除**——仍承担 dedup 主逻辑，保留
- **FastAPI 路由改造使用 get_db dependency**——Phase 6 不动路由层
- **前端 E2E Playwright 验证 Home.vue 拆分后无回归**——超出范围
