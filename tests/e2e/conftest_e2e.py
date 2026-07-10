"""PIPE-04 E2E 测试 fixtures。

提供：
- backend_url / frontend_url: dev server URL（默认 http://localhost:8000 / :5173）
- test_tag: 隔离用的 run_id tag
- trigger_pipeline_sync: 同步触发完整 pipeline run 并等待主阶段完成
"""
import asyncio
import os
import time
import uuid

import httpx
import pytest


@pytest.fixture(scope="session")
def backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def test_tag() -> str:
    """本测试套件隔离用的 run_id tag，用于检索 Neo4j 中本测试产生的节点。"""
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def trigger_pipeline_sync():
    """同步触发完整 pipeline run 并等待主阶段完成（轮询 status 最多 5 分钟）。

    使用方式（pytest test）：
        def test_something(trigger_pipeline_sync, backend_url):
            result = trigger_pipeline_sync(backend_url)
            assert result.get("status") in ("completed", "failed")
    """

    async def _trigger_and_wait(backend_url: str, timeout_s: int = 300) -> dict:
        async with httpx.AsyncClient(base_url=backend_url, timeout=10) as client:
            r = await client.post(
                "/api/v1/pipeline/trigger",
                json={"run_type": "smoke_test", "selected_stages": None},
            )
            r.raise_for_status()
            body = r.json()
            run_id = body["run_id"]
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                r2 = await client.get(f"/api/v1/pipeline/runs/{run_id}")
                r2.raise_for_status()
                status = r2.json().get("status")
                if status in ("completed", "failed", "cancelled"):
                    return r2.json()
                await asyncio.sleep(2)
            return r2.json()

    return _trigger_and_wait
