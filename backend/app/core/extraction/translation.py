"""English → Chinese translation hook for non-CJK JD sources (Phase 15 / I18N-01).

When a JD's title/industry is detected as non-CJK (English), we ask the LLM to
provide a Chinese version that is then stored in `position_records.name_cn` and
`industry_zh` (separate columns). The original fields are kept intact so we don't
lose the source language.

Failure mode: if the LLM errors out, we fall back to using the original text
as `name_cn` and tag the row with `name_translated_by='original'` so the frontend
can show the honest "英文原文" label.

Phase 27 (qwen-plus 资源包优化): 翻译结果按 sha256(title|industry) 缓存在 Redis,
TTL 30 天。Backfill / reseed 场景同 title 多次翻译时直接命中,不再发请求。
任何 Redis 异常均优雅降级,不影响翻译功能。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from loguru import logger

_CJK_PATTERN = re.compile(r"[一-鿿]")
_JP_KO_HANGUL = re.compile(r"[぀-ヿ가-힯]")

# Phase 27: 翻译缓存命名空间与 TTL
_TRANS_CACHE_PREFIX = "llm:trans:"
_TRANS_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 天


def has_cjk(text: str | None) -> bool:
    """Return True if the string contains at least one CJK Unified Ideograph."""
    if not text:
        return False
    return bool(_CJK_PATTERN.search(text))


def looks_asian(text: str | None) -> bool:
    """Return True if the string contains CJK or Japanese/Korean characters.

    Used to decide whether a source needs translation.
    """
    if not text:
        return False
    return bool(_CJK_PATTERN.search(text) or _JP_KO_HANGUL.search(text))


def _trans_cache_key(title: str, industry: str | None) -> str:
    """sha256(lowercase title|lowercase industry) → 跨大小写命中。"""
    payload = f"{(title or '').lower().strip()}|{(industry or '').lower().strip()}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{_TRANS_CACHE_PREFIX}{h}"


def _trans_cache_get(title: str, industry: str | None) -> dict[str, str | None] | None:
    """读 Redis 缓存;Redis 故障或未启用时返回 None(调用方继续走 LLM)。"""
    try:
        from app.config import settings
        from app.services.resources import resources

        if not getattr(settings, "translation_cache_enabled", True):
            return None
        redis = resources.redis_client
        if redis is None:
            return None
        raw = redis.get(_trans_cache_key(title, industry))
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return {
            "name_cn": data.get("name_cn") or None,
            "industry_zh": data.get("industry_zh") or None,
        }
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("translation cache GET fault (fall-through): {}", exc)
        return None


def _trans_cache_set(
    title: str,
    industry: str | None,
    result: dict[str, str | None],
) -> None:
    """写 Redis 缓存;失败不影响主流程。"""
    try:
        from app.config import settings
        from app.services.resources import resources

        if not getattr(settings, "translation_cache_enabled", True):
            return
        # 仅缓存「有 name_cn」的有效结果,避免污染后续命中
        if not result.get("name_cn"):
            return
        redis = resources.redis_client
        if redis is None:
            return
        redis.set(
            _trans_cache_key(title, industry),
            json.dumps(result, ensure_ascii=False),
            ex=_TRANS_CACHE_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("translation cache SET fault (ignored): {}", exc)


async def translate_title_industry(
    llm_client: Any,
    *,
    title: str,
    industry: str | None = None,
) -> dict[str, str | None]:
    """Translate a non-CJK title/industry pair to simplified Chinese.

    Returns a dict with `name_cn` and `industry_zh` keys. The values are
    `None` when the source is already CJK (no translation needed) or the LLM
    is unavailable. The caller decides what to do with `None`.
    """
    title = (title or "").strip()
    industry = (industry or "").strip() or None

    if not title:
        return {"name_cn": None, "industry_zh": None}

    if has_cjk(title):
        return {"name_cn": title, "industry_zh": industry}

    # Phase 27: 先查 Redis 缓存(覆盖同 title 多次翻译)
    cached = _trans_cache_get(title, industry)
    if cached is not None:
        logger.debug("translation cache hit: title={!r}", title[:40])
        return cached

    prompt = (
        "You are a recruiter translating a job posting into Simplified Chinese.\n"
        "Respond ONLY as JSON: {\"name_cn\": \"...\", \"industry_zh\": \"...\"}.\n"
        "Rules: faithful translation, no extra commentary, no invented facts, "
        "keep proper nouns in their original spelling if ambiguous.\n"
        f"Original title: {title!r}\n"
        f"Original industry: {industry!r}\n"
    )

    try:
        raw = await llm_client.generate(
            prompt,
            json_mode=True,
            temperature=0.0,
        )
        import json as _json

        data = _json.loads(raw)
        name_cn = (data.get("name_cn") or "").strip() or None
        industry_zh = (data.get("industry_zh") or "").strip() or None
        if name_cn and not has_cjk(name_cn):
            # D8h fix: LLM 对专有名词/品牌岗位名返回原文（如 "Account Executive"）。
            # 原逻辑丢弃 → 岗位列表仍显示「英文原文」。改为把原文作为 name_cn 兜底，
            # 至少让岗位有显示名（后续可人工修正），前端不再标「英文原文」。
            # 仅当原文与 title 相同时才兜底（避免 LLM 返回无关英文被误存）。
            if name_cn.lower().strip() == (title or "").lower().strip():
                logger.info("translate_title_industry: LLM returned original name, using as fallback name_cn={!r}", name_cn)
                result_payload: dict[str, str | None] = {"name_cn": name_cn, "industry_zh": industry_zh}
                _trans_cache_set(title, industry, result_payload)
                return result_payload
            logger.warning("translate_title_industry: LLM returned non-CJK name_cn={!r}", name_cn)
            return {"name_cn": None, "industry_zh": None}
        result_payload = {"name_cn": name_cn, "industry_zh": industry_zh}
        _trans_cache_set(title, industry, result_payload)
        return result_payload
    except Exception as exc:  # noqa: BLE001 — fall back gracefully
        logger.warning("translate_title_industry failed: {}", exc)
        return {"name_cn": None, "industry_zh": None}
