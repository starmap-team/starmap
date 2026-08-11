"""Phase 02 D-03: graph_sync 阶段末 Position PG↔Neo4j 一致性校验单元测试。

沿 M3 D-06「一致性告警仅观察不阻断」口径：
- 计数一致 → 不写 outbox
- Neo4j 多/少节点 → 写 `position_pg_neo4j_drift` 告警条目，且不抛异常
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.pipeline.stages.graph_sync import (
    POSITION_DRIFT_ALERT_TYPE,
    POSITION_DRIFT_OUTBOX_STATUS,
    _check_position_consistency,
)


class _RecordingSession:
    """AsyncSession stand-in that records objects added via session.add()."""

    def __init__(self, pg_count: int, added: list[Any]) -> None:
        self._pg_count = pg_count
        self._added = added

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        result = AsyncMock()
        result.scalar = lambda: self._pg_count
        return result

    def add(self, obj: Any) -> None:
        self._added.append(obj)

    def begin(self) -> Any:
        @asynccontextmanager
        async def _cm() -> Any:
            yield None

        return _cm()


def _make_session_factory(pg_count: int, added: list[Any]) -> Any:
    def _factory() -> Any:
        @asynccontextmanager
        async def _cm() -> Any:
            yield _RecordingSession(pg_count, added)

        return _cm()

    return _factory


def _make_driver(total: int, with_cid: int | None = None, *, raise_on_run: bool = False) -> Any:
    with_cid = total if with_cid is None else with_cid

    class _Session:
        async def run(self, _query: str, **_params: Any) -> Any:
            if raise_on_run:
                raise RuntimeError("neo4j unavailable")
            result = AsyncMock()
            result.single = AsyncMock(return_value={"total": total, "with_cid": with_cid})
            return result

    class _Driver:
        def session(self) -> Any:
            @asynccontextmanager
            async def _cm() -> Any:
                yield _Session()

            return _cm()

    return _Driver()


RUN_ID = str(uuid.uuid4())


class TestPositionConsistencyCheck:
    @pytest.mark.asyncio
    async def test_counts_aligned_no_alert(self) -> None:
        """PG 与 Neo4j 计数一致 → diff=0，不写 outbox 告警。"""
        added: list[Any] = []
        diff = await _check_position_consistency(
            _make_session_factory(212, added), _make_driver(212), RUN_ID,
        )
        assert diff == 0
        assert added == []

    @pytest.mark.asyncio
    async def test_neo4j_has_extra_node_alerts(self) -> None:
        """Neo4j 多 1 节点 → diff=+1，写入 position_pg_neo4j_drift 告警。"""
        added: list[Any] = []
        diff = await _check_position_consistency(
            _make_session_factory(212, added), _make_driver(213, with_cid=212), RUN_ID,
        )
        assert diff == 1
        assert len(added) == 1
        record = added[0]
        assert record.status == POSITION_DRIFT_OUTBOX_STATUS
        assert record.error.startswith(POSITION_DRIFT_ALERT_TYPE)
        assert "pg=212" in record.error
        assert "neo4j_total=213" in record.error
        assert "legacy_without_canonical_id=1" in record.error

    @pytest.mark.asyncio
    async def test_neo4j_missing_node_alerts(self) -> None:
        """Neo4j 少 1 节点 → diff=-1，同样写入告警条目。"""
        added: list[Any] = []
        diff = await _check_position_consistency(
            _make_session_factory(212, added), _make_driver(211), RUN_ID,
        )
        assert diff == -1
        assert len(added) == 1
        assert POSITION_DRIFT_ALERT_TYPE in added[0].error
        assert "diff=-1" in added[0].error

    @pytest.mark.asyncio
    async def test_driver_none_is_noop(self) -> None:
        """Neo4j 不可用 → 返回 0 且不写 outbox（不阻断）。"""
        added: list[Any] = []
        diff = await _check_position_consistency(_make_session_factory(212, added), None, RUN_ID)
        assert diff == 0
        assert added == []

    @pytest.mark.asyncio
    async def test_query_failure_is_non_blocking(self) -> None:
        """取数抛异常 → 吞掉并返回 0，绝不向上抛（M3 D-06 仅观察不阻断）。"""
        added: list[Any] = []
        diff = await _check_position_consistency(
            _make_session_factory(212, added), _make_driver(0, raise_on_run=True), RUN_ID,
        )
        assert diff == 0
        assert added == []

    @pytest.mark.asyncio
    async def test_outbox_write_failure_is_non_blocking(self) -> None:
        """告警落库失败 → 仍返回 diff，不抛异常。"""

        class _ExplodingFactory:
            def __call__(self) -> Any:
                @asynccontextmanager
                async def _cm() -> Any:
                    yield _ExplodingSession()

                return _cm()

        class _ExplodingSession:
            async def execute(self, *_a: Any, **_k: Any) -> Any:
                result = AsyncMock()
                result.scalar = lambda: 212
                return result

            def add(self, _obj: Any) -> None:
                raise RuntimeError("db down")

            def begin(self) -> Any:
                @asynccontextmanager
                async def _cm() -> Any:
                    yield None

                return _cm()

        diff = await _check_position_consistency(_ExplodingFactory(), _make_driver(218, 212), RUN_ID)
        assert diff == 6


class TestGraphSyncStageWiring:
    """一致性校验必须默认接在 graph_sync 阶段末（不依赖 reconcile_on_sync 开关）。"""

    def test_stage_calls_consistency_substep(self) -> None:
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "app" / "core" / "pipeline" / "stages" / "graph_sync.py"
        ).read_text(encoding="utf-8")
        assert "_run_position_consistency_substep(run_id)" in source
        # 必须在 reconcile 的 if 分支之外（默认开启）
        reconcile_idx = source.index("if settings.pipeline_graph_sync_reconcile_on_sync:")
        call_idx = source.index("_run_position_consistency_substep(run_id)")
        indent_line = source[:call_idx].rsplit("\n", 1)[-1]
        assert call_idx > reconcile_idx
        assert indent_line == " " * 8, "consistency check must not be nested under reconcile flag"
