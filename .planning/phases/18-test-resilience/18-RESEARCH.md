# Phase 18 RESEARCH

## 1. 跨端 20 抽样测试改 pytest-asyncio

### 现状
- `backend/tests/integration/test_cross_tier_consistency.py` 用 `asyncio.run()` 嵌套调用
- pytest 默认是 sync, 嵌套 event loop 冲突
- 错误: `RuntimeError: Event loop is closed` + `'NoneType' object has no attribute 'send'`

### 修复方案

**方案 A: pytest-asyncio mode=auto (推荐)**
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

```python
import pytest

@pytest.mark.asyncio
async def test_cross_tier(trial):
    from app.db.session import get_async_engine
    # 直接 await
    engine = get_async_engine()
    async with AsyncSession(bind=engine) as s:
        ...
```

**方案 B: 改用 sync wrapper**
```python
def test_cross_tier(trial):
    import asyncio
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(_test_async())
    loop.close()
```

采用方案 A — 干净, async 上下文自然

### 文件变更
- `backend/pyproject.toml` — 加 `[tool.pytest.ini_options]`
- `backend/tests/integration/test_cross_tier_consistency.py` — 改 `@pytest.mark.asyncio`

## 2. 失败重试集成测试 (mock LLM)

### 现状
- 没有测试覆盖 "LLM 失败 → import 阶段如何" 
- 没有测试覆盖 "Redis 失败 → dedup 降级"
- 用户在生产环境遇到"做了一半"的情况时,没有自动化测试覆盖

### 修复方案

**新建 `test_pipeline_failure_retry.py`:**

```python
import pytest
from unittest.mock import patch, AsyncMock

class TestPipelineFailureRetry:
    """Phase 18-02: 阶段失败时数据不漂移, 重试后状态正确."""
    
    @patch("app.core.pipeline.executor.run_batch_extract_jd")
    def test_import_failure_doesnt_corrupt_clean_data(
        self, mock_extract
    ):
        """import 失败后, jd_raw 仍 status=raw, 不会被错误标 'cleaned'."""
        mock_extract.return_value = {"status": "failed", "error": "LLM timeout"}
        
        # 触发 import stage
        run_id = _trigger(["import"])
        run = _wait_terminal(run_id, max_wait=30)
        
        import_stage = next(s for s in run["stages"] if s["name"] == "import")
        assert import_stage["status"] == "failed"
        # jd_raw.status 仍为 raw (未被错误标 cleaned)
        # 这是 status gate 的作用
```

### 关键场景
- LLM 失败 → import failed, clean 数据保留
- Redis 失败 → dedup 降级到 legacy SimHash
- Neo4j 失败 → graph_sync 部分成功 (Phase 17 已实现)
- 全程 cancel → 上游保留, 下游 skipped
- retry 单 stage → 不重跑上游 (验证通过 outbox 状态)

## 3. 清理

### Active debug sessions
- `graph-child-nodes-fix.md` — 标记 resolved (3D 视图已工作)
- `position-list-detail-ux-resolved.md` — 已经是 "已解决" 但未改 frontmatter, 修正

### Pending todos
- `csv-import-endpoint.md` — Phase 17 已实现, archive
- `integrate-4-free-apis.md` — Phase 15 已实现, archive

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| pytest-asyncio 配置错误 | LOW | MED | pyproject.toml 是单行配置 |
| Mock LLM 测试与真实行为不同 | MED | LOW | 只 mock 错误路径 |
| 关闭 debug 后又出问题 | LOW | LOW | 目录保留 |