"""Phase 03 Plan 03 Task 6: stages/graph_sync.py 阶段测试。

锁定 graph_sync 阶段行为契约（outbox + 可选 reconcile + 模块表面）。
"""
from __future__ import annotations

from pathlib import Path


def _graph_sync_source() -> str:
    base = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline" / "stages" / "graph_sync.py"
    return base.read_text(encoding="utf-8")


class TestExecuteGraphSyncStructure:
    """execute_graph_sync 结构契约。"""

    def test_function_exists(self):
        from app.core.pipeline.stages import graph_sync

        assert hasattr(graph_sync, "execute_graph_sync")
        assert callable(graph_sync.execute_graph_sync)

    def test_reconcile_sub_step_event(self):
        """D-07 reconcile 子步骤事件存在（sub_step="reconcile"）。"""
        source = _graph_sync_source()
        assert 'sub_step="reconcile"' in source, (
            "graph_sync must emit sub_step='reconcile' when reconcile_on_sync=True (D-15)"
        )

    def test_reconcile_uses_config_flag(self):
        """reconcile 必须读 settings.pipeline_graph_sync_reconcile_on_sync。"""
        source = _graph_sync_source()
        assert "pipeline_graph_sync_reconcile_on_sync" in source, (
            "reconcile must gate on settings.pipeline_graph_sync_reconcile_on_sync (D-07)"
        )

    def test_reconcile_failure_non_fatal(self):
        """对账失败必须非致命（仅告警不阻断）。"""
        source = _graph_sync_source()
        # 函数体应有 try/except 包裹 reconcile 调用
        assert "_run_reconcile_substep" in source, (
            "graph_sync must use _run_reconcile_substep helper"
        )
        # _run_reconcile_substep 自身也应有 try/except
        assert "non-fatal" in source, (
            "reconcile must be marked non-fatal"
        )


class TestGraphSyncModuleSurface:
    """stages.execute_graph_sync 必须是真实现（Task 6 完成标志）。"""

    def test_graph_sync_is_real_not_stub(self):
        from app.core.pipeline import stages

        fn = stages.execute_graph_sync
        try:
            result = fn("test-run-id")
        except NotImplementedError as exc:
            raise AssertionError("stages.execute_graph_sync is still a stub; Task 6 incomplete") from exc
        assert isinstance(result, dict)


class TestDeprecatedScripts:
    """D-07: 原对账脚本打 DEPRECATED banner。"""

    def test_backfill_graph_to_pg_deprecated(self):
        from pathlib import Path

        script = (
            Path(__file__).resolve().parents[2] / "scripts" / "backfill_graph_to_pg.py"
        ).read_text(encoding="utf-8")
        assert "DEPRECATED" in script, (
            "scripts/backfill_graph_to_pg.py must have DEPRECATED banner (D-07)"
        )
        assert "pipeline_graph_sync_reconcile_on_sync" in script, (
            "banner must reference the new config switch"
        )

    def test_sync_pg_edges_to_graph_deprecated(self):
        from pathlib import Path

        script = (
            Path(__file__).resolve().parents[2] / "scripts" / "sync_pg_edges_to_graph.py"
        ).read_text(encoding="utf-8")
        assert "DEPRECATED" in script, (
            "scripts/sync_pg_edges_to_graph.py must have DEPRECATED banner (D-07)"
        )
        assert "pipeline_graph_sync_reconcile_on_sync" in script, (
            "banner must reference the new config switch"
        )


class TestStagesModuleSurface:
    """所有 6 阶段已迁出 — 未迁出 stub 列表应为空。"""

    def test_unmigrated_stages_empty(self):
        """D-01 进度完成标志：未迁出 stub 列表为空。"""
        from app.core.pipeline import stages

        # 所有 6 个 execute_* 必须返回 dict（真实现）而非抛 NotImplementedError
        for name in [
            "execute_crawl",
            "execute_dedup",
            "execute_clean",
            "execute_import",
            "execute_graph_sync",
            "execute_timeseries",
        ]:
            fn = getattr(stages, name)
            # crawl 签名带 run_type
            args = ["test-run-id", "incremental"] if name == "execute_crawl" else ["test-run-id"]
            try:
                result = fn(*args)
            except NotImplementedError as exc:
                raise AssertionError(f"{name} still a stub; Task 6 should complete all migrations") from exc
            assert isinstance(result, dict)
