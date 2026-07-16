"""conftest.py：pytest 公共 fixture。"""
import pytest
from fastapi.testclient import TestClient

from app.main import _rate_buckets, app


async def _noop_sse_check(client_ip: str) -> None:
    """No-op SSE connection check — prevents global counter pollution in tests."""
    pass


@pytest.fixture(autouse=True)
def _clean_global_state(monkeypatch):
    """确保每个测试后清理全局状态，防止跨测试污染。

    - 清理 FastAPI dependency_overrides
    - 清理 rate limiter buckets
    - 绕过 SSE 连接数限制（避免全局计数器污染测试）
    """
    # Bypass SSE connection limit check in all tests
    import app.dependencies as dep_mod
    monkeypatch.setattr(dep_mod, "_sse_connect_check", _noop_sse_check)
    dep_mod._sse_ip_connections.clear()
    dep_mod._sse_global_connections = 0

    yield

    app.dependency_overrides.clear()
    _rate_buckets.clear()
    dep_mod._sse_ip_connections.clear()
    dep_mod._sse_global_connections = 0


@pytest.fixture
def client():
    """同步测试客户端（用 httpx）。"""
    with TestClient(app) as c:
        yield c
