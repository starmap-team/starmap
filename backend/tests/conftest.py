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

    # P1 fix (functional-review 2026-08-13): 禁用 lifespan 后台 cron 扫描任务。
    # 测试 patch `app.services.resources.resources` 为 mock 期间，cron_scanner_loop
    # 首次迭代（last_reconcile_at is None）会调用 init_resources() → 把真实
    # Neo4j driver 写回被 patch 的 mock → learning/evolution 测试偶发失败
    # （flaky，全量 ~5min 长跑触发率更高）。测试不依赖定时调度，patch 为
    # no-op 安全（cron 调度逻辑有独立单测 test_cron_scheduler.py）。
    # 必须在 yield 之前（setup 区）patch，测试运行期间才生效。
    import app.core.pipeline.cron_scheduler as _cron_mod

    async def _noop_cron_scanner_loop(interval_seconds: int = 60) -> None:
        """测试期间 no-op：不扫描、不 reconcile、不调 init_resources。"""
        return

    monkeypatch.setattr(_cron_mod, "cron_scanner_loop", _noop_cron_scanner_loop)

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
