"""Phase 03 Plan 03 Task 4: stages/crawl.py 阶段测试。

锁定 crawl 阶段行为契约（结构 + 子步骤事件）。
"""
from __future__ import annotations

from pathlib import Path


def _crawl_source() -> str:
    base = Path(__file__).resolve().parents[2] / "app" / "core" / "pipeline" / "stages" / "crawl.py"
    return base.read_text(encoding="utf-8")


class TestExecuteCrawlStructure:
    """execute_crawl 结构契约。"""

    def test_function_exists_in_stages_crawl(self):
        from app.core.pipeline.stages import crawl

        assert hasattr(crawl, "execute_crawl")
        assert callable(crawl.execute_crawl)

    def test_signature_takes_run_type(self):
        """execute_crawl(run_id, run_type) 必须保留 run_type 参数。"""
        import inspect

        from app.core.pipeline.stages import crawl

        sig = inspect.signature(crawl.execute_crawl)
        params = list(sig.parameters.keys())
        assert params == ["run_id", "run_type"], f"signature changed: {params}"

    def test_sub_step_events_in_source(self):
        """每数据源/平台发 sub_step=crawl:<source_name> 事件（D-15）。"""
        source = _crawl_source()
        assert 'sub_step=f"crawl:' in source, (
            "execute_crawl must emit sub_step events for each data source (D-15)"
        )
        # 至少出现 2 处（skip path + start path）
        occurrences = source.count('sub_step=f"crawl:')
        assert occurrences >= 2, (
            f"expected ≥2 sub_step occurrences (skip + start paths), got {occurrences}"
        )


class TestExecuteCrawlModuleSurface:
    """stages.execute_crawl 必须是真实现（Task 4 完成标志）。"""

    def test_crawl_is_real_not_stub(self):
        from app.core.pipeline import stages

        fn = stages.execute_crawl
        try:
            result = fn("test-run-id", "incremental")
        except NotImplementedError as exc:
            raise AssertionError("stages.execute_crawl is still a stub; Task 4 incomplete") from exc
        assert isinstance(result, dict)
