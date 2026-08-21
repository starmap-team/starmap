"""Integration tests for /admin/review-* endpoints using FastAPI TestClient."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_admin_user():
    """Mock the admin user for require_admin dependency."""
    return {"sub": "admin", "role": "admin", "username": "admin"}


@pytest.fixture
def client(mock_admin_user):
    """Test client with admin auth + DB session mocked.

    require_admin depends on get_current_user which validates JWT. We override
    BOTH to return the admin user, bypassing token validation.
    """
    from app.dependencies import get_current_user, get_db_session, get_neo4j_driver, require_admin
    from app.main import app

    async def _mock_session():
        session = AsyncMock()
        # 真实 SQLAlchemy AsyncSession.execute().scalar() 是同步的；
        # AsyncMock 默认 scalar() 返回 coroutine，需显式转同步
        result = MagicMock()
        result.scalar.return_value = 0
        session.execute.return_value = result
        return session

    app.dependency_overrides[get_db_session] = _mock_session
    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    app.dependency_overrides[require_admin] = lambda: mock_admin_user
    app.dependency_overrides[get_neo4j_driver] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════
# /admin/review-items
# ══════════════════════════════════════════════════════════════


def test_list_review_items_default_returns_pending(client, mock_admin_user):
    """Default endpoint returns pending_review items."""
    from datetime import UTC, datetime

    from app.services import review_service

    fake_item = review_service.ReviewItem(
        entity_type="position",
        entity_id=uuid.uuid4(),
        name="Test Position",
        industry="AI",
        review_status="pending_review",
        created_by="system:extraction",
        reviewed_by=None,
        reviewed_at=None,
        submitted_at=datetime.now(UTC),
        rejection_reason=None,
        created_at=datetime.now(UTC),
    )
    with patch.object(review_service, "list_by_status", AsyncMock(return_value=[fake_item])):
        resp = client.get("/api/v1/admin/review-items", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_list_review_items_filters_by_status(client):
    """?status=approved returns approved items only."""
    from app.services import review_service

    with patch.object(review_service, "list_by_status", AsyncMock(return_value=[])) as m:
        resp = client.get(
            "/api/v1/admin/review-items?status=approved",
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    # Verify the service was called with status=approved
    m.assert_awaited_once()
    call_kwargs = m.await_args.kwargs
    assert call_kwargs.get("status") == "approved"


def test_list_review_items_filters_by_entity_type(client):
    """?entity_type=position narrows to positions only."""
    from app.services import review_service

    with patch.object(review_service, "list_by_status", AsyncMock(return_value=[])) as m:
        resp = client.get(
            "/api/v1/admin/review-items?entity_type=position",
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    call_kwargs = m.await_args.kwargs
    assert call_kwargs.get("entity_type") == "position"


# ══════════════════════════════════════════════════════════════
# /admin/review/{type}/{id}/approve
# ══════════════════════════════════════════════════════════════


def test_approve_review_item_success(client):
    """POST /admin/review/position/{uuid}/approve calls review_service.approve."""
    from app.services import review_service

    entity_id = uuid.uuid4()
    fake_item = review_service.ReviewItem(
        entity_type="position",
        entity_id=entity_id,
        name="AI Engineer",
        industry="AI",
        review_status="approved",
        created_by="system:extraction",
        reviewed_by="admin",
        reviewed_at=None,
        submitted_at=None,
        rejection_reason=None,
        created_at=None,
    )
    with patch.object(review_service, "approve", AsyncMock(return_value=fake_item)) as m:
        resp = client.post(
            f"/api/v1/admin/review/position/{entity_id}/approve",
            json={"reason": "looks good"},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["review_status"] == "approved"
    assert body["reviewed_by"] == "admin"
    m.assert_awaited_once()


def test_approve_invalid_uuid_returns_400(client):
    resp = client.post(
        "/api/v1/admin/review/position/not-a-uuid/approve",
        json={},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 400


def test_approve_not_found_returns_404(client):
    from app.services import review_service

    entity_id = uuid.uuid4()
    with patch.object(
        review_service, "approve",
        AsyncMock(side_effect=review_service.ReviewNotFound("not found")),
    ):
        resp = client.post(
            f"/api/v1/admin/review/position/{entity_id}/approve",
            json={},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 404


def test_approve_invalid_state_returns_409(client):
    from app.services import review_service

    entity_id = uuid.uuid4()
    with patch.object(
        review_service, "approve",
        AsyncMock(side_effect=review_service.InvalidStateTransition("can't approve draft")),
    ):
        resp = client.post(
            f"/api/v1/admin/review/skill/{entity_id}/approve",
            json={},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 409


# ══════════════════════════════════════════════════════════════
# /admin/review/{type}/{id}/reject
# ══════════════════════════════════════════════════════════════


def test_reject_requires_reason(client):
    """Reject without reason returns 422."""
    entity_id = uuid.uuid4()
    resp = client.post(
        f"/api/v1/admin/review/position/{entity_id}/reject",
        json={"reason": ""},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 422


def test_reject_with_reason_calls_service(client):
    from app.services import review_service

    entity_id = uuid.uuid4()
    fake_item = review_service.ReviewItem(
        entity_type="position",
        entity_id=entity_id,
        name="Dup",
        industry=None,
        review_status="rejected",
        created_by=None,
        reviewed_by="admin",
        reviewed_at=None,
        submitted_at=None,
        rejection_reason="duplicate",
        created_at=None,
    )
    with patch.object(review_service, "reject", AsyncMock(return_value=fake_item)) as m:
        resp = client.post(
            f"/api/v1/admin/review/position/{entity_id}/reject",
            json={"reason": "duplicate"},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    m.assert_awaited_once()


# ══════════════════════════════════════════════════════════════
# /admin/review-stats
# ══════════════════════════════════════════════════════════════


def test_review_stats_returns_aggregates(client):
    from app.services import review_service

    expected = {
        "position": 38,
        "skill": 269,
        "position_approved": 38,
        "skill_approved": 269,
    }
    with patch.object(review_service, "count_by_status", AsyncMock(return_value=expected)):
        resp = client.get("/api/v1/admin/review-stats", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    assert resp.json() == expected
