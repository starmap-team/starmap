"""Tests for AP-07 (SSE client limit) and FE-02 (A/B test results)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dashboard.sse_broadcaster import (
    MAX_SSE_CLIENTS,
)

# ── AP-07: SSE connection limit ──


class TestAP07SSEClientLimit:
    """AP-07: SSE event_stream should enforce MAX_SSE_CLIENTS limit."""

    def test_max_clients_is_configured(self):
        assert MAX_SSE_CLIENTS > 0
        assert MAX_SSE_CLIENTS <= 200  # reasonable upper bound

    @pytest.mark.asyncio
    async def test_event_stream_rejects_when_at_capacity(self):
        """When _active_sse_clients >= MAX_SSE_CLIENTS, new connections get error event."""
        import app.core.dashboard.sse_broadcaster as sse_mod

        # Save original count
        original = sse_mod._active_sse_clients
        try:
            # Simulate at-capacity
            sse_mod._active_sse_clients = sse_mod.MAX_SSE_CLIENTS

            redis = MagicMock()
            redis.pubsub = MagicMock()
            pubsub = MagicMock()
            pubsub.subscribe = AsyncMock()
            redis.pubsub.return_value = pubsub

            from app.core.dashboard.sse_broadcaster import event_stream

            messages = []
            async for msg in event_stream(redis):
                messages.append(msg)
                break  # only need first message

            # Should get error event about max clients
            assert len(messages) == 1
            assert "Max SSE clients" in messages[0] or "error" in messages[0]
        finally:
            sse_mod._active_sse_clients = original


# ── FE-02: A/B test results endpoint ──


class TestFE02ABTestResults:
    """FE-02: A/B test result recording and aggregation."""

    @pytest.mark.asyncio
    async def test_record_and_retrieve_results(self):
        from app.api.v1.admin_prompts import (
            ABResultRequest,
            _ab_results,
            get_ab_results,
            record_ab_result,
        )

        # Clean slate
        prompt_name = "test_prompt_fe02"
        _ab_results.pop(prompt_name, None)

        # Record two results for v1 and one for v2
        await record_ab_result(prompt_name, ABResultRequest(version="v1", success=True, f1=0.85, latency_ms=100.0))
        await record_ab_result(prompt_name, ABResultRequest(version="v1", success=False, f1=0.70, latency_ms=150.0))
        await record_ab_result(prompt_name, ABResultRequest(version="v2", success=True, f1=0.92, latency_ms=80.0))

        # Retrieve aggregated results
        result = await get_ab_results(prompt_name)

        assert result["total"] == 3
        assert "v1" in result["versions"]
        assert "v2" in result["versions"]
        assert result["versions"]["v1"]["count"] == 2
        assert result["versions"]["v1"]["success_rate"] == 0.5
        assert result["versions"]["v1"]["avg_f1"] == pytest.approx(0.775, rel=0.01)
        assert result["versions"]["v2"]["count"] == 1
        assert result["versions"]["v2"]["success_rate"] == 1.0
        assert result["versions"]["v2"]["avg_f1"] == 0.92

        # Cleanup
        _ab_results.pop(prompt_name, None)

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from app.api.v1.admin_prompts import _ab_results, get_ab_results

        prompt_name = "nonexistent_prompt_fe02"
        _ab_results.pop(prompt_name, None)

        result = await get_ab_results(prompt_name)
        assert result["total"] == 0
        assert result["versions"] == {}
