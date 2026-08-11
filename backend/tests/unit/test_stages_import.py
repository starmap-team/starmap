"""Phase 03 Plan 03 Task 5: stages/import_.py 阶段测试 + SSOT 可观测化测试。

锁定 import 阶段行为契约（D-15 三子步骤事件 + D-06 一致性告警调用）。
"""
from __future__ import annotations

from pathlib import Path


def _import_source() -> str:
    base = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline" / "stages" / "import_.py"
    return base.read_text(encoding="utf-8")


class TestExecuteImportSubSteps:
    """D-15: import 阶段发 3 子步骤事件（extract/normalize/persist）。"""

    def test_sub_step_extract_in_source(self):
        source = _import_source()
        assert 'sub_step="extract"' in source, "import stage must emit sub_step='extract'"

    def test_sub_step_normalize_in_source(self):
        source = _import_source()
        assert 'sub_step="normalize"' in source, "import stage must emit sub_step='normalize'"

    def test_sub_step_persist_in_source(self):
        source = _import_source()
        assert 'sub_step="persist"' in source, "import stage must emit sub_step='persist'"

    def test_all_three_sub_steps_present(self):
        """全部 3 子步骤事件存在。"""
        source = _import_source()
        for step in ("extract", "normalize", "persist"):
            assert f'sub_step="{step}"' in source, f"missing sub_step={step}"


class TestImportModuleSurface:
    """stages.execute_import 必须是真实现（Task 5 完成标志）。"""

    def test_import_is_real_not_stub(self):
        from app.core.pipeline import stages

        fn = stages.execute_import
        try:
            result = fn("test-run-id")
        except NotImplementedError as exc:
            raise AssertionError("stages.execute_import is still a stub; Task 5 incomplete") from exc
        assert isinstance(result, dict)


class TestConsistencyService:
    """D-06: pipeline_consistency 服务提供仅日志告警（不改数据）。"""

    def test_consistency_module_importable(self):
        from app.services import pipeline_consistency

        assert hasattr(pipeline_consistency, "check_pg_neo4j_consistency")
        assert callable(pipeline_consistency.check_pg_neo4j_consistency)

    def test_consistency_does_not_block_on_failure(self):
        """失败时返回 dict 不抛错（不阻断流水线）。"""
        import asyncio

        from app.services.pipeline_consistency import check_pg_neo4j_consistency

        result = asyncio.run(check_pg_neo4j_consistency("test-run-id"))
        assert isinstance(result, dict)
        assert "severity" in result
        assert "alerted" in result
