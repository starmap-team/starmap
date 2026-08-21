"""Translation cache unit tests (Phase 27).

覆盖:
- CJK 输入短路(CJK 不发请求不写缓存)
- 空 title 短路
- Redis 命中:不调用 llm_client.generate,直接返回缓存。
- Redis 未命中:写入缓存,下次命中。
- 关闭开关:完全旁路缓存,直接走 LLM。
- Redis 故障:GET/SET 抛异常 → 不传播。
- 大小写不敏感:same title 不同大小写命中同一 key。
- 仅缓存有效结果 (name_cn 非 None)。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.core.extraction import translation


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "translation_cache_enabled", True, raising=False,
    )


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock(name="fake_redis_client")
    fake.get.return_value = None
    fake.set.return_value = True
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake),
    )
    return fake


# ─────────────────────────────────────────────────────────────────
# CJK / 空短路(已有行为,不回归)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cjk_title_short_circuits(fake_redis: MagicMock) -> None:
    llm = MagicMock()
    llm.generate = AsyncMock(side_effect=AssertionError("should not be called"))
    result = await translation.translate_title_industry(llm, title="后端工程师")
    assert result == {"name_cn": "后端工程师", "industry_zh": None}
    llm.generate.assert_not_called()
    fake_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_empty_title_returns_none(fake_redis: MagicMock) -> None:
    llm = MagicMock()
    llm.generate = AsyncMock(side_effect=AssertionError("should not be called"))
    result = await translation.translate_title_industry(llm, title="")
    assert result == {"name_cn": None, "industry_zh": None}
    llm.generate.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# Cache key
# ─────────────────────────────────────────────────────────────────


def test_cache_key_case_insensitive() -> None:
    a = translation._trans_cache_key("Backend Engineer", "Internet")
    b = translation._trans_cache_key("backend engineer", "internet")
    assert a == b


def test_cache_key_includes_industry() -> None:
    a = translation._trans_cache_key("Backend Engineer", "Internet")
    b = translation._trans_cache_key("Backend Engineer", "FinTech")
    assert a != b


def test_cache_key_handles_none_industry() -> None:
    # 不能因为 None/"" 差异导致不同 key
    assert (
        translation._trans_cache_key("Backend Engineer", None)
        == translation._trans_cache_key("Backend Engineer", "")
    )


# ─────────────────────────────────────────────────────────────────
# 命中路径
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_skips_llm(fake_redis: MagicMock) -> None:
    fake_redis.get.return_value = json_dumps(
        {"name_cn": "后端工程师", "industry_zh": "互联网/IT"},
    )
    llm = MagicMock()
    llm.generate = AsyncMock(side_effect=AssertionError("should not be called"))

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result == {"name_cn": "后端工程师", "industry_zh": "互联网/IT"}
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_returns_none_industry_zh_correctly(fake_redis: MagicMock) -> None:
    fake_redis.get.return_value = json_dumps(
        {"name_cn": "后端工程师", "industry_zh": None},
    )
    llm = MagicMock()
    llm.generate = AsyncMock(side_effect=AssertionError("should not be called"))

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry=None,
    )
    assert result == {"name_cn": "后端工程师", "industry_zh": None}


# ─────────────────────────────────────────────────────────────────
# 未命中 → 调 LLM → 写缓存
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_miss_calls_llm_and_writes(fake_redis: MagicMock) -> None:
    fake_redis.get.return_value = None  # miss
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"name_cn": "后端工程师", "industry_zh": "互联网/IT"}',
    )

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result == {"name_cn": "后端工程师", "industry_zh": "互联网/IT"}
    llm.generate.assert_awaited_once()
    fake_redis.set.assert_called_once()
    call_kwargs = fake_redis.set.call_args.kwargs
    assert call_kwargs["ex"] == 30 * 24 * 3600


@pytest.mark.asyncio
async def test_cache_skipped_for_empty_result(fake_redis: MagicMock) -> None:
    """LLM 返回无 name_cn 时不写缓存(避免污染命中)。"""
    fake_redis.get.return_value = None
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"name_cn": null, "industry_zh": null}',
    )

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result == {"name_cn": None, "industry_zh": None}
    fake_redis.set.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# 关闭开关
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_disabled_skips_redis_and_uses_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "translation_cache_enabled", False, raising=False,
    )
    fake_redis = MagicMock()
    fake_redis.get.return_value = json_dumps(
        {"name_cn": "不应返回", "industry_zh": None},
    )
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake_redis),
    )

    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"name_cn": "后端工程师", "industry_zh": "互联网/IT"}',
    )

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result["name_cn"] == "后端工程师"
    fake_redis.get.assert_not_called()
    fake_redis.set.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# Redis 故障优雅降级
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_get_fault_falls_through_to_llm(fake_redis: MagicMock) -> None:
    fake_redis.get.side_effect = ConnectionError("redis down")
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"name_cn": "后端工程师", "industry_zh": "互联网/IT"}',
    )

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result == {"name_cn": "后端工程师", "industry_zh": "互联网/IT"}


@pytest.mark.asyncio
async def test_redis_set_fault_does_not_break(fake_redis: MagicMock) -> None:
    fake_redis.get.return_value = None
    fake_redis.set.side_effect = ConnectionError("redis down")
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"name_cn": "后端工程师", "industry_zh": "互联网/IT"}',
    )

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result == {"name_cn": "后端工程师", "industry_zh": "互联网/IT"}


@pytest.mark.asyncio
async def test_redis_none_falls_through(fake_redis: MagicMock) -> None:
    # 上面 fixture 给的是 fake redis;显式置 None 验证 redis 未初始化
    import app.services.resources as res_mod
    res_mod.resources.redis_client = None

    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"name_cn": "后端工程师", "industry_zh": "互联网/IT"}',
    )

    result = await translation.translate_title_industry(
        llm, title="Backend Engineer", industry="Internet",
    )
    assert result["name_cn"] == "后端工程师"


# ─────────────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────────────


def json_dumps(obj: object) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
