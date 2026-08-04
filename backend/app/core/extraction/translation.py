"""English → Chinese translation hook for non-CJK JD sources (Phase 15 / I18N-01).

When a JD's title/industry is detected as non-CJK (English), we ask the LLM to
provide a Chinese version that is then stored in `position_records.name_cn` and
`industry_zh` (separate columns). The original fields are kept intact so we don't
lose the source language.

Failure mode: if the LLM errors out, we fall back to using the original text
as `name_cn` and tag the row with `name_translated_by='original'` so the frontend
can show the honest "英文原文" label.
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

_CJK_PATTERN = re.compile(r"[一-鿿]")
_JP_KO_HANGUL = re.compile(r"[぀-ヿ가-힯]")


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
            # Defensive: LLM returned English or empty. Fall back.
            logger.warning("translate_title_industry: LLM returned non-CJK name_cn={!r}", name_cn)
            return {"name_cn": None, "industry_zh": None}
        return {"name_cn": name_cn, "industry_zh": industry_zh}
    except Exception as exc:  # noqa: BLE001 — fall back gracefully
        logger.warning("translate_title_industry failed: {}", exc)
        return {"name_cn": None, "industry_zh": None}
