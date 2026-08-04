"""Phase 3 Plan 02: DAG 串行调度 + JdStatus.cleaned 状态机测试。"""
from __future__ import annotations

import pytest

from app.core.pipeline.orchestrator import (
    STAGE_DEPS,
    StageName,
    get_ready_stages,
)


class TestDagSerialDeps:
    """验证 STAGE_DEPS 串行化：clean 依赖 dedup，import 依赖 clean。"""

    def test_clean_depends_on_dedup_not_crawl(self):
        assert STAGE_DEPS[StageName.CLEAN.value] == [StageName.DEDUP.value]

    def test_import_depends_on_clean_only(self):
        assert STAGE_DEPS[StageName.IMPORT.value] == [StageName.CLEAN.value]

    def test_clean_not_ready_when_dedup_running(self):
        """clean 在 dedup 未完成时不应 ready。"""
        stages = [
            {"name": "crawl", "status": "completed"},
            {"name": "dedup", "status": "running"},
            {"name": "clean", "status": "pending"},
        ]
        ready = get_ready_stages(stages)
        assert "clean" not in ready

    def test_clean_ready_after_dedup_completed(self):
        """clean 在 dedup 完成后应 ready。"""
        stages = [
            {"name": "crawl", "status": "completed"},
            {"name": "dedup", "status": "completed"},
            {"name": "clean", "status": "pending"},
        ]
        ready = get_ready_stages(stages)
        assert "clean" in ready

    def test_import_not_ready_when_clean_running(self):
        """import 在 clean 未完成时不应 ready。"""
        stages = [
            {"name": "crawl", "status": "completed"},
            {"name": "dedup", "status": "completed"},
            {"name": "clean", "status": "running"},
            {"name": "import", "status": "pending"},
        ]
        ready = get_ready_stages(stages)
        assert "import" not in ready

    def test_import_ready_after_clean_completed(self):
        """import 在 clean 完成后应 ready。"""
        stages = [
            {"name": "crawl", "status": "completed"},
            {"name": "dedup", "status": "completed"},
            {"name": "clean", "status": "completed"},
            {"name": "import", "status": "pending"},
        ]
        ready = get_ready_stages(stages)
        assert "import" in ready

    def test_full_serial_chain(self):
        """完整串行链：crawl→dedup→clean→import→graph_sync。"""
        stages = [
            {"name": "crawl", "status": "completed"},
            {"name": "dedup", "status": "completed"},
            {"name": "clean", "status": "completed"},
            {"name": "import", "status": "completed"},
            {"name": "graph_sync", "status": "pending"},
        ]
        ready = get_ready_stages(stages)
        assert ready == ["graph_sync"]

    def test_dedup_and_clean_not_parallel(self):
        """dedup 和 clean 不应同时 ready（串行非并行）。"""
        stages = [
            {"name": "crawl", "status": "completed"},
            {"name": "dedup", "status": "pending"},
            {"name": "clean", "status": "pending"},
        ]
        ready = get_ready_stages(stages)
        assert "dedup" in ready
        assert "clean" not in ready  # clean 等 dedup，不能并行


class TestJdStatusCleaned:
    """验证 JdStatus 枚举含 cleaned 值。"""

    def test_cleaned_enum_exists(self):
        try:
            from crawler.persistence.models import JdStatus
        except ImportError:
            pytest.skip("crawler package not on path (run in Docker or add to sys.path)")
        assert hasattr(JdStatus, "cleaned")
        assert JdStatus.cleaned.value == "cleaned"

    def test_all_statuses(self):
        try:
            from crawler.persistence.models import JdStatus
        except ImportError:
            pytest.skip("crawler package not on path (run in Docker or add to sys.path)")
        expected = {"raw", "cleaned", "extracted", "duplicate", "failed"}
        actual = {s.value for s in JdStatus}
        assert actual == expected
