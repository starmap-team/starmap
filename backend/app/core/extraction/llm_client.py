"""Multi-provider LLM client with fallback support.

Supports:
- MiMo API: https://token-plan-cn.xiaomimimo.com/v1 (reasoning model, primary)
- DeepSeek API: https://api.deepseek.com/chat/completions
- Xunfei Spark API: https://spark-api-open.xf-yun.com/v1/chat/completions
- Local Qwen/Ollama fallback: /api/chat endpoint

Fallback chain: MiMo -> DeepSeek -> Xunfei -> Qwen/Ollama
Authentication: Bearer token via API keys.
"""

import json
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


class LLMConnectionError(Exception):
    """Raised when connection to the LLM API fails."""


class LLMResponseError(Exception):
    """Raised when the LLM returns an unexpected response."""


class LLMTimeoutError(Exception):
    """Raised when the LLM API request times out."""


# API endpoints
_SPARK_HTTP_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"
_DEEPSEEK_HTTP_URL = "https://api.deepseek.com/chat/completions"

# Model mappings
_SPARK_MODELS: dict[str, str] = {
    "lite": "lite",
    "v2.0": "generalv2",
    "v3.0": "generalv3",
    "v3.5": "generalv3.5",
    "max-32k": "max-32k",
    "v4.0": "4.0Ultra",
    "pro-128k": "pro-128k",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
async def call_mimo_llm(
    prompt: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Call Xiaomi MiMo API (OpenAI-compatible endpoint, reasoning model).

    MiMo is a reasoning model: it uses reasoning_tokens before producing
    output. max_tokens must cover both reasoning + output, so we use 8192.

    Returns:
        Dict with 'role', 'content', 'model' keys (content = final answer only,
        reasoning_content discarded).
    """
    actual_timeout = timeout if timeout is not None else max(settings.llm_timeout, 30)
    api_key = settings.mimo_api_key
    if not api_key:
        raise LLMConnectionError("MIMO_API_KEY is not configured")

    base = settings.mimo_api_base.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.mimo_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8192,  # reasoning model: needs room for reasoning + output
    }

    logger.info("Calling MiMo {} at {}", settings.mimo_model, base)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(actual_timeout)) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(f"MiMo API timeout after {actual_timeout}s") from e
    except httpx.HTTPStatusError as e:
        raise LLMResponseError(f"MiMo API returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMConnectionError(f"MiMo API connection failed: {e}") from e

    choices = data.get("choices", [])
    if not choices:
        raise LLMResponseError("MiMo API returned empty choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    reasoning = message.get("reasoning_content", "")
    logger.debug("MiMo response: {} output chars, {} reasoning chars", len(content), len(reasoning))
    return {"role": "assistant", "content": content, "model": settings.mimo_model}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_xunfei_llm(
    prompt: str,
    model_version: str = "v3.5",
    timeout: int | None = None,
) -> dict[str, Any]:
    """Call Xunfei Spark API (OpenAI-compatible HTTP endpoint).

    Args:
        prompt: Input prompt text.
        model_version: Spark model version key.
        timeout: Request timeout in seconds (default: settings.llm_timeout).

    Returns:
        Dict with 'role', 'content', 'model' keys.

    Raises:
        LLMConnectionError: On connection failure.
        LLMResponseError: On unexpected response.
        LLMTimeoutError: On timeout.
    """
    actual_timeout = timeout if timeout is not None else settings.llm_timeout
    model = _SPARK_MODELS.get(model_version, "generalv3.5")
    api_key = settings.xunfei_api_key
    if not api_key:
        raise LLMConnectionError("XUNFEI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 4096,
    }

    logger.info("Calling Xunfei Spark {} ({})", model_version, model)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(actual_timeout)) as client:
            response = await client.post(_SPARK_HTTP_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(f"Xunfei API timeout after {actual_timeout}s") from e
    except httpx.HTTPStatusError as e:
        raise LLMResponseError(f"Xunfei API returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMConnectionError(f"Xunfei API connection failed: {e}") from e

    choices = data.get("choices", [])
    if not choices:
        raise LLMResponseError("Xunfei API returned empty choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    logger.debug("Xunfei response received ({} chars)", len(content))
    return {"role": "assistant", "content": content, "model": model_version}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_deepseek_llm(
    prompt: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Call DeepSeek API (OpenAI-compatible HTTP endpoint).

    Args:
        prompt: Input prompt text.
        timeout: Request timeout in seconds (default: settings.llm_timeout).

    Returns:
        Dict with 'role', 'content', 'model' keys.

    Raises:
        LLMConnectionError: On connection failure.
        LLMResponseError: On unexpected response.
        LLMTimeoutError: On timeout.
    """
    actual_timeout = timeout if timeout is not None else settings.llm_timeout
    api_key = settings.deepseek_api_key
    if not api_key:
        raise LLMConnectionError("DEEPSEEK_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 4096,
    }

    logger.info("Calling DeepSeek ({})", settings.deepseek_model)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(actual_timeout)) as client:
            response = await client.post(_DEEPSEEK_HTTP_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(f"DeepSeek API timeout after {actual_timeout}s") from e
    except httpx.HTTPStatusError as e:
        raise LLMResponseError(f"DeepSeek API returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMConnectionError(f"DeepSeek API connection failed: {e}") from e

    choices = data.get("choices", [])
    if not choices:
        raise LLMResponseError("DeepSeek API returned empty choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    logger.debug("DeepSeek response received ({} chars)", len(content))
    return {"role": "assistant", "content": content, "model": settings.deepseek_model}


async def call_llm_with_fallback(prompt: str) -> dict[str, Any]:
    """Call LLM with fallback: MiMo -> DeepSeek -> Xunfei -> Qwen/Ollama.

    Args:
        prompt: Input prompt text.

    Returns:
        Response dict with 'content' key.
    """
    errors: list[str] = []

    # Try MiMo first (primary, reasoning model)
    if settings.mimo_api_key:
        try:
            return await call_mimo_llm(prompt)
        except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
            msg = f"MiMo failed: {e}"
            logger.warning(msg)
            errors.append(msg)

    # Try DeepSeek second
    if settings.deepseek_api_key:
        try:
            return await call_deepseek_llm(prompt)
        except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
            msg = f"DeepSeek failed: {e}"
            logger.warning(msg)
            errors.append(msg)

    # Try Xunfei third
    if settings.xunfei_api_key:
        try:
            return await call_xunfei_llm(prompt)
        except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
            msg = f"Xunfei failed: {e}"
            logger.warning(msg)
            errors.append(msg)

    # Try local Qwen/Ollama fallback
    fallback_endpoint = settings.qwen_model_path
    if not fallback_endpoint:
        raise LLMConnectionError(
            f"No LLM endpoint configured. Tried: {'; '.join(errors) if errors else 'no providers available'}"
        )

    base = fallback_endpoint.rstrip("/")
    # Ollama uses /api/chat, not /v1/chat/completions
    ollama_url = f"{base}/api/chat"
    logger.info("Calling fallback Qwen/Ollama at {}", ollama_url)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": "qwen2.5:7b",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.5,
                        "num_predict": 4096,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]
            return {"role": "assistant", "content": content, "model": "qwen2.5-7b-fallback"}
    except httpx.TimeoutException as e:
        raise LLMTimeoutError("Fallback LLM timeout") from e
    except (httpx.RequestError, KeyError, IndexError) as e:
        raise LLMConnectionError(f"Fallback LLM failed: {e}") from e


def parse_llm_json_response(response_text: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling markdown code fences.

    Args:
        response_text: Raw response text from LLM.

    Returns:
        Parsed JSON dict.

    Raises:
        LLMResponseError: If JSON parsing fails.
    """
    text = response_text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        fence = lines[0]
        lang = fence.strip("`").strip().lower()
        if lang in ("json", "jsonl"):
            lines = lines[1:]
        else:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMResponseError(f"Failed to parse LLM JSON response: {e}\nRaw: {response_text[:500]}") from e


class LLMClient:
    """High-level LLM client for extraction tasks."""

    async def extract_from_jd(self, jd_text: str) -> dict[str, Any]:
        """Extract skills from a job description."""
        from app.core.extraction.prompt import get_prompt

        prompt = get_prompt("jd_extraction", jd_content=jd_text)
        response = await call_llm_with_fallback(prompt)
        return parse_llm_json_response(response["content"])

    async def validate_extraction(
        self,
        extraction_json: dict[str, Any],
        jd_text: str,
    ) -> dict[str, Any]:
        """Validate extracted skills via anti-hallucination check."""
        from app.core.extraction.prompt import get_prompt

        prompt = get_prompt(
            "anti_hallucination",
            extraction_json=json.dumps(extraction_json, ensure_ascii=False, indent=2),
            jd_content=jd_text,
        )
        response = await call_llm_with_fallback(prompt)
        return parse_llm_json_response(response["content"])

    async def judge_quality(
        self,
        system_output: dict[str, Any],
        golden: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate extraction quality against golden standard."""
        from app.core.extraction.prompt import get_prompt

        prompt = get_prompt(
            "llm_judge",
            system_json=json.dumps(system_output, ensure_ascii=False, indent=2),
            golden_json=json.dumps(golden, ensure_ascii=False, indent=2),
        )
        response = await call_llm_with_fallback(prompt)
        return parse_llm_json_response(response["content"])
