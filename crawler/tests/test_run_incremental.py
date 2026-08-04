"""Tests for crawler/scripts/run_incremental.py."""
from __future__ import annotations

from unittest.mock import patch

from crawler.scripts.run_incremental import _OPEN_SOURCES, _crawl_site, _spider_registry


class TestCrawlSite:
    """PLAN-005: _crawl_site 路由到真实开放源，未知源诚实返回空。"""

    def test_known_source_routes_to_spider(self) -> None:
        with patch(
            "crawler.spiders.arbeitnow.run_sync",
            return_value=[{"job_title": "Python Dev", "source_url": "https://arbeitnow.com/1"}],
        ) as mock_run:
            items = _crawl_site("arbeitnow", max_count=10)
            mock_run.assert_called_once_with(keyword="python", max_count=10)
            assert len(items) == 1
            assert items[0]["job_title"] == "Python Dev"

    def test_all_open_sources_registered(self) -> None:
        registry = _spider_registry()
        for site in _OPEN_SOURCES:
            assert site in registry, f"missing spider for {site}"
            assert callable(registry[site])

    def test_retired_source_returns_empty(self) -> None:
        # lagou/51job/bosszhipin 无对应 spider（已下线），必须诚实返回空而非崩溃
        for site in ("lagou", "51job", "bosszhipin"):
            assert _crawl_site(site, max_count=5) == []
