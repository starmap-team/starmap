"""Phase 03 Plan 03 Task 1: stages/common.py 公共层测试。

锁定公共层契约：
- publish_stage_progress / run_async / PipelineStageError / get_session_factory / select 可从 stages.common 导入
- StageProgress TypedDict 字段齐全
- 6 阶段模块导入公共层（隐式通过各模块 import）
"""
from __future__ import annotations

import pytest


class TestStagesCommonImports:
    """公共层符号导出验证。"""

    def test_public_symbols_importable(self):
        from app.core.pipeline.stages import common as c

        for name in [
            "PipelineStageError",
            "StageProgress",
            "get_session_factory",
            "logger",
            "publish_stage_progress",
            "run_async",
            "select",
        ]:
            assert hasattr(c, name), f"stages.common missing {name}"

    def test_stage_progress_typed_dict(self):
        """StageProgress 必填字段（TypedDict total=False, 存在即合规）。"""
        from app.core.pipeline.stages.common import StageProgress

        # 验证字段定义存在
        annotations = StageProgress.__annotations__
        for field in [
            "run_id",
            "stage",
            "status",
            "progress",
            "records_processed",
            "current_activity",
            "elapsed_ms",
            "sub_step",
        ]:
            assert field in annotations, f"StageProgress missing {field}"

    def test_publish_stage_progress_sub_step_field(self):
        """publish_stage_progress 必须支持 sub_step 参数（D-15）。"""
        import inspect

        from app.core.pipeline.stages.common import publish_stage_progress

        sig = inspect.signature(publish_stage_progress)
        assert "sub_step" in sig.parameters, "publish_stage_progress must accept sub_step"


class TestStagesModuleSurface:
    """stages 包必须重导出 6 个 stage execute_* 函数（占位或真实）。"""

    def test_all_six_stages_exported(self):
        from app.core.pipeline import stages

        for name in [
            "execute_crawl",
            "execute_dedup",
            "execute_clean",
            "execute_import",
            "execute_graph_sync",
            "execute_timeseries",
        ]:
            assert hasattr(stages, name), f"stages missing {name}"
            assert callable(getattr(stages, name)), f"stages.{name} not callable"

    def test_timeseries_is_real_not_stub(self):
        """timeseries 已迁出 — 不应是 _not_migrated 占位（Task 1 完成标志）。"""
        from app.core.pipeline import stages

        fn = stages.execute_timeseries
        # 占位 stub 通过抛 NotImplementedError 实现 — 真实现不会抛
        try:
            # 用 invalid run_id 调用：真实现返回 dict（即使 records_processed=0），不抛
            result = fn("test-not-implemented-run-id")
        except NotImplementedError:
            raise AssertionError(
                "stages.execute_timeseries is still a stub (NotImplementedError); "
                "Task 1 migration incomplete"
            )
        assert isinstance(result, dict)
        assert "records_processed" in result

    def test_unmigrated_stages_raise(self):
        """未迁出的 stage 调用应抛 NotImplementedError（D-01 进度标识）。"""
        from app.core.pipeline import stages

        for name in ["execute_crawl", "execute_dedup", "execute_clean", "execute_import", "execute_graph_sync"]:
            fn = getattr(stages, name)
            with pytest.raises(NotImplementedError):
                fn("test-run-id")
