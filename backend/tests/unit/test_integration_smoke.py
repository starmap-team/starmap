"""Integration smoke tests — exercise wired behavior through public APIs.

Ponytail: uses TestClient + AsyncMock to drive the FastAPI app and the LLM call
chain end-to-end without spinning up Postgres/Neo4j/Docker. Catches the bugs
unit tests can't: wrong routes, missing middleware, broken wiring, atomicity.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

# ── FastAPI endpoint contract ───────────────────────────────────────────────


def test_cost_summary_endpoint_round_trip() -> None:
    """GET /api/v1/extract/cost-summary returns the tracker summary shape."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.extract import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        resp = client.get("/extract/cost-summary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["price_cny_per_1m_tokens"] == 1.0
    assert "total_cost_cny" in body
    assert "total_tokens" in body
    assert "by_model" in body


def test_cost_summary_reflects_recorded_calls() -> None:
    """If tracker accumulates state from earlier, summary exposes it."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.extract import router
    from app.core.llm import cost_tracker

    cost_tracker.tracker._by_model.clear()

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        cost_tracker.tracker.record(model="test-mimo", prompt="a" * 400, content="b" * 200)
        resp = client.get("/extract/cost-summary")

    assert resp.status_code == 200
    body = resp.json()
    assert "test-mimo" in body["by_model"], body
    assert body["by_model"]["test-mimo"]["input_tokens"] == 100
    assert body["by_model"]["test-mimo"]["output_tokens"] == 50


# ── Outbox wiring: full stage3 codepath ────────────────────────────────────


def test_manual_extraction_writes_outbox_with_nullable_run_id() -> None:
    """End-to-end codepath: persist → outbox(pending) → graph → outbox(completed).

    Locks the H1 invariant: run_id=None, extraction_ids populated, no UUID-nil
    sentinel. Uses runner-side persistence stub that injects a stable record id
    we can verify in the captured outbox call.
    """
    from app.core.pipeline import executor
    from app.tasks import stage3_services

    captured: dict = {}
    captured_id = "11111111-2222-3333-4444-555555555555"

    async def fake_create(sf, outbox_id, run_id, extraction_ids=None):  # noqa: ANN001
        captured["run_id"] = run_id
        captured["extraction_ids"] = extraction_ids

    async def fake_complete(sf, outbox_id, triples):  # noqa: ANN001
        captured["completed"] = triples

    async def fake_fail(sf, outbox_id, err):  # noqa: ANN001
        captured["fail"] = err

    async def fake_extract(jd_text, options=None):  # noqa: ANN001
        return {"success": True, "data": {"position_name": "x", "required_skills": []}}

    async def patched_persist(session, jd_text, result, **kwargs):  # noqa: ANN001
        class R:
            id = captured_id  # type: ignore[misc]
            job_title = "test"
        # 2026-08-14 门禁修复: persist_extraction_result 现返回 3 元组
        # (record, position_id, skill_ids)（stage3_services.py:244 解包）。
        return R(), None, []

    async def fake_graph_write(data, **kwargs):  # noqa: ANN001
        return {"triples_merged": 3}

    async def fake_load(sm):  # noqa: ANN001
        return {}

    class _SessionCtx:
        async def __aenter__(self):
            class S:
                async def execute(self, *a, **k): return None
                def add(self, *a, **k): pass
                async def flush(self): pass
                def begin(self):
                    class T:
                        async def __aenter__(self): return None
                        async def __aexit__(self, *a): return False
                    return T()
            return S()

        async def __aexit__(self, *a): return False

    with (
        patch.object(stage3_services, "persist_extraction_result", patched_persist),
        patch.object(stage3_services, "extract_from_jd", fake_extract),
        patch.object(stage3_services, "write_single_extraction_to_graph", fake_graph_write),
        patch.object(stage3_services, "_load_source_counts", fake_load),
        patch.object(stage3_services, "get_async_engine", lambda: type("E", (), {"dispose": AsyncMock()})()),
        patch.object(stage3_services, "async_sessionmaker", lambda *a, **k: lambda: _SessionCtx()),
        patch.object(executor, "_create_outbox_record", fake_create),
        patch.object(executor, "_complete_outbox_record", fake_complete),
        patch.object(executor, "_fail_outbox_record", fake_fail),
    ):
        result = asyncio.run(stage3_services.run_batch_extract_jd("hi"))

    assert result["status"] == "completed"
    assert captured["run_id"] is None, "H1: manual extractions must use NULL run_id"
    assert captured["extraction_ids"] == [captured_id], "extraction_ids must link back to record"


# ── call_llm_with_fallback: track_all_4_providers via mock ─────────────────


def test_call_llm_with_fallback_tracks_costs_per_provider() -> None:
    """Mock the 4 provider callables and confirm tracker.record fires per success."""
    from app.core.extraction import llm_client
    from app.core.llm import cost_tracker

    cost_tracker.tracker._by_model.clear()

    # 2026-08-14 门禁修复: 降级链新增 DashScope(首选) 与 Spark X(短 prompt 优先)。
    # dashscope_api_key 未设 → 跳过；但 xunfei_api_key 已 stub 且 prompt 短 →
    # Spark X 会先于 MiMo 执行且未被 mock → 真实调用走 httpx stub（无 post 方法）崩。
    # 显式 mock Spark X 抛连接错误，让链落到 MiMo（测试意图：mimo-test 记账）。
    from app.core.extraction.llm_client import LLMConnectionError

    # Enable all 4 paths by stubbing settings + provider functions
    with (
        patch.object(llm_client.settings, "mimo_api_key", "stub", create=True),
        patch.object(llm_client.settings, "deepseek_api_key", "stub", create=True),
        patch.object(llm_client.settings, "xunfei_api_key", "stub", create=True),
        patch.object(llm_client.settings, "qwen_model_path", "http://localhost:11434", create=True),
        patch.object(
            llm_client, "call_mimo_llm",
            AsyncMock(return_value={"role": "assistant", "content": "mimo-out", "model": "mimo-test"}),
        ),
        patch.object(
            llm_client, "call_spark_x_llm",
            AsyncMock(side_effect=LLMConnectionError("spark-x down")),
        ),
        patch.object(
            llm_client, "call_deepseek_llm",
            AsyncMock(return_value={"role": "assistant", "content": "ds-out", "model": "ds-test"}),
        ),
        patch.object(
            llm_client, "call_xunfei_llm",
            AsyncMock(return_value={"role": "assistant", "content": "xf-out", "model": "xf-test"}),
        ),
        patch.object(
            llm_client, "httpx", new=_StubHttpxOk("ollama-out"),
        ),
    ):
        asyncio.run(llm_client.call_llm_with_fallback("prompt-prompt"))

    summary = cost_tracker.tracker.summary()
    # MiMo is tried first; succeeds → summary has mimo-test only
    assert "mimo-test" in summary["by_model"], summary
    assert summary["by_model"]["mimo-test"]["calls"] == 1


class _StubHttpxOk:
    """Fake httpx module so the Ollama path can run without network."""

    def __init__(self, content: str) -> None:
        self.content = content

    class AsyncClient:
        def __init__(self, *a, **k): pass

        async def __aenter__(self_inner):  # noqa: ANN001
            class _Resp:
                status_code = 200

                def raise_for_status(self): pass

                def json(self_inner_inner):  # noqa: ANN001
                    return {"message": {"content": "ollama-out"}}
            return _Resp()

        async def __aexit__(self, *a): return False

    class Timeout:
        def __init__(self, *a, **k): pass

    class TimeoutException(Exception):
        pass

    class RequestError(Exception):
        pass

    class HTTPStatusError(Exception):
        pass
