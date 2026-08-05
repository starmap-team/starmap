"""PLAN-003: RemoteOK spider 测试 (mock compliance.fetch)。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from crawler.spiders import remoteok

SAMPLE = [
    {"success": "Please note: this is not a job listing"},
    {
        "position": "Senior Backend Engineer",
        "company": "ACME Corp",
        "description": "<strong>Build</strong> APIs with Python.<br>FastAPI experience.",
        "apply_url": "https://remoteok.com/remote-jobs/abc",
        "salary_min": "80000",
        "salary_max": "120000",
        "date": "2026-07-31T05:02:54+00:00",
        "tags": ["python", "backend"],
    },
    {
        "position": "Data Analyst",
        "company": "Data Inc",
        "description": "Analyze data with SQL.",
        "apply_url": "https://remoteok.com/remote-jobs/def",
        "salary_min": None,
        "salary_max": None,
        "date": "",
        "tags": ["sql"],
    },
]


def _resp(status: int, payload) -> SimpleNamespace:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload)
    return SimpleNamespace(status_code=status, text=text)


class TestRunSync:
    @patch("crawler.spiders.remoteok.fetch")
    def test_happy_path_shapes_items(self, mock_fetch) -> None:
        mock_fetch.return_value = _resp(200, SAMPLE)
        items = remoteok.run_sync(keyword="python", max_count=5)
        assert len(items) == 2
        it = items[0]
        assert it["source_site"] == "remoteok"
        assert it["job_title"] == "Senior Backend Engineer"
        assert "Build APIs with Python. FastAPI experience." in it["clean_text"]
        assert it["salary_min"] == 80000
        assert it["salary_max"] == 120000
        assert it["publish_date"] == "2026-07-31"

    @patch("crawler.spiders.remoteok.fetch")
    def test_placeholder_index_zero_skipped(self, mock_fetch) -> None:
        """[0] 占位不产出职位。"""
        mock_fetch.return_value = _resp(200, SAMPLE)
        items = remoteok.run_sync()
        assert all(it["job_title"] != "" for it in items)
        assert len(items) == 2

    @patch("crawler.spiders.remoteok.fetch")
    def test_non_200_returns_empty(self, mock_fetch) -> None:
        mock_fetch.return_value = _resp(500, "")
        assert remoteok.run_sync() == []

    @patch("crawler.spiders.remoteok.fetch")
    def test_invalid_json_returns_empty(self, mock_fetch) -> None:
        mock_fetch.return_value = _resp(200, "not json")
        assert remoteok.run_sync() == []

    @patch("crawler.spiders.remoteok.fetch")
    def test_empty_description_skipped_honestly(self, mock_fetch) -> None:
        """空壳职位诚实跳过 (不编造)。"""
        data = [SAMPLE[0], {**SAMPLE[1], "description": "<p></p>"}]
        mock_fetch.return_value = _resp(200, data)
        assert remoteok.run_sync() == []

    @patch("crawler.spiders.remoteok.fetch")
    def test_max_count_limits(self, mock_fetch) -> None:
        mock_fetch.return_value = _resp(200, SAMPLE)
        items = remoteok.run_sync(max_count=1)
        assert len(items) == 1
