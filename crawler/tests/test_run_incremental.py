"""Tests for crawler/scripts/run_incremental.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from crawler.scripts.run_incremental import _crawl_site


class TestCrawlSite:
    def test_lagou_uses_signal_collection(self) -> None:
        """Verify lagou uses Scrapy signals to collect items."""
        with patch("scrapy.crawler.CrawlerProcess") as mock_process_cls:
            mock_process = MagicMock()
            mock_process_cls.return_value = mock_process

            mock_crawler = MagicMock()
            mock_process.create_crawler.return_value = mock_crawler

            # Simulate item_scraped signal being fired
            def simulate_crawl(*args, **kwargs):
                # Get the signal handler that was connected
                signal_handler = None
                for call in mock_crawler.signals.connect.call_args_list:
                    if call[1].get("signal"):
                        signal_handler = call[0][0]
                        break

                # Simulate Scrapy firing the signal with items
                if signal_handler:
                    signal_handler({"job_title": "Python Dev", "source_url": "https://lagou.com/1"}, None, None)
                    signal_handler({"job_title": "Java Dev", "source_url": "https://lagou.com/2"}, None, None)

            mock_process.start.side_effect = simulate_crawl

            items = _crawl_site("lagou", max_count=10)

            # Verify CrawlerProcess was created
            mock_process_cls.assert_called_once()
            # Verify create_crawler was called with LagouSpider
            mock_process.create_crawler.assert_called_once()
            # Verify signal was connected
            mock_crawler.signals.connect.assert_called_once()
            # Verify items were collected
            assert len(items) == 2
            assert items[0]["job_title"] == "Python Dev"
            assert items[1]["job_title"] == "Java Dev"

    def test_51job_uses_signal_collection(self) -> None:
        """Verify 51job uses Scrapy signals to collect items."""
        with patch("scrapy.crawler.CrawlerProcess") as mock_process_cls:
            mock_process = MagicMock()
            mock_process_cls.return_value = mock_process

            mock_crawler = MagicMock()
            mock_process.create_crawler.return_value = mock_crawler

            # Simulate item_scraped signal being fired
            def simulate_crawl(*args, **kwargs):
                signal_handler = None
                for call in mock_crawler.signals.connect.call_args_list:
                    if call[1].get("signal"):
                        signal_handler = call[0][0]
                        break

                if signal_handler:
                    signal_handler({"job_title": "Frontend Dev", "source_url": "https://51job.com/1"}, None, None)

            mock_process.start.side_effect = simulate_crawl

            items = _crawl_site("51job", max_count=5)

            # Verify signal-based collection works
            mock_crawler.signals.connect.assert_called_once()
            assert len(items) == 1
            assert items[0]["job_title"] == "Frontend Dev"

    def test_bosszhipin_uses_run_sync(self) -> None:
        """Verify bosszhipin uses run_sync and converts items to dict."""
        with patch("crawler.spiders.boss.run_sync") as mock_run_sync:
            mock_run_sync.return_value = [
                {"job_title": "Backend Dev", "source_url": "https://boss.com/1"},
                {"job_title": "DevOps", "source_url": "https://boss.com/2"},
            ]

            items = _crawl_site("bosszhipin", max_count=10)

            mock_run_sync.assert_called_once_with(keyword="python", max_count=10)
            assert len(items) == 2
            assert items[0]["job_title"] == "Backend Dev"
