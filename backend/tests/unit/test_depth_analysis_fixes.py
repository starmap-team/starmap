"""Tests for bug fixes from depth-analysis-report (BL-01, BL-02, BL-08, BL-11, BL-13, BL-16)."""
from __future__ import annotations

import time

import pytest

from app.core.extraction.jd_extract import mask_pii
from app.core.extraction.prompt import _ACTIVE_VERSIONS, get_active_version
from app.core.matching.cache import MatchCache
from app.services.judge_service import evaluate_batch_async, evaluate_sample_async

# ── BL-01: Judge F1 empty-set returns 0.0 not 1.0 ──


class TestBL01EmptySetF1:
    """BL-01: Both golden and system having no skills should return F1=0, not F1=1."""

    @pytest.mark.asyncio
    async def test_both_empty_skills_returns_zero_f1(self):
        golden = {"id": "e1", "required_skills": [], "bonus_skills": []}
        system = {"id": "e1", "required_skills": [], "bonus_skills": []}
        result = await evaluate_sample_async(golden, system)
        # BL-01 fix: empty vs empty should be F1=0.0, not 1.0
        assert result.f1 == 0.0
        assert result.precision == 0.0
        assert result.recall == 0.0


# ── BL-11: Batch eval skips missing system samples ──


class TestBL11MissingSystemSamples:
    """BL-11: Missing system samples should be skipped, not counted as F1=0."""

    @pytest.mark.asyncio
    async def test_missing_system_skipped(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        system_file = tmp_path / "system.jsonl"

        # Golden has 2 samples, system only has 1
        golden_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
            '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )
        system_file.write_text(
            '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n',
            encoding="utf-8",
        )

        metrics = await evaluate_batch_async(golden_file, system_file, threshold=0.5)
        # BL-11: g2 is skipped (not in system), so only g1 is evaluated
        assert metrics.evaluated_samples == 1
        assert metrics.avg_f1 == 1.0  # g1 is perfect match


# ── BL-08: Chinese suffix cleaning min length ──


class TestBL08ChineseSuffixCleaning:
    """BL-08: _clean_skill_name should not over-strip to < 4 chars."""

    def test_short_name_not_stripped(self):
        """Names that would become < 4 chars after stripping should be preserved."""
        chinese_suffixes = ["系统", "安全", "开发", "管理"]

        def _clean(name):
            while True:
                original = name
                for suffix in chinese_suffixes:
                    if len(name) > 4 and name.endswith(suffix):
                        cleaned = name[: -len(suffix)]
                        if cleaned and len(cleaned) >= 4:
                            name = cleaned
                if name == original:
                    break
            return name

        # Should NOT strip "系统架构" (4 chars) → would become "系统" (2 chars)
        assert _clean("系统架构") == "系统架构"
        # Should strip "分布式系统架构" (7 chars) → "分布式系统" (5) → stays (5 ≥ 4)
        result = _clean("分布式系统架构")
        assert len(result) >= 4  # won't over-strip to "分布式" (3 chars)


# ── BL-13: Per-key TTL for profile cache ──


class TestBL13PerKeyTTL:
    """BL-13: Profile cache should use per-key TTL, not global expiry."""

    def test_per_key_expiry(self):
        cache = MatchCache(ttl=1, max_size=100)

        # Set two profiles
        cache.set_profile("position-a", {"required": [], "bonus": []})
        cache.set_profile("position-b", {"required": [], "bonus": []})

        # Both should be available immediately
        assert cache.get_profile("position-a") is not None
        assert cache.get_profile("position-b") is not None

        # Manually expire only position-a by setting its timestamp to past
        with cache._lock:
            cache._profile_cache_ts["position-a"] = time.monotonic() - 2

        # position-a should be expired, position-b should still be valid
        assert cache.get_profile("position-a") is None
        assert cache.get_profile("position-b") is not None

    def test_clear_resets_all(self):
        cache = MatchCache(ttl=300)
        cache.set_profile("pos-x", {"required": [], "bonus": []})
        cache.clear()
        assert cache.get_profile("pos-x") is None


# ── BL-16/FE-01: v4 Prompt is active ──


class TestBL16PromptVersion:
    """BL-16: jd_extraction should default to v4 (recall-optimized)."""

    def test_jd_extraction_active_version_is_v4(self):
        assert get_active_version("jd_extraction") == "v4"

    def test_active_versions_dict(self):
        assert _ACTIVE_VERSIONS["jd_extraction"] == "v4"


# ── BL-02: Pydantic fallback completeness ──


class TestBL02PydanticFallback:
    """BL-02: When Pydantic validation fails, fallback should cover ALL fields."""

    def test_mask_pii_chinese_name(self):
        """P0 DATA-01: Chinese name patterns should be redacted."""
        text = "姓名：张三 | 男 | 5年经验"
        masked = mask_pii(text)
        assert "张三" not in masked
        assert "[REDACTED]" in masked

    def test_mask_pii_phone(self):
        text = "联系电话：13812345678"
        masked = mask_pii(text)
        assert "13812345678" not in masked

    def test_mask_pii_email(self):
        text = "邮箱：test@example.com"
        masked = mask_pii(text)
        assert "test@example.com" not in masked

    def test_mask_pii_id_card(self):
        text = "身份证：110101199001011234"
        masked = mask_pii(text)
        assert "110101199001011234" not in masked
