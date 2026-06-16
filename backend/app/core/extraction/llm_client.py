"""Xunfei Spark API async LLM client with fallback support.

Uses the OpenAI-compatible HTTP API: https://spark-api-open.xf-yun.com/v1/chat/completions
Authentication: Bearer token via XUNFEI_API_KEY (APIPassword from console).
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


_SPARK_HTTP_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"

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
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_xunfei_llm(
    prompt: str,
    model_version: str = "v3.5",
    timeout: int = 60,
) -> dict[str, Any]:
    """Call Xunfei Spark API (OpenAI-compatible HTTP endpoint).

    Args:
        prompt: Input prompt text.
        model_version: Spark model version key.
        timeout: Request timeout in seconds.

    Returns:
        Dict with 'role', 'content', 'model' keys.

    Raises:
        LLMConnectionError: On connection failure.
        LLMResponseError: On unexpected response.
        LLMTimeoutError: On timeout.
    """
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
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(_SPARK_HTTP_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(f"Xunfei API timeout after {timeout}s") from e
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


async def call_llm_with_fallback(prompt: str) -> dict[str, Any]:
    """Call LLM with fallback: Xunfei primary, local Qwen fallback.

    Args:
        prompt: Input prompt text.

    Returns:
        Response dict with 'content' key.
    """
    try:
        return await call_xunfei_llm(prompt)
    except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
        logger.warning("Xunfei failed, trying fallback: {}", e)

    fallback_endpoint = settings.qwen_model_path
    if not fallback_endpoint:
        raise LLMConnectionError("No fallback endpoint configured (qwen_model_path is empty)")

    logger.info("Calling fallback Qwen at {}", fallback_endpoint)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
            resp = await client.post(
                f"{fallback_endpoint}/v1/chat/completions",
                json={
                    "model": "qwen",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"role": "assistant", "content": content, "model": "qwen-fallback"}
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
