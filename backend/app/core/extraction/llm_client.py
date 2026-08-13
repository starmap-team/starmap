"""LLM Client — 多供应商 LLM 客户端，支持自动降级。

支持的模型（按优先级排序）：
- 讯飞 Spark X（X2/X1.5 深度推理，model=spark-x，首选）
- MiMo API: https://token-plan-cn.xiaomimimo.com/v1 (推理模型)
- DeepSeek API: https://api.deepseek.com/chat/completions
- Xunfei Spark API: https://spark-api-open.xf-yun.com/v1/chat/completions
- 本地 Qwen/Ollama 降级: /api/chat 端点

降级链：Spark X → MiMo → DeepSeek → Xunfei Spark → Qwen/Ollama
认证：通过 API Key 的 Bearer Token（讯飞系为 `Bearer {APIKey}:{APISecret}`）。

业务价值：
  确保技能抽取服务的高可用性，当主用模型不可用时自动切换备用模型，
  避免单点故障导致整个抽取流程中断。
"""

import json
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.llm.cost_tracker import tracker


class LLMConnectionError(Exception):
    """Raised when connection to the LLM API fails."""


class LLMResponseError(Exception):
    """Raised when the LLM returns an unexpected response."""


class LLMTimeoutError(Exception):
    """Raised when the LLM API request times out."""


# Model mappings（端点 URL 由 settings.spark_http_url / settings.deepseek_http_url 提供）
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
    api_secret = settings.xunfei_api_secret
    if not api_key:
        raise LLMConnectionError("XUNFEI_API_KEY is not configured")

    # 讯飞 HTTP OpenAI 兼容端点鉴权为 `Bearer {APIKey}:{APISecret}`（OpenAI 兼容，
    # 非 Spark WebSocket 的三段式 HMAC 签名）。实测仅带 APIKey 会 401
    # ("HMAC secret key does not match")；带 `APIKey:APISecret` 鉴权通过。
    if api_secret:
        bearer = f"{api_key}:{api_secret}"
    else:
        bearer = api_key

    headers = {
        "Authorization": f"Bearer {bearer}",
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
            response = await client.post(settings.spark_http_url, json=payload, headers=headers)
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


async def call_spark_x_llm(
    prompt: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Call Xunfei Spark X 深度推理模型（X2 / X1.5，model 固定为 spark-x）。

    Spark X 是深度推理模型：响应含 reasoning_content（推理轨迹）+ content（最终答案）。
    X2 端点：/x2/chat/completions（默认，推理更强）；X1.5 端点：/v2/chat/completions
    （更快）。鉴权与 Spark HTTP 兼容端点一致：`Bearer {APIKey}:{APISecret}`。

    2026-08-11 实测：X2 12s（reasoning 562 tokens）/ X1.5 7s，均可用。

    Args:
        prompt: Input prompt text.
        timeout: Request timeout in seconds (默认取 settings.llm_timeout)。

    Returns:
        Dict with 'role', 'content', 'model' keys（content = 最终答案，reasoning_content 丢弃）。

    Raises:
        LLMConnectionError / LLMResponseError / LLMTimeoutError。
    """
    actual_timeout = timeout if timeout is not None else max(settings.llm_timeout, 180)
    api_key = settings.xunfei_api_key
    api_secret = settings.xunfei_api_secret
    if not api_key:
        raise LLMConnectionError("XUNFEI_API_KEY is not configured")

    bearer = f"{api_key}:{api_secret}" if api_secret else api_key
    # 兼容两种配置：SPARK_X_URL 可能含 /chat/completions 后缀（如 /x2/chat/completions）
    # 也可能只到模型根路径（如 /x2/）——统一规范化，避免重复拼接导致 404。
    base = settings.spark_x_url.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
    }
    # 深度推理模型：max_tokens 需覆盖 reasoning + output
    payload = {
        "model": settings.spark_x_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8192,
    }

    logger.info("Calling Xunfei Spark X ({}) at {}", settings.spark_x_model, url)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(actual_timeout)) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(f"Spark X API timeout after {actual_timeout}s") from e
    except httpx.HTTPStatusError as e:
        raise LLMResponseError(f"Spark X API returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMConnectionError(f"Spark X API connection failed: {e}") from e

    choices = data.get("choices", [])
    if not choices:
        raise LLMResponseError("Spark X API returned empty choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    reasoning = message.get("reasoning_content", "")
    logger.debug("Spark X response: {} output chars, {} reasoning chars", len(content), len(reasoning))
    return {"role": "assistant", "content": content, "model": settings.spark_x_model}


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
            response = await client.post(settings.deepseek_http_url, json=payload, headers=headers)
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


# Spark X 深度推理对长 prompt 会触发讯飞网关 60s 504（实测：抽取 prompt ~2582 chars
# → 504；反幻觉 ~591 chars → 16s OK）。长 prompt 直接跳过 Spark X，避免每次拖 61s 后降级。
SPARK_X_MAX_PROMPT_CHARS = 1500


async def call_llm_with_fallback(
    prompt: str,
    prefer_spark_x: bool = False,
) -> dict[str, Any]:
    """Call LLM with fallback.

    路由策略（2026-08-11）：
    - Spark X（深度推理，X2）优先用于短 prompt（≤1500 字符）或 `prefer_spark_x=True`
      的调用（如 LLM 评测）；长抽取 prompt 直接跳过（讯飞网关 60s 504 限制）。
    - 之后依次 MiMo → DeepSeek → Xunfei Spark → Qwen/Ollama。

    Args:
        prompt: Input prompt text.
        prefer_spark_x: 显式要求优先 Spark X（用于质量敏感且 prompt 较短的调用）。

    Returns:
        Response dict with 'content' key.
    """
    errors: list[str] = []

    async def _call_and_track(coro_factory):  # type: ignore[no-untyped-def]
        """Run a provider call and record its cost before returning."""
        resp = await coro_factory(prompt)
        tracker.record(
            model=resp.get("model", "unknown"),
            prompt=prompt,
            content=str(resp.get("content", "")),
        )
        return resp

    spark_x_candidate = settings.xunfei_api_key and (
        prefer_spark_x or len(prompt) <= SPARK_X_MAX_PROMPT_CHARS
    )

    # Try Spark X first (X2/X1.5 深度推理 — 用户首选；仅短 prompt 或显式偏好时)
    if spark_x_candidate:
        try:
            return await _call_and_track(call_spark_x_llm)
        except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
            msg = f"Spark X failed: {e}"
            logger.warning(msg)
            errors.append(msg)

    # Try MiMo (secondary reasoning model)
    if settings.mimo_api_key:
        try:
            return await _call_and_track(call_mimo_llm)
        except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
            msg = f"MiMo failed: {e}"
            logger.warning(msg)
            errors.append(msg)

    # Try DeepSeek (抽取主阶段首选：长 prompt 稳定 4-7s)
    if settings.deepseek_api_key:
        try:
            return await _call_and_track(call_deepseek_llm)
        except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
            msg = f"DeepSeek failed: {e}"
            logger.warning(msg)
            errors.append(msg)

    # Try Xunfei Spark 传统模型
    if settings.xunfei_api_key:
        try:
            return await _call_and_track(call_xunfei_llm)
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
        # 本地 Ollama 生成慢（短 JD ~40-120s+），硬编码 120s 常导致真实抽取
        # 超时。放宽到 300s，让本地降级模型也能完成真实抽取（前端同步放宽）。
        async with httpx.AsyncClient(timeout=httpx.Timeout(300)) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": settings.qwen_model_name,
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
            result = {"role": "assistant", "content": content, "model": f"{settings.qwen_model_name.replace(':', '-')}-fallback"}
            tracker.record(model=result["model"], prompt=prompt, content=content)
            return result
    except httpx.TimeoutException as e:
        raise LLMTimeoutError("Fallback LLM timeout") from e
    except httpx.RequestError as e:
        # Network/HTTP transport errors — wrap as connection failure.
        raise LLMConnectionError(f"Fallback LLM transport failed: {e}") from e
    except (KeyError, IndexError) as e:
        # P0-AUDIT-FIX (2026-08-13): response-shape errors must NOT be coerced
        # into LLMConnectionError. If Ollama/Qwen changes its JSON layout,
        # the caller treats this as a transient transport failure and retries
        # forever. Re-raise as LLMResponseError so the orchestrator can decide
        # whether to retry (no) or fall back further (yes).
        raise LLMResponseError(f"Fallback LLM returned unexpected shape: {e}") from e


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
        # 记录实际用于抽取的模型（含降级 fallback，如 qwen2.5-7b-fallback），
        # 供抽取管线透传给前端做“本次所用模型/是否降级”提示。
        self.last_extraction_model = response.get("model")
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
        # LLM 评测质量敏感且 prompt 较短 → 优先 Spark X 深度推理
        response = await call_llm_with_fallback(prompt, prefer_spark_x=True)
        return parse_llm_json_response(response["content"])

    async def generate(self, prompt: str, **_kwargs: Any) -> str:
        """通用 LLM 调用 (I18N-01 翻译钩子适配接口).

        core/extraction/translation.translate_title_industry 依赖
        ``generate(prompt, json_mode=True, temperature=0.0)`` 形态;
        json_mode/temperature 由 prompt 内容承载, 此处不做额外解析.
        """
        response = await call_llm_with_fallback(prompt)
        return response.get("content", "")
