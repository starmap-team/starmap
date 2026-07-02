"""Tests for loop API endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.loop import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_loop_status_not_found():
    response = client.get("/loop/status/nonexistent-id")
    assert response.status_code == 404


def test_loop_history_empty():
    response = client.get("/loop/history")
    assert response.status_code == 200
    assert "items" in response.json()


def test_loop_run_validation_empty_jd():
    response = client.post("/loop/run", json={"jd_text": "", "target_position": "dev"})
    assert response.status_code == 422


def test_loop_run_validation_empty_target():
    response = client.post("/loop/run", json={"jd_text": "text", "target_position": ""})
    assert response.status_code == 422
