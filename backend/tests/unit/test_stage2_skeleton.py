"""阶段2接口骨架测试。"""
from __future__ import annotations


def test_graph_query_skeleton_response(client):
    resp = client.get("/api/v1/graph/query", params={"cypher": "MATCH (n) RETURN n LIMIT 1"})

    assert resp.status_code == 200
    assert resp.json() == {"nodes": [], "edges": []}


def test_graph_query_requires_cypher(client):
    resp = client.get("/api/v1/graph/query")

    assert resp.status_code == 422


def test_graph_panorama_skeleton_response(client):
    resp = client.get("/api/v1/graph/panorama")

    assert resp.status_code == 200
    assert resp.json() == {"nodes": [], "edges": []}


def test_positions_skeleton_response(client):
    resp = client.get("/api/v1/positions", params={"page": 2, "page_size": 10})

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "page": 2, "page_size": 10}


def test_positions_query_params_are_validated(client):
    resp = client.get("/api/v1/positions", params={"page": 0})

    assert resp.status_code == 422


def test_stage2_openapi_schema(client):
    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    schema = resp.json()
    graph_query = schema["paths"]["/api/v1/graph/query"]["get"]
    graph_panorama = schema["paths"]["/api/v1/graph/panorama"]["get"]
    positions = schema["paths"]["/api/v1/positions"]["get"]

    assert graph_query["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/GraphQueryResponse"
    )
    assert graph_panorama["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/GraphPanoramaResponse"
    )
    assert positions["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PositionListResponse"
    )

    graph_params = {param["name"]: param for param in graph_query["parameters"]}
    position_params = {param["name"]: param for param in positions["parameters"]}

    assert graph_params["cypher"]["required"] is True
    assert position_params["page"]["schema"]["minimum"] == 1
    assert position_params["page_size"]["schema"]["maximum"] == 100
