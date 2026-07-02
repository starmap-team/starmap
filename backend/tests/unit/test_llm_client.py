"""Tests for LLM client helpers."""
from __future__ import annotations

import pytest

from app.core.extraction.llm_client import (
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    parse_llm_json_response,
)


class TestLLMExceptions:
    def test_connection_error(self):
        e = LLMConnectionError("test")
        assert str(e) == "test"

    def test_response_error(self):
        e = LLMResponseError("test")
        assert str(e) == "test"

    def test_timeout_error(self):
        e = LLMTimeoutError("test")
        assert str(e) == "test"


class TestParseJson:
    def test_plain_json(self):
        result = parse_llm_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_code_fence(self):
        result = parse_llm_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_plain_code_fence(self):
        result = parse_llm_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_with_whitespace(self):
        result = parse_llm_json_response('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(LLMResponseError):
            parse_llm_json_response("not valid json")
