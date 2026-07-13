"""Deep tests for LLM client — fallback chain, JSON parsing, and LLMClient methods.

Covers:
- parse_llm_json_response: pure function tests for JSON extraction from LLM output
- call_llm_with_fallback: fallback chain MiMo -> DeepSeek -> Xunfei -> Qwen/Ollama
- LLMClient.extract_from_jd, validate_extraction, judge_quality: high-level methods
- Individual LLM call functions (call_mimo_llm, call_deepseek_llm, call_xunfei_llm)
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.extraction.llm_client import (
    LLMClient,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    call_deepseek_llm,
    call_llm_with_fallback,
    call_mimo_llm,
    call_xunfei_llm,
    parse_llm_json_response,
)

# ═══════════════════════════════════════════════════════════════
# TestParseLlmJsonResponse — pure function, no external deps
# ═══════════════════════════════════════════════════════════════


class TestParseLlmJsonResponse:
    """Tests for parse_llm_json_response — pure function, no external deps."""

    def test_plain_json_object(self):
        result = parse_llm_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_fences(self):
        result = parse_llm_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_in_plain_code_fences(self):
        result = parse_llm_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_leading_whitespace(self):
        result = parse_llm_json_response('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_json_with_trailing_text_still_parses(self):
        """JSON.loads is strict — trailing text causes failure unless it's valid JSON prefix."""
        # This should fail because JSON with trailing text is not valid JSON
        with pytest.raises(LLMResponseError):
            parse_llm_json_response('{"key": "value"} some text')

    def test_invalid_json_raises(self):
        with pytest.raises(LLMResponseError, match="Failed to parse LLM JSON"):
            parse_llm_json_response("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(LLMResponseError):
            parse_llm_json_response("")

    def test_nested_json(self):
        nested = {"outer": {"inner": [1, 2, 3]}, "arr": [{"a": "b"}]}
        result = parse_llm_json_response(json.dumps(nested))
        assert result == nested

    def test_json_with_jsonl_fence(self):
        result = parse_llm_json_response('```jsonl\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_array(self):
        result = parse_llm_json_response('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_json_with_unicode(self):
        result = parse_llm_json_response('{"name": "技能"}')
        assert result == {"name": "技能"}

    def test_code_fence_without_closing_fence(self):
        """Code fence without closing backticks — content is everything after first line."""
        result = parse_llm_json_response('```json\n{"key": "value"}')
        assert result == {"key": "value"}


# ═══════════════════════════════════════════════════════════════
# TestCallMimoLlm — mock httpx, test MiMo API call
# ═══════════════════════════════════════════════════════════════


class TestCallMimoLlm:
    """Tests for call_mimo_llm with mocked httpx."""

    @pytest.mark.asyncio
    async def test_success_returns_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "hello", "reasoning_content": "thinking..."}}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.mimo_api_key = "test-key"
                mock_settings.mimo_model = "mimo-test"
                mock_settings.mimo_api_base = "https://api.example.com"
                mock_settings.llm_timeout = 30

                result = await call_mimo_llm("test prompt")

        assert result["role"] == "assistant"
        assert result["content"] == "hello"
        assert result["model"] == "mimo-test"

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        with patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_settings.mimo_api_key = ""
            mock_settings.llm_timeout = 30

            with pytest.raises(LLMConnectionError, match="MIMO_API_KEY"):
                await call_mimo_llm("test prompt")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.mimo_api_key = "test-key"
                mock_settings.mimo_model = "mimo-test"
                mock_settings.mimo_api_base = "https://api.example.com"
                mock_settings.llm_timeout = 30

                with pytest.raises(LLMTimeoutError, match="MiMo API timeout"):
                    await call_mimo_llm("test prompt")

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response,
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.mimo_api_key = "test-key"
                mock_settings.mimo_model = "mimo-test"
                mock_settings.mimo_api_base = "https://api.example.com"
                mock_settings.llm_timeout = 30

                with pytest.raises(LLMResponseError, match="MiMo API returned 500"):
                    await call_mimo_llm("test prompt")

    @pytest.mark.asyncio
    async def test_connection_error_raises(self):
        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.RequestError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.mimo_api_key = "test-key"
                mock_settings.mimo_model = "mimo-test"
                mock_settings.mimo_api_base = "https://api.example.com"
                mock_settings.llm_timeout = 30

                with pytest.raises(LLMConnectionError, match="MiMo API connection failed"):
                    await call_mimo_llm("test prompt")

    @pytest.mark.asyncio
    async def test_empty_choices_raises(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.mimo_api_key = "test-key"
                mock_settings.mimo_model = "mimo-test"
                mock_settings.mimo_api_base = "https://api.example.com"
                mock_settings.llm_timeout = 30

                with pytest.raises(LLMResponseError, match="empty choices"):
                    await call_mimo_llm("test prompt")


# ═══════════════════════════════════════════════════════════════
# TestCallDeepseekLlm — mock httpx, test DeepSeek API call
# ═══════════════════════════════════════════════════════════════


class TestCallDeepseekLlm:
    """Tests for call_deepseek_llm with mocked httpx."""

    @pytest.mark.asyncio
    async def test_success_returns_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "deepseek response"}}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.deepseek_api_key = "ds-key"
                mock_settings.deepseek_model = "deepseek-test"
                mock_settings.llm_timeout = 30

                result = await call_deepseek_llm("test prompt")

        assert result["content"] == "deepseek response"
        assert result["model"] == "deepseek-test"

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        with patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_settings.deepseek_api_key = ""
            mock_settings.llm_timeout = 30

            with pytest.raises(LLMConnectionError, match="DEEPSEEK_API_KEY"):
                await call_deepseek_llm("test prompt")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.deepseek_api_key = "ds-key"
                mock_settings.deepseek_model = "deepseek-test"
                mock_settings.llm_timeout = 30

                with pytest.raises(LLMTimeoutError, match="DeepSeek API timeout"):
                    await call_deepseek_llm("test prompt")


# ═══════════════════════════════════════════════════════════════
# TestCallXunfeiLlm — mock httpx, test Xunfei API call
# ═══════════════════════════════════════════════════════════════


class TestCallXunfeiLlm:
    """Tests for call_xunfei_llm with mocked httpx."""

    @pytest.mark.asyncio
    async def test_success_returns_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "xunfei response"}}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.xunfei_api_key = "xf-key"
                mock_settings.llm_timeout = 30

                result = await call_xunfei_llm("test prompt")

        assert result["content"] == "xunfei response"
        assert result["model"] == "v3.5"

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        with patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_settings.xunfei_api_key = ""
            mock_settings.llm_timeout = 30

            with pytest.raises(LLMConnectionError, match="XUNFEI_API_KEY"):
                await call_xunfei_llm("test prompt")

    @pytest.mark.asyncio
    async def test_custom_model_version(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.core.extraction.llm_client.settings") as mock_settings:
                mock_settings.xunfei_api_key = "xf-key"
                mock_settings.llm_timeout = 30

                result = await call_xunfei_llm("test prompt", model_version="v4.0")

        assert result["model"] == "v4.0"


# ═══════════════════════════════════════════════════════════════
# TestCallLlmWithFallback — mock individual LLM functions
# ═══════════════════════════════════════════════════════════════


class TestCallLlmWithFallback:
    """Tests for call_llm_with_fallback — fallback chain logic."""

    @pytest.mark.asyncio
    async def test_mimo_succeeds_first(self):
        """MiMo succeeds — no fallback called."""
        with patch("app.core.extraction.llm_client.call_mimo_llm", new_callable=AsyncMock) as mock_mimo, \
             patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_mimo.return_value = {"role": "assistant", "content": "mimo result", "model": "mimo"}
            mock_settings.mimo_api_key = "key"
            mock_settings.deepseek_api_key = "key"
            mock_settings.xunfei_api_key = "key"
            mock_settings.qwen_model_path = ""

            result = await call_llm_with_fallback("test prompt")

        assert result["content"] == "mimo result"
        mock_mimo.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_mimo_fails_deepseek_succeeds(self):
        """MiMo fails, DeepSeek succeeds."""
        with patch("app.core.extraction.llm_client.call_mimo_llm", new_callable=AsyncMock) as mock_mimo, \
             patch("app.core.extraction.llm_client.call_deepseek_llm", new_callable=AsyncMock) as mock_ds, \
             patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_mimo.side_effect = LLMConnectionError("MiMo down")
            mock_ds.return_value = {"role": "assistant", "content": "ds result", "model": "ds"}
            mock_settings.mimo_api_key = "key"
            mock_settings.deepseek_api_key = "key"
            mock_settings.xunfei_api_key = "key"
            mock_settings.qwen_model_path = ""

            result = await call_llm_with_fallback("test prompt")

        assert result["content"] == "ds result"
        mock_mimo.assert_called_once()
        mock_ds.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_mimo_deepseek_fail_xunfei_succeeds(self):
        """MiMo and DeepSeek fail, Xunfei succeeds."""
        with patch("app.core.extraction.llm_client.call_mimo_llm", new_callable=AsyncMock) as mock_mimo, \
             patch("app.core.extraction.llm_client.call_deepseek_llm", new_callable=AsyncMock) as mock_ds, \
             patch("app.core.extraction.llm_client.call_xunfei_llm", new_callable=AsyncMock) as mock_xf, \
             patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_mimo.side_effect = LLMConnectionError("MiMo down")
            mock_ds.side_effect = LLMResponseError("DS error")
            mock_xf.return_value = {"role": "assistant", "content": "xf result", "model": "xf"}
            mock_settings.mimo_api_key = "key"
            mock_settings.deepseek_api_key = "key"
            mock_settings.xunfei_api_key = "key"
            mock_settings.qwen_model_path = ""

            result = await call_llm_with_fallback("test prompt")

        assert result["content"] == "xf result"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self):
        """All LLM calls fail — LLMConnectionError propagated."""
        with patch("app.core.extraction.llm_client.call_mimo_llm", new_callable=AsyncMock) as mock_mimo, \
             patch("app.core.extraction.llm_client.call_deepseek_llm", new_callable=AsyncMock) as mock_ds, \
             patch("app.core.extraction.llm_client.call_xunfei_llm", new_callable=AsyncMock) as mock_xf, \
             patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_mimo.side_effect = LLMConnectionError("MiMo down")
            mock_ds.side_effect = LLMConnectionError("DS down")
            mock_xf.side_effect = LLMConnectionError("XF down")
            mock_settings.mimo_api_key = "key"
            mock_settings.deepseek_api_key = "key"
            mock_settings.xunfei_api_key = "key"
            mock_settings.qwen_model_path = ""

            with pytest.raises(LLMConnectionError, match="No LLM endpoint configured"):
                await call_llm_with_fallback("test prompt")

    @pytest.mark.asyncio
    async def test_timeout_triggers_fallback(self):
        """MiMo timeout triggers fallback to DeepSeek."""
        with patch("app.core.extraction.llm_client.call_mimo_llm", new_callable=AsyncMock) as mock_mimo, \
             patch("app.core.extraction.llm_client.call_deepseek_llm", new_callable=AsyncMock) as mock_ds, \
             patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_mimo.side_effect = LLMTimeoutError("MiMo timeout")
            mock_ds.return_value = {"role": "assistant", "content": "ds result", "model": "ds"}
            mock_settings.mimo_api_key = "key"
            mock_settings.deepseek_api_key = "key"
            mock_settings.xunfei_api_key = "key"
            mock_settings.qwen_model_path = ""

            result = await call_llm_with_fallback("test prompt")

        assert result["content"] == "ds result"

    @pytest.mark.asyncio
    async def test_no_api_keys_skips_providers(self):
        """No API keys configured — skips providers, raises error."""
        with patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_settings.mimo_api_key = ""
            mock_settings.deepseek_api_key = ""
            mock_settings.xunfei_api_key = ""
            mock_settings.qwen_model_path = ""

            with pytest.raises(LLMConnectionError, match="no providers available"):
                await call_llm_with_fallback("test prompt")

    @pytest.mark.asyncio
    async def test_qwen_fallback_succeeds(self):
        """All primary providers fail, Qwen/Ollama fallback succeeds."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "qwen result"}}
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.extraction.llm_client.call_mimo_llm", new_callable=AsyncMock) as mock_mimo, \
             patch("app.core.extraction.llm_client.call_deepseek_llm", new_callable=AsyncMock) as mock_ds, \
             patch("app.core.extraction.llm_client.call_xunfei_llm", new_callable=AsyncMock) as mock_xf, \
             patch("app.core.extraction.llm_client.httpx.AsyncClient") as mock_client_cls, \
             patch("app.core.extraction.llm_client.settings") as mock_settings:
            mock_mimo.side_effect = LLMConnectionError("MiMo down")
            mock_ds.side_effect = LLMConnectionError("DS down")
            mock_xf.side_effect = LLMConnectionError("XF down")

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            mock_settings.mimo_api_key = "key"
            mock_settings.deepseek_api_key = "key"
            mock_settings.xunfei_api_key = "key"
            mock_settings.qwen_model_path = "http://localhost:11434"

            result = await call_llm_with_fallback("test prompt")

        assert result["content"] == "qwen result"
        assert result["model"] == "qwen2.5-7b-fallback"


# ═══════════════════════════════════════════════════════════════
# TestLLMClientMethods — mock call_llm_with_fallback
# ═══════════════════════════════════════════════════════════════


class TestLLMClientMethods:
    """Tests for LLMClient high-level methods."""

    @pytest.mark.asyncio
    async def test_extract_from_jd_success(self):
        client = LLMClient()
        mock_response = {"role": "assistant", "content": '{"position_name": "Backend Dev", "required_skills": []}'}

        with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock_fallback, \
             patch("app.core.extraction.prompt.get_prompt", return_value="test prompt"):
            mock_fallback.return_value = mock_response

            result = await client.extract_from_jd("JD text here")

        assert result["position_name"] == "Backend Dev"
        assert result["required_skills"] == []

    @pytest.mark.asyncio
    async def test_extract_from_jd_parse_error(self):
        """LLM returns unparseable content — LLMResponseError raised."""
        client = LLMClient()
        mock_response = {"role": "assistant", "content": "not valid json"}

        with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock_fallback, \
             patch("app.core.extraction.prompt.get_prompt", return_value="test prompt"):
            mock_fallback.return_value = mock_response

            with pytest.raises(LLMResponseError):
                await client.extract_from_jd("JD text here")

    @pytest.mark.asyncio
    async def test_validate_extraction_success(self):
        client = LLMClient()
        mock_response = {"role": "assistant", "content": '{"is_valid": true, "confidence": 0.95}'}

        with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock_fallback, \
             patch("app.core.extraction.prompt.get_prompt", return_value="test prompt"):
            mock_fallback.return_value = mock_response

            result = await client.validate_extraction({"skills": []}, "JD text")

        assert result["is_valid"] is True
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_judge_quality_success(self):
        client = LLMClient()
        mock_response = {"role": "assistant", "content": '{"f1_score": 0.85, "details": "good match"}'}

        with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock_fallback, \
             patch("app.core.extraction.prompt.get_prompt", return_value="test prompt"):
            mock_fallback.return_value = mock_response

            result = await client.judge_quality({"system": "output"}, {"golden": "standard"})

        assert result["f1_score"] == 0.85
        assert result["details"] == "good match"

    @pytest.mark.asyncio
    async def test_extract_from_jd_with_markdown_fenced_json(self):
        """LLM returns JSON wrapped in markdown code fences."""
        client = LLMClient()
        content = '```json\n{"position_name": "DevOps", "required_skills": []}\n```'
        mock_response = {"role": "assistant", "content": content}

        with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock_fallback, \
             patch("app.core.extraction.prompt.get_prompt", return_value="test prompt"):
            mock_fallback.return_value = mock_response

            result = await client.extract_from_jd("JD text")

        assert result["position_name"] == "DevOps"
