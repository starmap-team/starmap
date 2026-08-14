"""Evolution orchestrator unit tests — month iterator + summary shape.

The full ``run_evolution_pipeline`` touches the DB, so we test only the
pure helpers here. Integration is covered by stage 5 E2E.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.evolution.orchestrator import _diff_and_persist, _month_iter
from app.models.evolution_models import EvolutionSnapshot


class TestMonthIter:
    def test_returns_chronological_order(self):
        months = _month_iter(3, datetime(2026, 7, 24, tzinfo=UTC))
        assert [m.strftime("%Y-%m") for m in months] == [
            "2026-04", "2026-05", "2026-06", "2026-07",
        ]

    def test_handles_year_boundary(self):
        months = _month_iter(2, datetime(2026, 2, 15, tzinfo=UTC))
        assert [m.strftime("%Y-%m") for m in months] == ["2025-12", "2026-01", "2026-02"]

    def test_includes_current_month_as_last(self):
        months = _month_iter(0, datetime(2026, 7, 4, tzinfo=UTC))
        assert len(months) == 1
        assert months[0] == datetime(2026, 7, 1, tzinfo=UTC)

    def test_naive_input_treated_as_utc(self):
        months = _month_iter(1, datetime(2026, 7, 4))
        assert all(m.tzinfo == UTC for m in months)


class TestPipelineCallable:
    def test_run_evolution_pipeline_importable_and_callable(self):
        from app.core.evolution.orchestrator import run_evolution_pipeline
        assert callable(run_evolution_pipeline)

    def test_process_single_position_importable(self):
        from app.core.evolution.orchestrator import _process_single_position
        assert callable(_process_single_position)

    def test_diff_and_persist_importable(self):
        from app.core.evolution.orchestrator import _diff_and_persist
        assert callable(_diff_and_persist)


class TestEvolutionPipelineError:
    def test_importable(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        assert EvolutionPipelineError is not None

    def test_is_exception_subclass(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        assert issubclass(EvolutionPipelineError, Exception)

    def test_constructor_with_message(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        err = EvolutionPipelineError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert err.step == ""

    def test_constructor_with_step(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        err = EvolutionPipelineError("snapshot failed", step="snapshot")
        assert err.step == "snapshot"
        assert "snapshot failed" in str(err)

    def test_caught_as_exception(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        try:
            raise EvolutionPipelineError("test error", step="diff")
        except EvolutionPipelineError as e:
            assert e.step == "diff"
            assert e.message == "test error"


def _snapshot(position: str, required: list[str], preferred: list[str] | None = None, source_count: int = 5) -> EvolutionSnapshot:
    return EvolutionSnapshot(
        position_name=position,
        snapshot_date=datetime(2026, 7, 1, tzinfo=UTC),
        required_skills=[{"name": s, "category": "general", "mention_count": source_count} for s in required],
        preferred_skills=[{"name": s, "category": "general", "mention_count": source_count} for s in (preferred or [])],
        source_count=source_count,
    )


class TestDiffAndPersist:
    def _make_session(self):
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        return session

    @pytest.mark.asyncio
    async def test_write_back_failure_does_not_block(self):
        """D-06: write-back raising → warning appended, _diff_and_persist still returns."""
        from app.core.evolution.diff_engine import DiffEngine
        from app.core.evolution.trust_scorer import TrustScorer

        old = _snapshot("后端工程师", required=["Python"], preferred=[])
        new = _snapshot("后端工程师", required=["Python", "FastAPI"], preferred=[])
        session = self._make_session()
        warnings: list[str] = []

        with patch(
            "app.core.evolution.orchestrator.write_back_changelog_row",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            written, edges = await _diff_and_persist(
                session, DiffEngine(), TrustScorer(), old, new, warnings
            )

        assert written >= 1  # changelog rows were still written
        assert edges == []  # nothing projected since write-back failed
        assert any("write-back loop failed" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_evidence_json_has_factors(self):
        """D-09: evidence_json includes factors {source, stability, type}."""
        from app.core.evolution.diff_engine import DiffEngine
        from app.core.evolution.trust_scorer import TrustScorer

        old = _snapshot("后端工程师", required=["Python"], preferred=[])
        new = _snapshot("后端工程师", required=["Python", "FastAPI"], preferred=[])
        session = self._make_session()
        warnings: list[str] = []

        with patch(
            "app.core.evolution.orchestrator.write_back_changelog_row",
            new=AsyncMock(return_value=None),
        ):
            await _diff_and_persist(session, DiffEngine(), TrustScorer(), old, new, warnings)

        added = list(session.add.call_args_list)
        assert added, "expected changelog rows to be added"
        # Each add call carries an EvolutionChangelog with evidence_json.factors
        row = added[0].args[0]
        factors = row.evidence_json["factors"]
        assert set(factors) == {"source", "stability", "type"}
        assert 0.0 <= factors["source"] <= 1.0
        assert 0.0 <= factors["stability"] <= 1.0
        assert factors["type"] in (1.0, 0.9, 0.7, 0.65, 0.5, 0.4)


class TestRunEvolutionPipelineSummary:
    @staticmethod
    def _make_factory():
        """A fake session factory: session supports ``async with`` + ``async with session.begin()``."""
        session = AsyncMock()
        begin_cm = MagicMock()
        begin_cm.__aenter__ = AsyncMock(return_value=session)
        begin_cm.__aexit__ = AsyncMock(return_value=False)
        session.begin = MagicMock(return_value=begin_cm)

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=cm)
        return factory

    @pytest.mark.asyncio
    async def test_summary_contains_consistency(self):
        """D-07: summary carries the consistency dict even when check succeeds."""
        from app.core.evolution.orchestrator import run_evolution_pipeline

        factory = self._make_factory()

        with patch("app.core.evolution.orchestrator.get_session_factory", return_value=factory), patch(
            "app.core.evolution.orchestrator.list_positions_with_records",
            new=AsyncMock(return_value=["后端工程师"]),
        ), patch(
            "app.core.evolution.orchestrator._process_single_position",
            new=AsyncMock(return_value=(1, 2, [("pos", "skill", "required", 0.9)])),
        ), patch(
            "app.core.evolution.orchestrator.project_edges_to_neo4j",
            new=AsyncMock(return_value=1),
        ), patch(
            "app.core.evolution.orchestrator.refresh_skill_timeseries",
            new=AsyncMock(return_value={}),
        ), patch(
            "app.core.evolution.orchestrator.PathRecommender",
        ) as mock_path:
            mock_path.return_value.recommend = AsyncMock(return_value=[])
            consistency = {
                "status": "ok", "pg_only": [], "neo4j_only": [],
                "attribute_mismatches": [], "checked_at": "2026-08-10T00:00:00Z",
            }
            with patch(
                "app.core.evolution.orchestrator.check_pg_neo4j_consistency",
                new=AsyncMock(return_value=consistency),
            ):
                summary = await run_evolution_pipeline(months_back=1)

        assert "consistency" in summary
        assert summary["consistency"]["status"] == "ok"
        assert summary["graph_projected_edges"] == 1
        assert summary["warnings"] == []
        assert summary["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_graph_projection_failure_only_warns(self):
        """D-06: graph_projection raising → warning appended, pipeline continues."""
        from app.core.evolution.orchestrator import run_evolution_pipeline

        factory = self._make_factory()

        with patch("app.core.evolution.orchestrator.get_session_factory", return_value=factory), patch(
            "app.core.evolution.orchestrator.list_positions_with_records",
            new=AsyncMock(return_value=["后端工程师"]),
        ), patch(
            "app.core.evolution.orchestrator._process_single_position",
            new=AsyncMock(return_value=(1, 2, [("pos", "skill", "required", 0.9)])),
        ), patch(
            "app.core.evolution.orchestrator.project_edges_to_neo4j",
            new=AsyncMock(side_effect=RuntimeError("neo4j down")),
        ), patch(
            "app.core.evolution.orchestrator.refresh_skill_timeseries",
            new=AsyncMock(return_value={}),
        ), patch(
            "app.core.evolution.orchestrator.PathRecommender",
        ) as mock_path:
            mock_path.return_value.recommend = AsyncMock(return_value=[])
            with patch(
                "app.core.evolution.orchestrator.check_pg_neo4j_consistency",
                new=AsyncMock(return_value={"status": "error", "error": "n/a"}),
            ):
                summary = await run_evolution_pipeline(months_back=1)

        assert summary["graph_projected_edges"] == 0
        assert any("graph_projection" in w for w in summary["warnings"])

    @pytest.mark.asyncio
    async def test_consistency_check_failure_only_warns(self):
        """D-07: consistency check raising → warning + summary error dict, no abort."""
        from app.core.evolution.orchestrator import run_evolution_pipeline

        factory = self._make_factory()

        with patch("app.core.evolution.orchestrator.get_session_factory", return_value=factory), patch(
            "app.core.evolution.orchestrator.list_positions_with_records",
            new=AsyncMock(return_value=[]),
        ):
            summary = await run_evolution_pipeline(months_back=1)

        # No positions → early return before consistency is mounted; warnings set.
        assert summary["positions_found"] == 0
        assert "no positions" in summary["warnings"][0]

    @pytest.mark.asyncio
    async def test_consistency_mismatch_downgraded_to_warning(self):
        """W5: status=='mismatch' 的 consistency 报告追加进 summary['warnings']。"""
        from app.core.evolution.orchestrator import run_evolution_pipeline

        factory = self._make_factory()

        with patch("app.core.evolution.orchestrator.get_session_factory", return_value=factory), patch(
            "app.core.evolution.orchestrator.list_positions_with_records",
            new=AsyncMock(return_value=["后端工程师"]),
        ), patch(
            "app.core.evolution.orchestrator._process_single_position",
            new=AsyncMock(return_value=(1, 0, [])),
        ), patch(
            "app.core.evolution.orchestrator.project_edges_to_neo4j",
            new=AsyncMock(return_value=0),
        ), patch(
            "app.core.evolution.orchestrator.refresh_skill_timeseries",
            new=AsyncMock(return_value={}),
        ), patch(
            "app.core.evolution.orchestrator.PathRecommender",
        ) as mock_path:
            mock_path.return_value.recommend = AsyncMock(return_value=[])
            consistency = {
                "status": "mismatch",
                "pg_only": [{"position_id": "p", "skill_id": "s", "requirement_type": "required"}],
                "neo4j_only": [],
                "attribute_mismatches": [],
                "checked_at": "2026-08-10T00:00:00Z",
            }
            with patch(
                "app.core.evolution.orchestrator.check_pg_neo4j_consistency",
                new=AsyncMock(return_value=consistency),
            ):
                summary = await run_evolution_pipeline(months_back=1)

        assert summary["consistency"]["status"] == "mismatch"
        assert any("consistency" in w and "mismatch" in w for w in summary["warnings"])


    @pytest.mark.asyncio
    async def test_same_snapshot_pair_change_not_duplicated(self):
        """去重 (2026-08-14): 同一快照对的同一变更只记录一次，不重复 INSERT。

        根因: 每轮管线 run 重复 diff 同一历史快照对 → 相同 changelog 累积
        （曾达 15,356 行 vs 56 真实键）。
        """
        from app.core.evolution.diff_engine import DiffEngine
        from app.core.evolution.trust_scorer import TrustScorer

        old = _snapshot("后端工程师", required=["Python"], preferred=[])
        new = _snapshot("后端工程师", required=["Python", "FastAPI"], preferred=[])

        # execute 第一次调用返回已存在的 changelog id → 去重命中，跳过 add
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value="existing-id")))

        warnings: list[str] = []
        written, edges = await _diff_and_persist(
            session, DiffEngine(), TrustScorer(), old, new, warnings
        )
        assert written == 0
        assert session.add.call_count == 0
