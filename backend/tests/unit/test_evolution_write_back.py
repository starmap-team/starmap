"""Unit tests for evolution write-back (D-04/D-05/D-06).

Uses the AsyncMock / fake-result pattern from test_dashboard_service.py —
the DB session is fully mocked, no real PG required.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.evolution.trust_scorer import WRITEBACK_TRUST_THRESHOLD
from app.core.evolution.write_back import (
    CHANGE_TO_REQUIREMENT_TYPE,
    WRITEBACK_CHANGE_TYPES,
    write_back_changelog_row,
)
from app.models.evolution_models import EvolutionChangelog
from app.models.extraction_models import PositionSkillRelation, SkillRecord


class _FakeScalarResult:
    def __init__(self, val):
        self._val = val

    def scalar_one_or_none(self):
        return self._val


class _FakeScalarListResult:
    def __init__(self, vals):
        self._vals = vals

    def scalars(self):
        return self

    def all(self):
        return self._vals


def _make_row(
    *,
    position_name: str = "后端工程师",
    skill_name: str = "FastAPI",
    change_type: str = "added_required",
    trust: float = 0.8,
    confidence: float = 0.9,
    status: str = "pending",
) -> EvolutionChangelog:
    return EvolutionChangelog(
        position_name=position_name,
        skill_name=skill_name,
        change_type=change_type,
        trust_score=trust,
        confidence=confidence,
        status=status,
    )


def _make_session(*execute_returns) -> MagicMock:
    """Session whose execute returns the given fake results in order."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(execute_returns))
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def position_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def skill_record() -> SkillRecord:
    return SkillRecord(id=uuid.uuid4(), name="FastAPI", category="general")


class TestWriteBackGate:
    @pytest.mark.asyncio
    async def test_trust_below_threshold_returns_false_and_skips(self):
        """trust < WRITEBACK_TRUST_THRESHOLD → False, no upsert."""
        row = _make_row(trust=WRITEBACK_TRUST_THRESHOLD - 0.01)
        session = _make_session()
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result is None
        session.execute.assert_not_called()
        assert warnings == []

    @pytest.mark.asyncio
    async def test_pending_low_trust_still_blocked(self):
        """Phase 23 Task 5: pending 行 trust<0.6 仍被拦（0.6 保守闸门保留）。"""
        row = _make_row(trust=WRITEBACK_TRUST_THRESHOLD - 0.01, status="pending")
        session = _make_session()
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result is None
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_approved_low_trust_writes_back(self, position_id, skill_record):
        """Phase 23 Task 5 (DF-04): approved 行 trust<0.6 直接放行写回 PSR。"""
        row = _make_row(change_type="added_required", trust=0.4, status="approved")
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarResult(None),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9  # 写回成功（INSERT PSR）
        added: PositionSkillRelation = session.add.call_args[0][0]
        assert added.requirement_type == "required"
        assert added.position_id == position_id
        assert warnings == []

    @pytest.mark.asyncio
    async def test_manual_approve_then_write_back(self, position_id, skill_record):
        """手动 approve（evolution.py:454-461 置 status='approved'）后写回成功。

        单源新技能 trust≈0.35-0.42 曾永远 <0.6 被静默拦截——审核即写回闭环（D8f）。
        """
        row = _make_row(change_type="added_preferred", trust=0.35, status="approved")
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarResult(None),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        added = session.add.call_args[0][0]
        assert added.requirement_type == "preferred"

    @pytest.mark.asyncio
    async def test_removed_change_type_skipped(self):
        """D8f: removed IS write-back-eligible (deletes the PSR row) but
        must NOT project confidence to Neo4j — returns None so the
        orchestrator skips graph_sync for ghost-edge avoidance."""
        row = _make_row(change_type="removed", trust=0.95)
        # First execute(): resolve position_id → returns id (raw UUID).
        # Second execute(): resolve skill_id → returns ORM SkillRecord-like
        #   object with `.id` attribute (not a raw UUID).
        # Third execute(): fetch existing PSR → returns None (no edge).
        # The function should still return None to signal "no projection".
        _fake_skill = MagicMock()
        _fake_skill.id = uuid.uuid4()
        session = _make_session(
            _FakeScalarResult(uuid.uuid4()),  # _resolve_position_id → UUID
            _FakeScalarResult(_fake_skill),  # _resolve_skill_id → ORM-like
            _FakeScalarResult(None),          # existing PSR lookup
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        # P0-AUDIT-FIX (2026-08-13): removed returns None even when the PSR
        # is deleted, so the orchestrator does NOT project to Neo4j —
        # otherwise we would produce ghost REQUIRES edges (PG deleted,
        # Neo4j still present).
        assert result is None
        assert warnings == []

    @pytest.mark.asyncio
    async def test_retained_change_type_skipped(self):
        """retained is a no-op (D-04)."""
        row = _make_row(change_type="retained", trust=0.95)
        session = _make_session()
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result is None
        session.execute.assert_not_called()
        assert warnings == []


class TestAddedWriteBack:
    @pytest.mark.asyncio
    async def test_added_required_inserts_new_row(self, position_id, skill_record):
        """trust >= 0.6 added_required → INSERT PSR row (position, skill, required)."""
        row = _make_row(change_type="added_required")
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarResult(None),  # no existing PSR → insert
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        added: PositionSkillRelation = session.add.call_args[0][0]
        assert added.position_id == position_id
        assert added.skill_id == skill_record.id
        assert added.requirement_type == "required"
        assert added.confidence == 0.9
        assert warnings == []

    @pytest.mark.asyncio
    async def test_added_preferred_uses_mapping(self, position_id, skill_record):
        """added_preferred maps to requirement_type='preferred' (D-04 mapping)."""
        row = _make_row(change_type="added_preferred")
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarResult(None),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        added = session.add.call_args[0][0]
        assert added.requirement_type == "preferred"

    @pytest.mark.asyncio
    async def test_added_existing_row_takes_max_confidence(self, position_id, skill_record):
        """Existing (position, skill, required) row → confidence = max(existing, new)."""
        row = _make_row(change_type="added_required", confidence=0.6)
        existing_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="required",
            confidence=0.4,
        )
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarResult(existing_psr),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.6
        session.add.assert_not_called()  # updated in place, no new row
        assert existing_psr.confidence == 0.6

    @pytest.mark.asyncio
    async def test_existing_confidence_higher_keeps_it(self, position_id, skill_record):
        """If existing confidence is higher, keep existing (max semantics)."""
        row = _make_row(change_type="added_required", confidence=0.5)
        existing_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="required",
            confidence=0.9,
        )
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarResult(existing_psr),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        assert existing_psr.confidence == 0.9


class TestPromotedDemotedWriteBack:
    @pytest.mark.asyncio
    async def test_promoted_updates_existing_row(self, position_id, skill_record):
        """promoted → locate (position, skill) row, SET requirement_type='required'."""
        row = _make_row(change_type="promoted")
        existing_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="preferred",
            confidence=0.3,
        )
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarListResult([existing_psr]),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        session.add.assert_not_called()  # no new row
        assert existing_psr.requirement_type == "required"
        assert existing_psr.confidence == 0.9  # max(0.3, 0.9)

    @pytest.mark.asyncio
    async def test_demoted_updates_existing_row(self, position_id, skill_record):
        """demoted → SET requirement_type='preferred' (D-04 mapping)."""
        row = _make_row(change_type="demoted")
        existing_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="required",
            confidence=0.9,
        )
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarListResult([existing_psr]),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        assert existing_psr.requirement_type == "preferred"
        assert existing_psr.confidence == 0.9  # max(0.9, 0.9)

    @pytest.mark.asyncio
    async def test_promoted_no_existing_row_inserts(self, position_id, skill_record):
        """promoted with no existing PSR row → INSERT new row (defensive)."""
        row = _make_row(change_type="promoted")
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarListResult([]),
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        added = session.add.call_args[0][0]
        assert added.requirement_type == "required"

    @pytest.mark.asyncio
    async def test_promoted_collapses_duplicate_pair(self, position_id, skill_record):
        """W6: duplicate required+preferred pair → promoted keeps the required row, deletes preferred."""
        row = _make_row(change_type="promoted", confidence=0.8)
        required_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="required",
            confidence=0.5,
        )
        preferred_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="preferred",
            confidence=0.6,
        )
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarListResult([required_psr, preferred_psr]),
        )
        session.delete = AsyncMock()
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.8  # max(0.5, 0.8)
        assert required_psr.requirement_type == "required"
        assert required_psr.confidence == 0.8
        session.delete.assert_awaited_once_with(preferred_psr)

    @pytest.mark.asyncio
    async def test_demoted_collapses_duplicate_pair(self, position_id, skill_record):
        """W6: duplicate pair → demoted keeps the preferred row, deletes required."""
        row = _make_row(change_type="demoted", confidence=0.7)
        required_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="required",
            confidence=0.9,
        )
        preferred_psr = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_record.id,
            requirement_type="preferred",
            confidence=0.4,
        )
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(skill_record),
            _FakeScalarListResult([required_psr, preferred_psr]),
        )
        session.delete = AsyncMock()
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.7  # max(0.4, 0.7)
        assert preferred_psr.requirement_type == "preferred"
        assert preferred_psr.confidence == 0.7
        session.delete.assert_awaited_once_with(required_psr)


class TestUnresolvedAndFailures:
    @pytest.mark.asyncio
    async def test_unresolved_position_skips_with_warning_no_fabrication(self, skill_record):
        """D-08: unresolvable position → skip + warning, never fabricate."""
        row = _make_row(position_name="算法专家")
        session = _make_session(_FakeScalarResult(None))  # position lookup → None
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result is None
        session.add.assert_not_called()  # no fabricated PositionRecord / PSR
        assert any("算法专家" in w for w in warnings)
        assert len(warnings) == 1

    @pytest.mark.asyncio
    async def test_exception_appends_warning_and_does_not_raise(self):
        """D-06 fail-soft: any exception → warning appended, no raise."""
        row = _make_row()
        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db blew up"))
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result is None
        assert len(warnings) == 1
        assert "db blew up" in warnings[0]

    @pytest.mark.asyncio
    async def test_skill_created_when_missing(self, position_id):
        """Missing SkillRecord → SELECT-then-INSERT skill row, then PSR upsert."""
        row = _make_row(change_type="added_required")
        session = _make_session(
            _FakeScalarResult(position_id),
            _FakeScalarResult(None),  # skill missing
            _FakeScalarResult(None),  # no existing PSR
        )
        warnings: list[str] = []

        result = await write_back_changelog_row(session, row, warnings)

        assert result == 0.9
        # First add call creates the SkillRecord
        added_skill = session.add.call_args_list[0][0][0]
        assert isinstance(added_skill, SkillRecord)
        assert added_skill.name == "FastAPI"
        session.flush.assert_awaited()


class TestConstants:
    def test_mapping_covers_change_types(self):
        # D8f: WRITEBACK_CHANGE_TYPES gained "removed" — the write-back path
        # now also deletes PSR rows for skill removals (closed-loop with
        # PG→Neo4j). `removed` is excluded from CHANGE_TO_REQUIREMENT_TYPE
        # because removal has no requirement type.
        assert WRITEBACK_CHANGE_TYPES == {
            "added_required", "added_preferred", "promoted", "demoted", "removed",
        }
        assert CHANGE_TO_REQUIREMENT_TYPE == {
            "added_required": "required",
            "added_preferred": "preferred",
            "promoted": "required",
            "demoted": "preferred",
        }
        # "removed" must NOT be in CHANGE_TO_REQUIREMENT_TYPE.
        assert "removed" not in CHANGE_TO_REQUIREMENT_TYPE
