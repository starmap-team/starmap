"""健康检查冒烟测试。

验证：应用能启动、/health 返回 200。
这是 CI 的最基本门禁（§17.8 每日集成）。
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import get_current_user, get_db_session
from app.main import app

# ── Fake session for DB override ──

_mock_session = AsyncMock()
_mock_session.execute = AsyncMock(return_value=AsyncMock(
    scalar=AsyncMock(return_value=0),
    scalars=AsyncMock(return_value=AsyncMock(all=AsyncMock(return_value=[]))),
))


async def _override_db():
    yield _mock_session


_MOCK_USER = {"sub": "dev", "role": "admin", "username": "developer"}


@pytest.fixture(autouse=True)
def _setup_overrides():
    """Override auth + DB for all health tests."""
    app.dependency_overrides[get_current_user] = lambda: _MOCK_USER
    app.dependency_overrides[get_db_session] = _override_db
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_v1_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_detail_ok(client):
    """D-09: /health/detail 返回 200 含 services(4) + llm_keys(3 bool) + demo_data。"""
    resp = client.get("/health/detail")
    assert resp.status_code == 200
    body = resp.json()

    # services: 4 个服务 ping 状态（值可能 not_initialized，仅断言 key 存在）
    assert "services" in body
    for svc in ("neo4j", "postgres", "redis", "ollama"):
        assert svc in body["services"], f"missing service: {svc}"

    # llm_keys: 3 个 LLM key 布尔值
    assert "llm_keys" in body
    for key in ("mimo", "deepseek", "xunfei"):
        assert key in body["llm_keys"], f"missing llm_key: {key}"
        assert isinstance(body["llm_keys"][key], bool)

    # demo_data: review_queue_seeded(bool) + pipeline_runs_count(int)
    assert "demo_data" in body
    assert isinstance(body["demo_data"]["review_queue_seeded"], bool)
    assert isinstance(body["demo_data"]["pipeline_runs_count"], int)


def test_health_detail_no_key_leak(client):
    """D-05/T-08-05: /health/detail 不得泄露任何 API key 实际值。"""
    resp = client.get("/health/detail")
    assert resp.status_code == 200
    body_text = json.dumps(resp.json(), ensure_ascii=False)

    for key_value in (
        settings.mimo_api_key,
        settings.deepseek_api_key,
        settings.xunfei_api_key,
    ):
        # 空字符串自动通过（无值可泄露）；非空时必须不出现在响应中
        if key_value:
            assert key_value not in body_text, "API key value leaked in /health/detail"
