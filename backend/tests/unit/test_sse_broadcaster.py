"""Tests for SSE event broadcaster."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dashboard.sse_broadcaster import (
    VALID_EVENT_TYPES,
    _format_sse,
    get_recent_events,
    publish_event,
)


class TestValidEventTypes:
    def test_contains_expected_types(self):
        assert "pipeline_update" in VALID_EVENT_TYPES
        assert "quality_alert" in VALID_EVENT_TYPES
        assert "data_milestone" in VALID_EVENT_TYPES
        assert "extraction_complete" in VALID_EVENT_TYPES


class TestFormatSSE:
    def test_basic_format(self):
        result = _format_sse("test_event", {"key": "value"})
        assert "event: test_event" in result
        assert "data:" in result
        assert result.endswith("\n\n")
        # Extract and verify JSON data
        data_line = [l for l in result.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[5:])
        assert data["key"] == "value"

    def test_empty_data(self):
        result = _format_sse("ping", {})
        data_line = [l for l in result.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[5:])
        assert data == {}


class TestPublishEvent:
    @pytest.mark.asyncio
    async def test_none_redis_returns_false(self):
        result = await publish_event(None, "test", {"data": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_publishes_message(self):
        redis = MagicMock()
        redis.publish = AsyncMock(return_value=1)
        redis.lpush = AsyncMock(return_value=1)
        redis.ltrim = AsyncMock(return_value=True)
        redis.expire = AsyncMock(return_value=True)

        result = await publish_event(redis, "pipeline_update", {"run_id": "abc"})
        assert result is True
        redis.publish.assert_called_once()
        redis.lpush.assert_called_once()
        redis.ltrim.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        redis = MagicMock()
        redis.publish = AsyncMock(side_effect=Exception("connection lost"))
        redis.lpush = AsyncMock(return_value=1)

        result = await publish_event(redis, "test", {"data": 1})
        assert result is False


class TestGetRecentEvents:
    @pytest.mark.asyncio
    async def test_none_redis_returns_empty(self):
        result = await get_recent_events(None)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_parsed_events(self):
        redis = MagicMock()
        redis.lrange = AsyncMock(return_value=[
            '{"type": "a", "data": {}, "timestamp": 100}',
            '{"type": "b", "data": {}, "timestamp": 200}',
        ])

        events = await get_recent_events(redis)
        assert len(events) == 2
        assert events[0]["type"] == "a"
        assert events[1]["type"] == "b"

    @pytest.mark.asyncio
    async def test_filters_by_since(self):
        redis = MagicMock()
        redis.lrange = AsyncMock(return_value=[
            '{"type": "a", "data": {}, "timestamp": 100}',
            '{"type": "b", "data": {}, "timestamp": 200}',
        ])

        events = await get_recent_events(redis, since=150)
        assert len(events) == 1
        assert events[0]["type"] == "b"

    @pytest.mark.asyncio
    async def test_invalid_json_skipped(self):
        redis = MagicMock()
        redis.lrange = AsyncMock(return_value=[
            '{"type": "a", "timestamp": 100}',
            "not-json",
            '{"type": "b", "timestamp": 200}',
        ])

        events = await get_recent_events(redis)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        redis = MagicMock()
        redis.lrange = AsyncMock(side_effect=Exception("redis down"))

        events = await get_recent_events(redis)
        assert events == []
