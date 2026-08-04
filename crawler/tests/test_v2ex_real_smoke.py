"""v2ex_remote spider smoke tests — covers the 3 failure modes that historically
caused silent 0-record crawl runs:

1. HTTP 200 with valid JSON → returns items with all required fields
2. urlopen timeout / network error → graceful degradation, returns partial/empty list
3. HTTP 200 with malformed JSON body → caught, returns partial/empty list

These tests do NOT hit the real network — they patch ``urllib.request.urlopen``
so they are deterministic and CI-safe.
"""
from __future__ import annotations

import io
import json
from collections.abc import Sequence
from typing import Any
from unittest.mock import MagicMock

import pytest

# Stage 2.2: conftest mocks crawler.spiders as a whole. To test the real
# v2ex_remote module we must bypass that mock by importing the file directly
# via importlib, otherwise `import crawler.spiders.v2ex_remote` would return
# a MagicMock and AttributeError on attribute access.
import importlib.util
from pathlib import Path

_V2EX_PATH = (
    Path(__file__).resolve().parents[1]
    / "spiders"
    / "v2ex_remote.py"
)


def _load_real_v2ex_module():
    """Load crawler/spiders/v2ex_remote.py bypassing the conftest MagicMock.

    The spider module has zero persistence imports, so it is safe to load
    in isolation; we only need to defeat the parent-package mock.
    """
    spec = importlib.util.spec_from_file_location("_v2ex_under_test", _V2EX_PATH)
    assert spec is not None and spec.loader is not None, "v2ex_remote.py not found"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures: simulate urlopen responses
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal context-manager mimicking http.client.HTTPResponse."""

    def __init__(self, payload: bytes) -> None:
        self._buf = io.BytesIO(payload)

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _make_urlopen(return_map: dict[str, bytes | Exception]):
    """Return a fake urlopen that dispatches by URL substring match."""

    def _fake_urlopen(req, timeout=15):  # noqa: ANN001
        url = getattr(req, "full_url", str(req))
        for needle, payload in return_map.items():
            if needle in url:
                if isinstance(payload, Exception):
                    raise payload
                return _FakeResponse(payload)
        # Default: empty but valid JSON list
        return _FakeResponse(b"[]")

    return _fake_urlopen


# ---------------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def v2ex():
    return _load_real_v2ex_module()


# ---------------------------------------------------------------------------
# Scenario 1: HTTP 200 + valid V2EX + Remotive payload
# ---------------------------------------------------------------------------


def test_run_sync_happy_path(v2ex, monkeypatch):
    """Valid 200 + valid JSON → returns ≥1 item per source with all required keys."""
    v2ex_payload = [
        {
            "id": 12345,
            "title": "Python 后端工程师",
            "url": "https://www.v2ex.com/t/12345",
            "content": "FastAPI / PostgreSQL / Redis",
            "content_rendered": "<p>FastAPI / PostgreSQL</p>",
            "created": 1700000000,
        }
    ]
    remotive_payload = {
        "jobs": [
            {
                "title": "Senior Python Engineer",
                "url": "https://remotive.com/jobs/1",
                "company_name": "Acme",
                "description": "Python backend for SaaS platform.",
                "candidate_required_location": "Remote",
                "publication_date": "2026-07-01",
            }
        ]
    }
    payload_map = {
        "v2ex.com": json.dumps(v2ex_payload).encode(),
        "remotive.com": json.dumps(remotive_payload).encode(),
    }
    monkeypatch.setattr(v2ex.urllib.request, "urlopen", _make_urlopen(payload_map))

    items = v2ex.run_sync(keyword="python", max_count=5)

    assert isinstance(items, list)
    assert len(items) >= 1
    required_fields = {
        "source_site", "source_url", "raw_html", "clean_text",
        "job_title", "company", "salary_min", "salary_max",
        "location", "publish_date", "content_hash",
    }
    for it in items:
        missing = required_fields - set(it.keys())
        assert not missing, f"item missing fields: {missing}"
        assert it["content_hash"], "content_hash must be non-empty"
        assert it["source_site"] in {"v2ex", "remotive"}, f"unexpected source_site: {it['source_site']}"


# ---------------------------------------------------------------------------
# Scenario 2: network timeout / unreachable
# ---------------------------------------------------------------------------


def test_run_sync_handles_timeout(v2ex, monkeypatch):
    """Both endpoints raise OSError (timeout/unreachable) → returns empty list, no exception."""
    import socket

    timeout_err = socket.timeout("simulated timeout")

    def _always_raise(req, timeout=15):  # noqa: ANN001
        raise timeout_err

    monkeypatch.setattr(v2ex.urllib.request, "urlopen", _always_raise)

    items = v2ex.run_sync(keyword="python", max_count=3)
    # Current contract: return whatever was collected so far (possibly empty),
    # never propagate the exception. This is what executor.execute_crawl expects.
    assert isinstance(items, list)


# ---------------------------------------------------------------------------
# Scenario 3: malformed JSON body (HTTP 200 but payload is not valid JSON)
# ---------------------------------------------------------------------------


def test_run_sync_handles_malformed_json(v2ex, monkeypatch):
    """Endpoints return 200 but body is not JSON → caught, returns empty/partial list."""
    payload_map = {
        "v2ex.com": b"<html>502 Bad Gateway</html>",
        "remotive.com": b"::not-json::",
    }
    monkeypatch.setattr(v2ex.urllib.request, "urlopen", _make_urlopen(payload_map))

    items = v2ex.run_sync(keyword="python", max_count=3)
    # Even with both endpoints failing JSON parse, run_sync must not crash.
    assert isinstance(items, list)


# ---------------------------------------------------------------------------
# Scenario 4: partial degradation (v2ex up, remotive down)
# ---------------------------------------------------------------------------


def test_run_sync_partial_degradation(v2ex, monkeypatch):
    """v2ex returns items, remotive times out → still returns the v2ex items."""
    import socket

    v2ex_payload = [
        {"id": 999, "title": "Go 后端", "content": "golang", "url": "https://v2ex.com/t/999", "created": 1700000000}
    ]
    payload_map = {
        "v2ex.com": json.dumps(v2ex_payload).encode(),
        "remotive.com": socket.timeout("remotive down"),
    }
    monkeypatch.setattr(v2ex.urllib.request, "urlopen", _make_urlopen(payload_map))

    items = v2ex.run_sync(keyword="go", max_count=2)
    assert len(items) >= 1
    assert items[0]["source_site"] == "v2ex"
    assert items[0]["job_title"] == "Go 后端"