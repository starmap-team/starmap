"""Tests for crawler/pipelines/incremental.py."""
from __future__ import annotations

from unittest.mock import patch

from crawler.pipelines.incremental import (
    IncrementalResult,
    check_incremental,
)


# ---------------------------------------------------------------------------
# IncrementalResult
# ---------------------------------------------------------------------------
class TestIncrementalResult:
    def test_defaults(self) -> None:
        r = IncrementalResult()
        assert r.total == 0
        assert r.inserted == 0
        assert r.url_duplicate == 0
        assert r.content_near_duplicate == 0
        assert r.failed == 0
        assert r.skipped_urls == []
        assert r.inserted_urls == []


# ---------------------------------------------------------------------------
# check_incremental
# ---------------------------------------------------------------------------
class TestCheckIncremental:
    @patch("crawler.pipelines.incremental.get_existing_hashes", return_value={})
    @patch("crawler.pipelines.incremental.get_existing_urls", return_value=set())
    def test_all_new_records_pass(self, _mock_urls, _mock_hashes) -> None:
        records = [
            {"source_url": "https://a.com/1", "clean_text": "Python 后端工程师 招聘"},
            {"source_url": "https://b.com/2", "clean_text": "Java 架构师 高级开发"},
        ]
        filtered, stats = check_incremental(records)
        assert stats.total == 2
        assert stats.inserted == 2
        assert stats.url_duplicate == 0
        assert len(filtered) == 2

    @patch("crawler.pipelines.incremental.get_existing_hashes", return_value={})
    @patch("crawler.pipelines.incremental.get_existing_urls", return_value={"https://a.com/1"})
    def test_url_duplicate_skipped(self, _mock_urls, _mock_hashes) -> None:
        records = [
            {"source_url": "https://a.com/1", "clean_text": "Python 后端"},
            {"source_url": "https://b.com/2", "clean_text": "Java 架构师"},
        ]
        filtered, stats = check_incremental(records)
        assert stats.total == 2
        assert stats.inserted == 1
        assert stats.url_duplicate == 1
        assert len(filtered) == 1
        assert filtered[0]["source_url"] == "https://b.com/2"

    @patch("crawler.pipelines.incremental.get_existing_hashes", return_value={})
    @patch("crawler.pipelines.incremental.get_existing_urls", return_value=set())
    def test_batch_internal_dedup(self, _mock_urls, _mock_hashes) -> None:
        # 两条几乎一样的内容
        records = [
            {"source_url": "https://a.com/1", "clean_text": "Python 后端工程师 招聘 要求三年经验"},
            {"source_url": "https://a.com/2", "clean_text": "Python 后端工程师 招聘 要求三年经验"},
        ]
        filtered, stats = check_incremental(records)
        assert stats.total == 2
        assert stats.content_near_duplicate == 1
        assert len(filtered) == 1

    @patch("crawler.pipelines.incremental.get_existing_hashes", return_value={})
    @patch("crawler.pipelines.incremental.get_existing_urls", return_value=set())
    def test_content_hash_updated(self, _mock_urls, _mock_hashes) -> None:
        records = [
            {"source_url": "https://a.com/1", "clean_text": "Python 后端工程师"},
        ]
        filtered, _stats = check_incremental(records)
        assert "content_hash" in filtered[0]
        assert len(filtered[0]["content_hash"]) == 64

    def test_no_skip_existing(self) -> None:
        records = [
            {"source_url": "https://a.com/1", "clean_text": "Python 后端"},
        ]
        filtered, stats = check_incremental(records, skip_existing_urls=False)
        assert stats.total == 1
        assert stats.inserted == 1
        assert len(filtered) == 1

    @patch("crawler.pipelines.incremental.get_existing_hashes", return_value={})
    @patch("crawler.pipelines.incremental.get_existing_urls", return_value=set())
    def test_empty_records(self, _mock_urls, _mock_hashes) -> None:
        filtered, stats = check_incremental([])
        assert stats.total == 0
        assert stats.inserted == 0
        assert len(filtered) == 0

    @patch("crawler.pipelines.incremental.get_existing_hashes", return_value={})
    @patch("crawler.pipelines.incremental.get_existing_urls", return_value=set())
    def test_no_clean_text_skips_simhash(self, _mock_urls, _mock_hashes) -> None:
        records = [
            {"source_url": "https://a.com/1"},
        ]
        filtered, stats = check_incremental(records)
        assert stats.total == 1
        assert stats.inserted == 1
        # content_hash 不会被设置（因为没有 clean_text）
        assert "content_hash" not in filtered[0]
