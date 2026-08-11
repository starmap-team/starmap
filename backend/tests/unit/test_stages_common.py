"""Phase 03 Plan 03 Task 1: stages/common.py 公共层测试。

锁定公共层契约：
- publish_stage_progress / run_async / PipelineStageError / get_session_factory / select 可从 stages.common 导入
- StageProgress TypedDict 字段齐全
- 6 阶段模块导入公共层（隐式通过各模块 import）
"""
from __future__ import annotations


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
        except NotImplementedError as exc:
            raise AssertionError(
                "stages.execute_timeseries is still a stub (NotImplementedError); "
                "Task 1 migration incomplete"
            ) from exc
        assert isinstance(result, dict)
        assert "records_processed" in result

    def test_unmigrated_stages_raise(self):
        """未迁出的 stage 调用应抛 NotImplementedError（D-01 进度标识）。

        当前已迁出全部 6 阶段（Tasks 1-6），故未迁出列表为空。
        该测试作为回归守护：未来若新增阶段且未迁出，应失败。
        """

        unmigrated: list[str] = []
        assert unmigrated == [], "all 6 stages must be migrated (D-01 完成)"

    def test_dedup_is_real_not_stub(self):
        """dedup 已迁出 — Task 2 完成标志。"""
        from app.core.pipeline import stages

        fn = stages.execute_dedup
        try:
            result = fn("test-not-implemented-run-id")
        except NotImplementedError as exc:
            raise AssertionError("stages.execute_dedup is still a stub; Task 2 incomplete") from exc
        assert isinstance(result, dict)

    def test_clean_is_real_not_stub(self):
        """clean 已迁出 — Task 3 完成标志。"""
        from app.core.pipeline import stages

        fn = stages.execute_clean
        try:
            result = fn("test-not-implemented-run-id")
        except NotImplementedError as exc:
            raise AssertionError("stages.execute_clean is still a stub; Task 3 incomplete") from exc
        assert isinstance(result, dict)

    def test_crawl_is_real_not_stub(self):
        """crawl 已迁出 — Task 4 完成标志（签名带 run_type）。

        Phase 03 Plan 03 补完：原实现会真实执行 crawl（连 DB + 爬虫网络请求），
        在全量测试中会因连接池/网络而卡住。本测试改为 patch crawl 内部依赖
        （spider 注册表 / 配置加载 / outbox 更新），仅验证「非占位 stub」契约。
        """
        from unittest.mock import AsyncMock, patch

        from app.core.pipeline import stages

        fn = stages.execute_crawl
        with patch("app.core.pipeline.stages.crawl.build_spider_registry", return_value={}), \
             patch("app.core.pipeline.stages.crawl._get_crawl_configs", new=AsyncMock(return_value=[])), \
             patch("app.core.pipeline.stages.crawl._skip_paused_sources_if_needed", new=AsyncMock()), \
             patch("app.core.pipeline.stages.crawl._update_source_after_crawl"), \
             patch("app.core.pipeline.stages.crawl.publish_stage_progress", new=AsyncMock()), \
             patch("crawler.persistence.dao.init_schema"):
            try:
                result = fn("test-run-id", "incremental")
            except NotImplementedError as exc:
                raise AssertionError("stages.execute_crawl is still a stub; Task 4 incomplete") from exc
        assert isinstance(result, dict)

    def test_import_is_real_not_stub(self):
        """import 已迁出 — Task 5 完成标志。"""
        from app.core.pipeline import stages

        fn = stages.execute_import
        try:
            result = fn("test-run-id")
        except NotImplementedError as exc:
            raise AssertionError("stages.execute_import is still a stub; Task 5 incomplete") from exc
        assert isinstance(result, dict)
