"""Tests for review_service state machine.

Covers all legal/illegal transitions, idempotency, and audit log writes.
Phase 23 enterprise review-workflow.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.review_service import (
    ALLOWED_STATUSES,
    InvalidStateTransition,
    MissingRejectionReason,
    ReviewNotFound,
    approve,
    count_by_status,
    list_by_status,
    reject,
    submit_for_review,
    unpublish,
)


def _fake_row(*, review_status: str = "draft", name: str = "Test", industry: str | None = None,
              entity_id: uuid.UUID | None = None):
    """Create a MagicMock that quacks like a SQLAlchemy ORM row."""
    row = MagicMock()
    row.id = entity_id or uuid.uuid4()
    row.name = name
    row.industry = industry
    row.review_status = review_status
    row.created_by = None
    row.reviewed_by = None
    row.reviewed_at = None
    row.submitted_at = None
    row.rejection_reason = None
    row.created_at = datetime.now(UTC)
    return row


def _fake_session_with_entity(entity):
    """Return an AsyncMock session that finds `entity` and accepts audit-log adds."""
    session = AsyncMock()
    # SELECT returns the entity
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=entity)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ══════════════════════════════════════════════════════════════
# Allowed status enum
# ══════════════════════════════════════════════════════════════


def test_allowed_statuses_constant():
    """The state machine has the four states from the design doc."""
    assert ALLOWED_STATUSES == ("draft", "pending_review", "approved", "rejected")


# ══════════════════════════════════════════════════════════════
# submit_for_review
# ══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_submit_draft_to_pending_review():
    row = _fake_row(review_status="draft")
    session = _fake_session_with_entity(row)

    item = await submit_for_review(
        session, entity_type="position", entity_id=row.id, actor="alice",
    )

    assert item.review_status == "pending_review"
    assert row.review_status == "pending_review"
    assert row.submitted_at is not None
    assert session.add.called  # audit log row appended
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_submit_rejected_to_pending_review_clears_reason():
    row = _fake_row(review_status="rejected", name="Senior Dev")
    row.rejection_reason = "duplicate of existing"
    session = _fake_session_with_entity(row)

    item = await submit_for_review(
        session, entity_type="position", entity_id=row.id, actor="alice",
    )

    assert item.review_status == "pending_review"
    assert row.rejection_reason is None  # cleared on resubmit
    assert session.add.called


@pytest.mark.asyncio
async def test_submit_already_pending_is_idempotent():
    """Re-submitting a pending entity must NOT create a duplicate audit log row."""
    row = _fake_row(review_status="pending_review")
    session = _fake_session_with_entity(row)

    item = await submit_for_review(
        session, entity_type="skill", entity_id=row.id, actor="alice",
    )

    assert item.review_status == "pending_review"
    # The state didn't change — no audit log row should be added.
    assert not session.add.called
    assert not session.commit.await_count


@pytest.mark.asyncio
async def test_submit_approved_is_illegal():
    """An approved entity cannot be re-submitted; admin must unpublish first."""
    row = _fake_row(review_status="approved")
    session = _fake_session_with_entity(row)

    with pytest.raises(InvalidStateTransition):
        await submit_for_review(
            session, entity_type="position", entity_id=row.id, actor="alice",
        )
    # Nothing was written
    assert not session.add.called
    assert not session.commit.await_count


@pytest.mark.asyncio
async def test_submit_missing_entity_raises_not_found():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(ReviewNotFound):
        await submit_for_review(
            session, entity_type="position", entity_id=uuid.uuid4(), actor="alice",
        )


# ══════════════════════════════════════════════════════════════
# approve
# ══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_approve_pending_to_approved():
    row = _fake_row(review_status="pending_review", name="AI Engineer")
    session = _fake_session_with_entity(row)

    item = await approve(
        session, entity_type="position", entity_id=row.id, actor="bob", reason="looks good",
    )

    assert item.review_status == "approved"
    assert row.reviewed_by == "bob"
    assert row.reviewed_at is not None
    assert session.add.called  # audit log
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_approve_already_approved_is_idempotent():
    row = _fake_row(review_status="approved")
    session = _fake_session_with_entity(row)

    item = await approve(
        session, entity_type="position", entity_id=row.id, actor="bob",
    )

    assert item.review_status == "approved"
    assert not session.add.called  # no duplicate audit log
    assert not session.commit.await_count


@pytest.mark.asyncio
async def test_approve_draft_is_illegal():
    row = _fake_row(review_status="draft")
    session = _fake_session_with_entity(row)

    with pytest.raises(InvalidStateTransition):
        await approve(
            session, entity_type="skill", entity_id=row.id, actor="bob",
        )


@pytest.mark.asyncio
async def test_approve_rejected_is_illegal():
    row = _fake_row(review_status="rejected")
    session = _fake_session_with_entity(row)

    with pytest.raises(InvalidStateTransition):
        await approve(
            session, entity_type="skill", entity_id=row.id, actor="bob",
        )


# ══════════════════════════════════════════════════════════════
# reject
# ══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reject_pending_to_rejected_requires_reason():
    row = _fake_row(review_status="pending_review")
    session = _fake_session_with_entity(row)

    with pytest.raises(MissingRejectionReason):
        await reject(
            session, entity_type="position", entity_id=row.id, actor="bob", reason="",
        )
    with pytest.raises(MissingRejectionReason):
        await reject(
            session, entity_type="position", entity_id=row.id, actor="bob", reason="   ",
        )
    # Nothing was written
    assert not session.add.called


@pytest.mark.asyncio
async def test_reject_pending_to_rejected_succeeds():
    row = _fake_row(review_status="pending_review", name="ML Engineer")
    session = _fake_session_with_entity(row)

    item = await reject(
        session, entity_type="skill", entity_id=row.id, actor="bob", reason="duplicate of existing skill",
    )

    assert item.review_status == "rejected"
    assert row.reviewed_by == "bob"
    assert row.rejection_reason == "duplicate of existing skill"
    assert session.add.called
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_reject_already_rejected_is_idempotent():
    row = _fake_row(review_status="rejected", name="OldSkill")
    row.rejection_reason = "duplicate"
    session = _fake_session_with_entity(row)

    item = await reject(
        session, entity_type="skill", entity_id=row.id, actor="bob", reason="another reason",
    )

    assert item.review_status == "rejected"
    assert row.rejection_reason == "duplicate"  # unchanged
    assert not session.add.called
    assert not session.commit.await_count


@pytest.mark.asyncio
async def test_reject_approved_is_illegal():
    row = _fake_row(review_status="approved")
    session = _fake_session_with_entity(row)

    with pytest.raises(InvalidStateTransition):
        await reject(
            session, entity_type="position", entity_id=row.id, actor="bob", reason="too late",
        )


# ══════════════════════════════════════════════════════════════
# unpublish
# ══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_unpublish_approved_to_draft_requires_reason():
    row = _fake_row(review_status="approved")
    session = _fake_session_with_entity(row)

    with pytest.raises(MissingRejectionReason):
        await unpublish(
            session, entity_type="position", entity_id=row.id, actor="bob", reason="",
        )


@pytest.mark.asyncio
async def test_unpublish_approved_to_draft_succeeds():
    row = _fake_row(review_status="approved", name="Obsolete")
    session = _fake_session_with_entity(row)

    item = await unpublish(
        session, entity_type="position", entity_id=row.id, actor="bob", reason="duplicate",
    )

    assert item.review_status == "draft"
    assert row.reviewed_by == "bob"
    assert row.rejection_reason == "duplicate"
    assert session.add.called


@pytest.mark.asyncio
async def test_unpublish_pending_is_illegal():
    row = _fake_row(review_status="pending_review")
    session = _fake_session_with_entity(row)

    with pytest.raises(InvalidStateTransition):
        await unpublish(
            session, entity_type="skill", entity_id=row.id, actor="bob", reason="oops",
        )


@pytest.mark.asyncio
async def test_unpublish_draft_is_illegal():
    row = _fake_row(review_status="draft")
    session = _fake_session_with_entity(row)

    with pytest.raises(InvalidStateTransition):
        await unpublish(
            session, entity_type="skill", entity_id=row.id, actor="bob", reason="oops",
        )


# ══════════════════════════════════════════════════════════════
# list_by_status
# ══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_by_status_merges_position_and_skill():
    """list_by_status with no entity_type filter returns both, sorted by created_at."""
    pos = _fake_row(review_status="pending_review", name="P1")
    pos.created_at = datetime(2026, 7, 14, 10, 0, 0, tzinfo=UTC)
    skl = _fake_row(review_status="pending_review", name="S1")
    skl.created_at = datetime(2026, 7, 14, 11, 0, 0, tzinfo=UTC)  # newer

    session = AsyncMock()
    # First call (position) returns pos; second (skill) returns skl.
    pos_result = MagicMock()
    pos_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[pos])))
    skl_result = MagicMock()
    skl_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[skl])))
    session.execute = AsyncMock(side_effect=[pos_result, skl_result])

    items = await list_by_status(session, status="pending_review", limit=10)

    assert len(items) == 2
    types = {i.entity_type for i in items}
    assert types == {"position", "skill"}
    # Newer (skl) should be first
    assert items[0].entity_type == "skill"
    assert items[1].entity_type == "position"


@pytest.mark.asyncio
async def test_list_by_status_filters_by_entity_type():
    pos = _fake_row(review_status="approved", name="P1")
    session = AsyncMock()
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[pos])))
    session.execute = AsyncMock(return_value=result)

    items = await list_by_status(session, entity_type="position", status="approved", limit=10)

    assert len(items) == 1
    assert items[0].entity_type == "position"
    # Only one SQL execute (only positions queried)
    assert session.execute.await_count == 1


# ══════════════════════════════════════════════════════════════
# count_by_status
# ══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_count_by_status_aggregates_both_types():
    session = AsyncMock()
    # Position GROUP BY result
    pos_result = MagicMock()
    pos_result.all = MagicMock(return_value=[("approved", 38), ("pending_review", 2)])
    # Skill GROUP BY result
    skl_result = MagicMock()
    skl_result.all = MagicMock(return_value=[("approved", 269)])
    session.execute = AsyncMock(side_effect=[pos_result, skl_result])

    counts = await count_by_status(session)

    assert counts["position_approved"] == 38
    assert counts["position_pending_review"] == 2
    assert counts["skill_approved"] == 269
    assert counts["position"] == 40
    assert counts["skill"] == 269
