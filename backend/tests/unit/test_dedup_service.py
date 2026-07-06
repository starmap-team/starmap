"""Unit tests for app.services.dedup_service — SimHash-based deduplication."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.dedup_service import (
    _char_ngrams,
    _content_hash,
    dedup_jd_records,
    hamming_distance,
    is_near_duplicate,
    simhash,
 )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeJD:
    """Minimal JD record for testing."""

    clean_text: str
    source_url: str = ""


# ---------------------------------------------------------------------------
# _char_ngrams
# ---------------------------------------------------------------------------


class TestCharNgrams:
    def test_basic_trigrams(self):
        grams = _char_ngrams("abcde", n=3)
        assert grams == ["abc", "bcd", "cde"]

    def test_shorter_than_n(self):
        grams = _char_ngrams("ab", n=3)
        assert grams == ["ab"]

    def test_empty_string(self):
        assert _char_ngrams("", n=3) == []

    def test_whitespace_normalised(self):
        grams = _char_ngrams("a  b", n=3)
        # "a b" -> ["a b"]
        assert grams == ["a b"]

    def test_case_insensitive(self):
        assert _char_ngrams("ABC", n=3) == _char_ngrams("abc", n=3)


# ---------------------------------------------------------------------------
# simhash
# ---------------------------------------------------------------------------


class TestSimhash:
    def test_consistent_hash(self):
        text = "Python后端开发工程师，负责微服务架构设计与开发"
        h1 = simhash(text)
        h2 = simhash(text)
        assert h1 == h2

    def test_empty_text_returns_zero(self):
        assert simhash("") == 0

    def test_none_like_text_returns_zero(self):
        assert simhash("") == 0

    def test_different_texts_different_hashes(self):
        h1 = simhash("前端开发工程师，精通React和Vue框架")
        h2 = simhash("后端开发工程师，精通Python和Go语言")
        assert h1 != h2

    def test_similar_texts_close_hashes(self):
        """Similar JDs should have a small Hamming distance relative to random texts."""
        text_a = "我们需要一位Python高级工程师加入团队，负责后端微服务架构设计与开发"
        text_b = "我们需要一位Python高级工程师加入团队，负责后端微服务架构设计与开发。"
        h1 = simhash(text_a)
        h2 = simhash(text_b)
        # A single trailing character change should produce a small distance
        assert hamming_distance(h1, h2) <= 5

    def test_hash_bits_parameter(self):
        h64 = simhash("test text", hash_bits=64)
        h32 = simhash("test text", hash_bits=32)
        # 32-bit hash should fit in 32 bits
        assert h32 < (1 << 32)
        # 64-bit hash may exceed 32 bits
        assert h64 >= 0


# ---------------------------------------------------------------------------
# hamming_distance
# ---------------------------------------------------------------------------


class TestHammingDistance:
    def test_identical_hashes(self):
        assert hamming_distance(0b1111, 0b1111) == 0

    def test_all_bits_different(self):
        assert hamming_distance(0b0000, 0b1111) == 4

    def test_one_bit_different(self):
        assert hamming_distance(0b1010, 0b1011) == 1

    def test_zero_hashes(self):
        assert hamming_distance(0, 0) == 0


# ---------------------------------------------------------------------------
# is_near_duplicate
# ---------------------------------------------------------------------------


class TestIsNearDuplicate:
    def test_identical_is_near_dup(self):
        h = simhash("some text here")
        assert is_near_duplicate(h, h) is True

    def test_very_similar_texts_near_dup(self):
        """Texts differing only by a trailing character should be near-duplicate.

        Character 3-gram SimHash is sensitive to short texts; use a longer
        passage so that a single-character change produces distance <= 3.
        """
        base = "我们需要一位Python高级工程师加入团队，负责后端微服务的架构设计与开发工作，要求五年以上经验"
        h1 = simhash(base)
        h2 = simhash(base + "。")
        # A single trailing character on a long text should be within threshold 3
        assert is_near_duplicate(h1, h2, threshold=3) is True

    def test_very_different_texts(self):
        h1 = simhash("前端开发工程师，精通React和Vue框架，负责用户界面开发")
        h2 = simhash("销售经理，负责华南区域客户拓展和团队管理，需出差")
        # Default threshold is 3; very different texts should exceed it
        assert is_near_duplicate(h1, h2, threshold=3) is False

    def test_custom_threshold(self):
        h1 = simhash("Python工程师")
        h2 = simhash("Java工程师")
        dist = hamming_distance(h1, h2)
        # With a very high threshold, they should match
        assert is_near_duplicate(h1, h2, threshold=64) is True
        # With threshold below the distance, they should not
        if dist > 0:
            assert is_near_duplicate(h1, h2, threshold=0) is False


# ---------------------------------------------------------------------------
# _content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_deterministic(self):
        h1 = _content_hash("hello")
        h2 = _content_hash("hello")
        assert h1 == h2

    def test_different_inputs(self):
        h1 = _content_hash("hello")
        h2 = _content_hash("world")
        assert h1 != h2

    def test_sha256_length(self):
        h = _content_hash("test")
        assert len(h) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# dedup_jd_records
# ---------------------------------------------------------------------------


class TestDedupJdRecords:
    @pytest.mark.asyncio
    async def test_empty_input(self):
        unique, dups = await dedup_jd_records([])
        assert unique == []
        assert dups == []

    @pytest.mark.asyncio
    async def test_all_unique(self):
        records = [
            FakeJD("Python后端开发工程师，负责微服务架构"),
            FakeJD("前端开发工程师，精通React和Vue"),
            FakeJD("数据分析师，熟悉SQL和Python"),
        ]
        unique, dups = await dedup_jd_records(records)
        assert len(unique) == 3
        assert len(dups) == 0

    @pytest.mark.asyncio
    async def test_exact_duplicates(self):
        records = [
            FakeJD("Python开发工程师"),
            FakeJD("Python开发工程师"),  # exact duplicate
        ]
        unique, dups = await dedup_jd_records(records)
        assert len(unique) == 1
        assert len(dups) == 1

    @pytest.mark.asyncio
    async def test_fuzzy_duplicates_with_high_threshold(self):
        """Near-duplicate JDs with small wording differences caught at higher threshold."""
        # These texts differ by one character ("5" vs "3") in a longer passage
        records = [
            FakeJD("我们需要一位Python高级工程师加入团队，负责后端微服务的架构设计与开发工作"),
            FakeJD("我们需要一位Python高级工程师加入团队，负责后端微服务的架构设计与开发工作。"),
        ]
        unique, dups = await dedup_jd_records(records, threshold=5)
        assert len(unique) == 1
        assert len(dups) == 1

    @pytest.mark.asyncio
    async def test_mixed_unique_and_duplicate(self):
        records = [
            FakeJD("Python后端开发，5年经验，Django"),
            FakeJD("Python后端开发，5年经验，Django"),  # exact duplicate of first
            FakeJD("前端开发工程师，精通React"),
        ]
        unique, dups = await dedup_jd_records(records)
        assert len(unique) == 2
        assert len(dups) == 1

    @pytest.mark.asyncio
    async def test_custom_text_getter(self):
        @dataclass
        class CustomRecord:
            description: str

        records = [
            CustomRecord("Python开发"),
            CustomRecord("Python开发"),
        ]
        unique, dups = await dedup_jd_records(
            records,
            text_getter=lambda r: r.description,
        )
        assert len(unique) == 1
        assert len(dups) == 1

    @pytest.mark.asyncio
    async def test_with_redis_client(self):
        """Test that a mock Redis client is used for exact dedup."""
        records = [
            FakeJD("unique jd text one"),
            FakeJD("unique jd text two"),
            FakeJD("unique jd text one"),  # exact duplicate
        ]

        class MockRedis:
            def __init__(self):
                self._store: dict[str, str] = {}

            async def exists(self, key: str) -> bool:
                return key in self._store

            async def setex(self, key: str, ttl: int, value: str) -> None:
                self._store[key] = value

        mock_redis = MockRedis()
        unique, dups = await dedup_jd_records(records, redis_client=mock_redis)
        assert len(unique) == 2
        assert len(dups) == 1

    @pytest.mark.asyncio
    async def test_redis_persists_across_calls(self):
        """Exact dedup via Redis should catch duplicates across batches."""

        class MockRedis:
            def __init__(self):
                self._store: dict[str, str] = {}

            async def exists(self, key: str) -> bool:
                return key in self._store

            async def setex(self, key: str, ttl: int, value: str) -> None:
                self._store[key] = value

        mock_redis = MockRedis()

        batch1 = [FakeJD("Python开发工程师")]
        _, _ = await dedup_jd_records(batch1, redis_client=mock_redis)

        batch2 = [FakeJD("Python开发工程师")]  # same text, different object
        unique, dups = await dedup_jd_records(batch2, redis_client=mock_redis)
        assert len(unique) == 0
        assert len(dups) == 1
