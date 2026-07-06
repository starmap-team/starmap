---
plan: 04-01
phase: 04-dataflow
status: complete
requirements:
  - EVAL-02
---

# Plan 04-01 Summary: EVAL-02 LLM Judge 真接线 + 超时降级

## What was built

为 `evaluation/judge_eval.py` 的 LLM judge 调用添加了 10 秒超时保护（D-11），确保失败/超时时静默回退到 `compute_skill_f1`（D-10），不阻塞主流程。

## Changes

### evaluation/judge_eval.py
- `_call_llm_judge()`: 将 `call_llm_with_fallback(prompt)` 包裹在 `asyncio.wait_for(..., timeout=10.0)` 中
- 捕获 `TimeoutError` 异常，返回 `(None, "LLM judge timed out after 10s")`
- `evaluate_single_sample()`: 当 `llm_score is None` 时记录降级日志 `logger.info("LLM judge unavailable for sample {}, using F1 only", sid)`
- 添加 `__main__` 自检块，验证 F1 fallback 路径

## Verification

- `python evaluation/judge_eval.py` 自检通过，输出 "F1 fallback OK"
- `ruff check evaluation/judge_eval.py` 无错误

## Key files

- `evaluation/judge_eval.py` — 10s 超时 + 降级逻辑 + 自检块

## Deviations

None — implementation matches D-09~D-12 exactly.
