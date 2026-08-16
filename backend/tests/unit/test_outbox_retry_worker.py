"""Outbox retry worker tests (Phase 23 Task 1 — DC-02/DF-01).

Covers:
- worker 只捡 `status='failed' AND retry_count<3`，跳过 completed/drift_warning
- 重放成功后 `_complete_outbox_record`；再次失败 retry_count+1
- retry_count>=3 触发告警日志 + audit_events 行（mock 断言 audit insert）
- 超龄 pending 行（>6h）被 sweep
- source_count max 语义：同 skill 重复 merge 不膨胀（graph_writer 侧断言）
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.extraction_models import JDExtractionRecord
from app.tasks import outbox_retry as w


def _make_row(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "run_id": None,
        "extraction_ids": [],
        "status": "failed",
        "triples_written": 0,
        "error": None,
        "retry_count": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── Fake session / session-factory helpers ─────────────────────────────────


class _FakeScalars:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class _FakeScalarsResult:
    def __init__(self, items: list) -> None:
        self._scalars = _FakeScalars(items)

    def scalars(self) -> _FakeScalars:
        return self._scalars


class _FakeRowsResult:
    """Result whose `.all()` returns rows (for select(PositionRecord.name, ...))."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _FakeSession:
    """execute() 按调用顺序返回预设结果，并记录 stmt。"""

    def __init__(self, execute_returns: list | None = None) -> None:
        self._execute_returns = list(execute_returns or [])
        self._idx = 0
        self.stmts: list = []

    async def execute(self, stmt, *args, **kwargs):
        self.stmts.append(stmt)
        if self._idx < len(self._execute_returns):
            r = self._execute_returns[self._idx]
            self._idx += 1
            return r
        return _FakeScalarsResult([])

    async def commit(self) -> None:
        pass

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args) -> bool:
        return False


class _FakeSM:
    """Session factory: returns a (possibly shared) fake session."""

    def __init__(self, session: _FakeSession | None = None) -> None:
        self._session = session or _FakeSession()

    def __call__(self) -> _FakeSession:
        return self._session


# ── _list_retryable_outbox ──────────────────────────────────────────────────


class TestListRetryableOutbox:
    @pytest.mark.asyncio
    async def test_only_failed_below_max_retry(self) -> None:
        rows = [
            _make_row(status="failed", retry_count=1),
            _make_row(status="failed", retry_count=0),
            _make_row(status="completed", retry_count=0),
            _make_row(status="drift_warning", retry_count=0),
            _make_row(status="failed", retry_count=3),
        ]
        session = _FakeSession([_FakeScalarsResult(rows)])
        result = await w._list_retryable_outbox(session)

        assert len(result) == 2
        assert all(r.status == "failed" for r in result)
        assert all((r.retry_count or 0) < w.MAX_RETRY_COUNT for r in result)
        # 不吞 completed / drift_warning 行
        assert not any(r.status != "failed" for r in result)

        sql = str(session.stmts[0])
        assert "graph_write_outbox" in sql
        assert "retry_count" in sql and "graph_write_outbox.status" in sql

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self) -> None:
        session = _FakeSession([_FakeScalarsResult([])])
        assert await w._list_retryable_outbox(session) == []


class TestSweepStalePending:
    @pytest.mark.asyncio
    async def test_only_stale_pending_picked(self) -> None:
        old = _make_row(status="pending", created_at=datetime.now(UTC) - timedelta(hours=7))
        fresh = _make_row(status="pending", created_at=datetime.now(UTC) - timedelta(hours=1))
        failed = _make_row(status="failed", created_at=datetime.now(UTC) - timedelta(hours=7))
        session = _FakeSession([_FakeScalarsResult([old, fresh, failed])])
        result = await w._sweep_stale_pending(session)

        assert len(result) == 1
        assert result[0] is old
        sql = str(session.stmts[0])
        assert "created_at" in sql and "graph_write_outbox.status" in sql


# ── _replay_outbox_row ──────────────────────────────────────────────────────


class TestReplayOutboxRow:
    def _build_sm_and_rows(
        self,
        extraction_id: uuid.UUID,
        pos_id: uuid.UUID,
        skill_id: uuid.UUID,
    ) -> tuple[_FakeSM, list[object]]:
        record = JDExtractionRecord(
            id=extraction_id,
            job_title="Python Dev",
            extracted_skills={
                "position_name": "Python Dev",
                "required_skills": [{"name": "FastAPI"}],
            },
        )
        session = _FakeSession([
            _FakeScalarsResult([record]),
            _FakeRowsResult([("Python Dev", pos_id)]),
            _FakeRowsResult([("FastAPI", skill_id)]),
        ])
        return _FakeSM(session), [record]

    @pytest.mark.asyncio
    async def test_replay_completes_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        extraction_id = uuid.uuid4()
        pos_id = uuid.uuid4()
        skill_id = uuid.uuid4()
        row = _make_row(extraction_ids=[str(extraction_id)], retry_count=0)
        sm, _ = self._build_sm_and_rows(extraction_id, pos_id, skill_id)

        captured: dict = {}
        calls: dict = {}

        async def fake_complete(sf, outbox_id, triples) -> None:
            captured["complete"] = (sf, outbox_id, triples)

        async def fake_batch(extractions, driver, canonical_ids_list=None) -> list:
            calls["extractions"] = extractions
            calls["canonical_ids_list"] = canonical_ids_list
            return [{"triples_merged": 5}]

        monkeypatch.setattr(
            "app.core.pipeline.stages.graph_sync._complete_outbox_record", fake_complete,
        )
        monkeypatch.setattr(
            "app.core.extraction.graph_writer.batch_write_extractions", fake_batch,
        )

        ok = await w._replay_outbox_row(sm, row, driver=None)

        assert ok is True
        assert captured["complete"][1] == row.id
        assert captured["complete"][2] == 5
        # canonical_ids_list 从 PG 重新解析并传入（Task 2 前置：canonical_id 必传）
        cids = calls["canonical_ids_list"][0]
        assert cids["position_id"] == str(pos_id)
        assert cids["skills"]["FastAPI"] == str(skill_id)

    @pytest.mark.asyncio
    async def test_replay_failure_increments_and_alerts_at_max(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        extraction_id = uuid.uuid4()
        pos_id = uuid.uuid4()
        skill_id = uuid.uuid4()
        row = _make_row(extraction_ids=[str(extraction_id)], retry_count=2)  # 2+1=3 → alert
        sm, _ = self._build_sm_and_rows(extraction_id, pos_id, skill_id)

        failed: dict = {}
        alerted: dict = {}

        async def fake_batch(*args, **kwargs) -> None:
            raise RuntimeError("neo4j connection refused")

        async def fake_fail(sf, outbox_id, err) -> None:
            failed["call"] = (sf, outbox_id, err)

        async def fake_alert(sf, row_obj, err) -> None:
            alerted["call"] = (row_obj, err)

        monkeypatch.setattr(
            "app.core.extraction.graph_writer.batch_write_extractions", fake_batch,
        )
        monkeypatch.setattr(
            "app.core.pipeline.stages.graph_sync._fail_outbox_record", fake_fail,
        )
        monkeypatch.setattr(w, "_alert_max_retry", fake_alert)

        ok = await w._replay_outbox_row(sm, row, driver=None)

        assert ok is False
        assert failed["call"][1] == row.id
        assert "neo4j connection refused" in failed["call"][2]
        assert alerted["call"][0] is row  # retry_count 达上限 → 告警

    @pytest.mark.asyncio
    async def test_replay_failure_no_alert_below_max(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        extraction_id = uuid.uuid4()
        pos_id = uuid.uuid4()
        skill_id = uuid.uuid4()
        row = _make_row(extraction_ids=[str(extraction_id)], retry_count=0)  # 0+1=1 < 3
        sm, _ = self._build_sm_and_rows(extraction_id, pos_id, skill_id)

        alerted: dict = {}

        async def fake_batch(*args, **kwargs) -> None:
            raise RuntimeError("boom")

        async def fake_fail(sf, outbox_id, err) -> None:
            pass

        async def fake_alert(sf, row_obj, err) -> None:
            alerted["call"] = True

        monkeypatch.setattr(
            "app.core.extraction.graph_writer.batch_write_extractions", fake_batch,
        )
        monkeypatch.setattr(
            "app.core.pipeline.stages.graph_sync._fail_outbox_record", fake_fail,
        )
        monkeypatch.setattr(w, "_alert_max_retry", fake_alert)

        ok = await w._replay_outbox_row(sm, row, driver=None)

        assert ok is False
        assert "call" not in alerted  # 未达上限不告警

    @pytest.mark.asyncio
    async def test_empty_extraction_ids_completes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        row = _make_row(extraction_ids=[], retry_count=0)
        session = _FakeSession([_FakeScalarsResult([])])
        sm = _FakeSM(session)

        captured: dict = {}

        async def fake_complete(sf, outbox_id, triples) -> None:
            captured["complete"] = (sf, outbox_id, triples)

        monkeypatch.setattr(
            "app.core.pipeline.stages.graph_sync._complete_outbox_record", fake_complete,
        )

        ok = await w._replay_outbox_row(sm, row, driver=None)

        assert ok is True
        assert captured["complete"][2] == 0  # 无抽取记录 → complete(0)


# ── _alert_max_retry ────────────────────────────────────────────────────────


class TestAlertMaxRetry:
    @pytest.mark.asyncio
    async def test_writes_audit_event(self) -> None:
        row = _make_row(retry_count=3)
        session = _FakeSession()
        sm = _FakeSM(session)

        await w._alert_max_retry(sm, row, "boom")

        assert len(session.stmts) == 1
        sql = str(session.stmts[0])
        assert "audit_events" in sql
        assert "max_retry_alert" in sql


# ── _run (whole round) ──────────────────────────────────────────────────────


class TestRun:
    @pytest.mark.asyncio
    async def test_run_skips_completed_and_replays_eligible(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        eligible = _make_row(status="failed", retry_count=1, extraction_ids=[str(uuid.uuid4())])
        completed_row = _make_row(status="completed")
        retry3 = _make_row(status="failed", retry_count=3)
        drift = _make_row(status="drift_warning")
        stale_pending = _make_row(
            status="pending", created_at=datetime.now(UTC) - timedelta(hours=7),
        )

        session = _FakeSession([
            _FakeScalarsResult([eligible, completed_row, retry3, drift]),
            _FakeScalarsResult([stale_pending]),
        ])
        sm = _FakeSM(session)

        replayed: list = []

        async def fake_replay(sm_arg, row, driver) -> bool:
            replayed.append(row)
            return True

        class _FakeDriverCM:
            async def __aenter__(self) -> object:
                return object()

            async def __aexit__(self, *args) -> bool:
                return False

        monkeypatch.setattr(w, "_replay_outbox_row", fake_replay)
        monkeypatch.setattr(
            "app.core.extraction.graph_writer.GraphConfig.get_driver", _FakeDriverCM,
        )
        # get_session_factory 在 _run 内 lazy import → patch 源头
        monkeypatch.setattr("app.db.session.get_session_factory", lambda: sm)

        stats = await w._run()

        assert len(replayed) == 2  # eligible + stale_pending
        assert eligible in replayed and stale_pending in replayed
        assert completed_row not in replayed
        assert retry3 not in replayed
        assert drift not in replayed
        assert stats["failed_retryable"] == 1
        assert stats["pending_swept"] == 1
        assert stats["replayed"] == 2
        assert stats["completed"] == 2

    @pytest.mark.asyncio
    async def test_run_no_rows_returns_zeros(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = _FakeSession([_FakeScalarsResult([])])
        sm = _FakeSM(session)
        monkeypatch.setattr("app.db.session.get_session_factory", lambda: sm)
        stats = await w._run()
        assert stats["replayed"] == 0 and stats["completed"] == 0


# ── 幂等性: source_count max 语义（graph_writer 侧，Task 1 波序前置落地）─────
# 断言 merge_skill 查询含 max 语义，重复 merge 不累加（IC-06 不膨胀）。


class TestSourceCountMaxSemantics:
    @pytest.mark.asyncio
    async def test_merge_skill_query_uses_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.extraction.graph_writer import merge_skill

        captured: dict = {}

        class _FakeResult:
            async def single(self):
                return {"s": {"name": "Python"}}

        class _FakeSession:
            async def run(self, query: str, **kwargs) -> _FakeResult:
                captured["query"] = query
                return _FakeResult()

            async def __aenter__(self) -> _FakeSession:
                return self

            async def __aexit__(self, *args) -> bool:
                return False

        class _FakeDriver:
            def session(self) -> _FakeSession:
                return _FakeSession()

        # merge_skill 在函数体内 import EntityTrustScorer（from app.core.trust.entity_trust）
        with patch("app.core.trust.entity_trust.EntityTrustScorer") as mock_scorer:
            mock_scorer.return_value.score.return_value = 0.5
            await merge_skill(_FakeDriver(), "Python", {"source_count": 5}, canonical_id="c1")

        assert "max(coalesce(s.source_count, 0), $source_count)" in captured["query"]
        assert "coalesce(s.source_count, 0) + $source_count" not in captured["query"]
