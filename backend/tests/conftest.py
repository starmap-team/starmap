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


@pytest.fixture
async def db_session():
    """真实异步 DB session(供 seed/集成测试);PostgreSQL 不可用时跳过而非 error。

    seed 函数自身 commit(幂等),故此处不做 rollback;复用 app 的共享 session_factory。
    """
    from sqlalchemy import text

    from app.db.session import get_session_factory

    sm = get_session_factory()
    # 连接预检:不可用则 skip,避免集成测试在缺少 DB 的环境里 error。
    try:
        async with sm() as probe:
            await probe.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL 不可用,跳过集成测试: {exc}")
    async with sm() as session:
        yield session


@pytest.fixture
def require_db():
    """Sync guard: skip if PostgreSQL unreachable (for sync tests hitting real DB endpoints)."""
    import asyncio

    from sqlalchemy import text

    from app.db.session import get_session_factory

    async def _check() -> None:
        sm = get_session_factory()
        async with sm() as probe:
            await probe.execute(text("SELECT 1"))

    try:
        asyncio.run(_check())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL 不可用,跳过集成测试: {exc}")
