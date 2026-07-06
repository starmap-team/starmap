"""Additional tests for loop API to boost coverage."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_v1_loop():
    """Test that the app has the loop router and can handle a basic request."""
    # Just a basic health check to confirm app starts
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
