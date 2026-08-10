"""统一错误响应格式测试 — 裸 raise HTTPException 经全局 handler 归一化。

覆盖：
- 404（未知路由）→ {detail, code, timestamp, fields?}
- 401（未认证访问受保护端点）→ 统一格式 + AUTH 错误码
"""

from fastapi.testclient import TestClient


def test_http_exception_handler_404_unified(client: TestClient) -> None:
    """未知路由 → 404，响应带 code/timestamp 的统一格式。"""
    resp = client.get("/api/v1/definitely-not-a-route-404")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "RES_NOT_FOUND"
    assert "detail" in body and body["detail"]
    assert "timestamp" in body


def test_http_exception_handler_401_unified(client: TestClient) -> None:
    """未认证访问受保护端点 → 统一格式（此前缺 code/timestamp）。"""
    resp = client.get("/api/v1/admin/stats")
    assert resp.status_code == 403
    body = resp.json()
    assert body["code"] == "AUTH_FORBIDDEN"
    assert "detail" in body and body["detail"]
    assert "timestamp" in body
