"""conftest.py：pytest 公共 fixture。"""
import pytest
from fastapi.testclient import TestClient

from app.main import _rate_buckets, app


@pytest.fixture(autouse=True)
def _clean_global_state():
    """确保每个测试后清理全局状态，防止跨测试污染。"""
    yield
    app.dependency_overrides.clear()
    _rate_buckets.clear()


@pytest.fixture
def client():
    """同步测试客户端（用 httpx）。"""
    with TestClient(app) as c:
        yield c
