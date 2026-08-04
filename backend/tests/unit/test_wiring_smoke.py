"""Wiring smoke checks — verify imports + endpoint registration without DB or network.

Confirms (in-process) that the changes from this branch actually load and
register correctly, which is the minimum we can guarantee without a live backend.
"""
from __future__ import annotations


def test_cost_tracker_singleton_exports_correct_price() -> None:
    from app.api.v1.extract import tracker as extract_tracker
    from app.core.llm.cost_tracker import PRICE_CNY_PER_1M, tracker

    assert PRICE_CNY_PER_1M == 1.0
    assert tracker is extract_tracker, "extract.py must import the same singleton"


def test_extract_router_has_cost_summary_endpoint() -> None:
    from app.api.v1.extract import router

    paths = {getattr(r, "path", "") for r in router.routes}
    assert any(p.endswith("/cost-summary") for p in paths), paths


def test_outbox_helper_accepts_none_run_id() -> None:
    """Regression for H1: _create_outbox_record now allows run_id=None."""
    import inspect

    from app.core.pipeline import executor

    sig = inspect.signature(executor._create_outbox_record)
    run_id_param = sig.parameters["run_id"]
    # "UUID | None" annotation must allow None
    assert "None" in str(run_id_param.annotation), (
        f"run_id should accept None, got {run_id_param.annotation}"
    )
    extraction_param = sig.parameters.get("extraction_ids")
    assert extraction_param is not None, "extraction_ids parameter missing"
    assert extraction_param.default is not inspect.Parameter.empty, (
        "extraction_ids must have default so pipeline callers don't break"
    )


def test_graph_write_outbox_model_run_id_is_nullable() -> None:
    from app.models.pipeline_models import GraphWriteOutbox

    col = GraphWriteOutbox.__table__.columns["run_id"]
    assert col.nullable is True, "H1 fix: run_id must be nullable for ad-hoc extractions"


def test_llm_client_does_not_break_pipeline_callers() -> None:
    """Regression for circular-import avoidance: importing llm_client is safe."""
    from app.core.extraction import llm_client  # noqa: F401
    from app.core.extraction.llm_client import call_llm_with_fallback  # noqa: F401


def test_stage3_services_run_batch_extract_jd_loads_cleanly() -> None:
    import inspect

    from app.tasks.stage3_services import run_batch_extract_jd  # noqa: F401

    assert inspect.iscoroutinefunction(run_batch_extract_jd)
