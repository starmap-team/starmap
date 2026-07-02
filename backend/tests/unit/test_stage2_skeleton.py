"""阶段2接口骨架测试。"""
from __future__ import annotations

import pytest

from app.dependencies import get_neo4j_driver
from app.main import app


@pytest.fixture(autouse=True)
def no_neo4j_driver():
    app.dependency_overrides[get_neo4j_driver] = lambda: None
    yield
    app.dependency_overrides.pop(get_neo4j_driver, None)


def test_positions_skeleton_response(client):
    from unittest.mock import AsyncMock, MagicMock

    from app.dependencies import get_db_session
    from app.main import app

    # Mock the database session to return empty results
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = override_session
    try:
        resp = client.get("/api/v1/positions", params={"page": 1, "page_size": 10})
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert isinstance(data["items"], list)


def test_positions_query_params_are_validated(client):
    resp = client.get("/api/v1/positions", params={"page": 0})

    assert resp.status_code == 422


def test_stage2_openapi_schema(client):
    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    schema = resp.json()
    positions = schema["paths"]["/api/v1/positions"]["get"]

    assert positions["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PositionListResponse"
    )

    position_params = {param["name"]: param for param in positions["parameters"]}

    assert position_params["page"]["schema"]["minimum"] == 1
    assert position_params["page_size"]["schema"]["maximum"] == 100
