---
phase: 17-pipeline-integrity
plan: 03
completed: 2026-07-30
status: completed
---

# Plan 17-03: import 兜底 + graph_sync 部分成功 (B3, B4) — COMPLETED

## 已完成

### Task 1: graph_writer 缺失 position_name 静默跳过 ✅
**文件:** `backend/app/core/extraction/graph_writer.py:622-627`

```python
if not _raw_name or not str(_raw_name).strip():
    # Phase 17-03 (Fix B3): 缺失 position_name 静默跳过, 不阻塞 batch
    logger.warning(f"graph_writer: extraction ... missing position_name, skipping")
    return {"positions": 0, "skills": 0, "requires": 0, "skipped": True, "reason": "missing_position_name"}
```

### Task 2: batch_write_extractions try/except 隔离 ✅
**文件:** `backend/app/core/extraction/graph_writer.py:715-727`

```python
for extraction in extractions:
    try:
        summary = await write_extraction_to_graph(extraction, driver)
    except Exception as exc:
        logger.warning(f"batch_write_extractions: skipped extraction: {exc}")
        summary = {"...skipped": True, "reason": str(exc)[:200]}
    summaries.append(summary)
```

### Task 3: execute_graph_sync 错误消息更新 ✅
**文件:** `backend/app/core/pipeline/executor.py:741-750`

移除了"missing position_name"分支 (现在 graph_writer 跳过, 不会抛错),新增"auth"分支。

## 验证

| 验证 | 结果 |
|------|------|
| 单元测试 (124 个) | ✅ pass |
| import 编译 | ✅ OK |
| graph_writer 静默跳过 | ✅ (修改后代码 review) |

## 行为变化

**之前 (一坏全坏):**
- 一条 extraction 缺 position_name → 整个 batch 失败
- 用户友好错误: "图谱同步失败：部分 JD 缺少职位名称字段..."

**现在 (部分成功):**
- 单条 extraction 缺 position_name → 跳过该条, 继续处理其他
- 错误消息变为: "图谱同步失败：Neo4j 连接异常..." (只对真正失败)
- audit log 记录 skipped 数量

## 文件变更

- `backend/app/core/extraction/graph_writer.py` (Task 1+2)
- `backend/app/core/pipeline/executor.py` (Task 3)