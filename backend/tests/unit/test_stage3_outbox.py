"""Phase 7 P0-1 fix: outbox regression test for run_batch_extract_jd.

When Neo4j write fails after Postgres commit, the outbox record must be
marked 'failed' so it can be retried later (preventing PG/Neo4j drift).
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.tasks import stage3_services as s


def _build_fake_session() -> Any:
    """Async ctx-mgr session with begin(); used by run_batch_extract_jd."""

    class _Session:
        async def execute(self, *a: Any, **k: Any) -> None: return None
        def add(self, *a: Any, **k: Any) -> None: pass
        async def flush(self) -> None: pass

        async def __aenter__(self) -> _Session: return self
        async def __aexit__(self, *a: Any) -> bool: return False

        def begin(self) -> Any:
            class _Tx:
                async def __aenter__(self_inner) -> None: return None
                async def __aexit__(self_inner, *a: Any) -> bool: return False
            return _Tx()

    return _Session()


class _FakeEngine:
    async def dispose(self) -> None: return None


class _FakeSM:
    """Session factory: returns a fresh fake session each call."""

    def __call__(self) -> Any: return _build_fake_session()


def _patch_common_deps(
    monkeypatch: pytest.MonkeyPatch,
    *,
    graph_write_impl: Any,
) -> dict:
    """Patch stage3_services + executor deps. Returns the capture dict."""
    captured: dict = {}

    fake_record = type("R", (), {"id": uuid.uuid4(), "job_title": "Python Dev"})

    async def fake_persist(session: Any, jd_text: str, result: Any, **kwargs: Any) -> Any:
        # D5 根治: persist 现返回 (record, position_id, skill_ids) 供图写穿线 canonical_id
        return fake_record(), str(uuid.uuid4()), {}

    async def fake_extract(jd_text: str, options: Any = None) -> dict:
        return {"success": True, "data": {"position_name": "Python Dev", "required_skills": []}}

    async def fake_load_counts(sm: Any) -> dict: return {}

    def fake_sessionmaker(engine: Any, expire_on_commit: bool = False) -> _FakeSM:
        return _FakeSM()

    monkeypatch.setattr(s, "persist_extraction_result", fake_persist)
    monkeypatch.setattr(s, "extract_from_jd", fake_extract)
    monkeypatch.setattr(s, "write_single_extraction_to_graph", graph_write_impl)
    monkeypatch.setattr(s, "_load_source_counts", fake_load_counts)
    monkeypatch.setattr(s, "get_async_engine", lambda: _FakeEngine())
    monkeypatch.setattr(s, "async_sessionmaker", fake_sessionmaker)

    from app.core.pipeline import executor as ex

    async def fake_create(sf: Any, outbox_id: Any, run_id: Any, extraction_ids: Any = None) -> None:
        captured["outbox_id"] = outbox_id
        captured["run_id"] = run_id
        captured["extraction_ids"] = extraction_ids

    async def fake_complete(sf: Any, outbox_id: Any, triples: int) -> None:
        captured["completed"] = (outbox_id, triples)

    async def fake_fail(sf: Any, outbox_id: Any, err: str) -> None:
        captured["failed"] = (outbox_id, err)

    monkeypatch.setattr(ex, "_create_outbox_record", fake_create)
    monkeypatch.setattr(ex, "_complete_outbox_record", fake_complete)
    monkeypatch.setattr(ex, "_fail_outbox_record", fake_fail)
    return captured


@pytest.mark.asyncio
async def test_outbox_marked_failed_when_graph_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neo4j write failure must flip outbox to 'failed'; no completed marker."""

    async def failing_graph_write(extraction: Any, canonical_ids: dict | None = None) -> Any:
        raise RuntimeError("neo4j connection refused")

    captured = _patch_common_deps(monkeypatch, graph_write_impl=failing_graph_write)

    with pytest.raises(RuntimeError, match="neo4j connection refused"):
        await s.run_batch_extract_jd("fake JD text")

    assert "outbox_id" in captured, "outbox create must run before graph write"
    assert "failed" in captured, "outbox must be marked failed on graph write error"
    assert "completed" not in captured, "outbox must NOT be completed on error"


@pytest.mark.asyncio
async def test_outbox_completed_when_graph_write_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful graph write must mark outbox 'completed'."""

    async def ok_graph_write(extraction: Any, canonical_ids: dict | None = None) -> dict:
        return {"triples_merged": 5}

    captured = _patch_common_deps(monkeypatch, graph_write_impl=ok_graph_write)

    result = await s.run_batch_extract_jd("fake JD text")

    assert result["status"] == "completed"
    assert "completed" in captured, "outbox must be marked completed on success"
    assert captured["completed"][1] == 5, "triples_written must be propagated"
    assert "failed" not in captured

    # H1: ad-hoc extraction must use run_id=None + extraction_ids for traceability
    assert captured.get("run_id") is None, "run_id must be NULL for ad-hoc extraction"
    assert captured.get("extraction_ids"), "extraction_ids must be populated for audit"


@pytest.mark.asyncio
async def test_retry_worker_does_not_swallow_completed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 23 Task 1: retry worker 只消费 failed 行，completed/drift_warning 不误捡。

    沿 `_list_retryable_outbox` 的 SQL 过滤 + Python 兜底过滤——completed 行已落库
    成功，重放会重复写图（即使 MERGE 幂等也造成 source_count 语义噪音），必须跳过。
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.tasks.outbox_retry import _list_retryable_outbox

    def _row(status: str, retry_count: int = 0) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(), status=status, retry_count=retry_count,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )

    rows = [
        _row("failed", retry_count=1),
        _row("completed"),
        _row("drift_warning"),
        _row("failed", retry_count=3),
    ]

    class _Scalars:
        def __init__(self, items: list) -> None:
            self._items = items

        def all(self) -> list:
            return self._items

    class _Result:
        def __init__(self, items: list) -> None:
            self._scalars = _Scalars(items)

        def scalars(self) -> _Scalars:
            return self._scalars

    class _Session:
        async def execute(self, *a: Any, **k: Any) -> _Result:
            return _Result(rows)

    picked = await _list_retryable_outbox(_Session())
    assert len(picked) == 1
    assert picked[0].status == "failed"
    assert picked[0].retry_count == 1  # completed/drift_warning/retry>=3 全部跳过
