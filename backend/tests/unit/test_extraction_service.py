"""Coverage boost: services/extraction_service.py — service 边界 re-export 防回归 (PLAN-013)。

路由层应经 service 边界访问抽取能力，而非直连 core。
锁定三个导出符号的来源，防止误改 import 导致分层被破坏。
"""

from __future__ import annotations

from app.services import extraction_service


def test_extract_from_jd_re_exports_core() -> None:
    import app.core.extraction.jd_extract as jd_extract

    assert extraction_service.extract_from_jd is jd_extract.extract_from_jd


def test_write_extraction_to_graph_re_exports_core() -> None:
    import app.core.extraction.graph_writer as graph_writer

    assert extraction_service.write_extraction_to_graph is graph_writer.write_extraction_to_graph


def test_tracker_re_exports_cost_tracker() -> None:
    from app.core.llm.cost_tracker import tracker as cost_tracker

    assert extraction_service.tracker is cost_tracker


def test_all_lists_exactly_the_public_surface() -> None:
    assert set(extraction_service.__all__) == {
        "extract_from_jd",
        "write_extraction_to_graph",
        "tracker",
    }
