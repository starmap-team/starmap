"""Tests for Phase 15-01 spider integrations.

Tests 4 spiders: arbeitnow, jobicy, weworkremotely, himalayas.
Uses mocking to avoid network dependency in CI.
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from crawler.spiders.arbeitnow import run_sync as arbeitnow_sync
from crawler.spiders.himalayas import run_sync as himalayas_sync
from crawler.spiders.jobicy import run_sync as jobicy_sync
from crawler.spiders.weworkremotely import run_sync as wwr_sync


# ── Arbeitnow ─────────────────────────────────────────────────────────


def test_arbeitnow_parses_valid_response():
    """Arbeitnow API returns {data: [...]} — verify field mapping."""
    fake_data = {
        "data": [
            {
                "slug": "test-slug-1",
                "title": "Python Engineer",
                "company_name": "TestCo",
                "description": "Build Python services",
                "url": "https://arbeitnow.com/jobs/1",
                "created_at": 1700000000,  # Unix timestamp
                "remote": True,
                "location": "Berlin",
            }
        ]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        items = arbeitnow_sync("python", 5)

    assert len(items) == 1
    item = items[0]
    assert item["source_site"] == "arbeitnow"
    assert item["job_title"] == "Python Engineer"
    assert item["company"] == "TestCo"
    assert item["clean_text"] == "Build Python services"
    assert "publish_date" in item
    assert item["location"] == "Berlin (远程)"
    expected_hash = hashlib.sha256(b"test-slug-1Build Python services").hexdigest()
    assert item["content_hash"] == expected_hash


def test_arbeitnow_handles_network_failure():
    """Network error returns empty list, no exception."""
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        items = arbeitnow_sync("python", 5)
    assert items == []


def test_arbeitnow_handles_string_created_at():
    """Some API responses may have string dates — should work."""
    fake_data = {
        "data": [
            {
                "slug": "s2",
                "title": "Backend",
                "company_name": "C2",
                "description": "desc",
                "url": "https://example.com/2",
                "created_at": "2026-01-15T00:00:00",
                "remote": False,
                "location": "Remote",
            }
        ]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        items = arbeitnow_sync("python", 5)
    assert items[0]["publish_date"] == "2026-01-15"


# ── Jobicy ────────────────────────────────────────────────────────────


def test_jobicy_parses_new_format():
    """Jobicy API now uses 'jobs' key (not 'jobList')."""
    fake_data = {
        "apiVersion": "2.0",
        "jobCount": 1,
        "jobs": [
            {
                "id": "abc123",
                "jobTitle": "Senior Python Dev",
                "companyName": "RemoteCo",
                "jobExcerpt": "We are hiring",
                "url": "https://jobicy.com/jobs/abc123",
                "pubDate": "2026-07-15",
                "jobGeo": "Worldwide",
            }
        ],
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        items = jobicy_sync("python", 5)

    assert len(items) == 1
    assert items[0]["source_site"] == "jobicy"
    assert items[0]["job_title"] == "Senior Python Dev"
    assert items[0]["publish_date"] == "2026-07-15"


def test_jobicy_falls_back_to_joblist():
    """If 'jobs' missing, fall back to 'jobList' (legacy)."""
    fake_data = {"jobList": [{"id": "1", "jobTitle": "T", "url": "u"}]}
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        items = jobicy_sync("python", 5)
    assert len(items) == 1


# ── WeWorkRemotely ────────────────────────────────────────────────────


def test_wwr_parses_rss():
    """WWR RSS title format: 'Company: Position'."""
    xml_data = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Tether: AI Engineer</title>
      <link>https://weworkremotely.com/jobs/1</link>
      <description>Work on AI</description>
      <pubDate>Mon, 15 Jul 2026</pubDate>
    </item>
    <item>
      <title>Plain Title No Colon</title>
      <link>https://weworkremotely.com/jobs/2</link>
      <description>Work on something</description>
    </item>
  </channel>
</rss>
"""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = xml_data.encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        items = wwr_sync("", 10)

    assert len(items) == 2
    assert items[0]["company"] == "Tether"
    assert items[0]["job_title"] == "AI Engineer"
    assert items[0]["source_site"] == "weworkremotely"
    # Second item: no colon → entire title becomes position
    assert items[1]["company"] == ""
    assert items[1]["job_title"] == "Plain Title No Colon"


def test_wwr_handles_invalid_xml():
    """Invalid XML → empty list, no crash."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<not-valid-xml>"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        items = wwr_sync("", 10)
    assert items == []


# ── Himalayas ──────────────────────────────────────────────────────────


def test_himalayas_returns_empty():
    """Himalayas API is broken (404), always returns empty."""
    items = himalayas_sync("python", 5)
    assert items == []


# ── Integration sanity check ──────────────────────────────────────────


def test_all_spiders_return_list_type():
    """All spiders return list[dict] even on errors."""
    for fn in [arbeitnow_sync, jobicy_sync, wwr_sync, himalayas_sync]:
        with patch("urllib.request.urlopen", side_effect=Exception("net")):
            result = fn("python", 3)
        assert isinstance(result, list)
        assert result == []