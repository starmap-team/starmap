"""Tests for FastAPI dependencies."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_has_health():
    """Just accessing the app verifies the dependency injection setup."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_app_root_health():
    resp = client.get("/health")
    assert resp.status_code == 200
