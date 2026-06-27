"""Unit tests for DiffEngine — skill change detection between snapshots."""

from datetime import UTC, datetime

from app.core.evolution.diff_engine import ChangeType, DiffEngine
from app.core.evolution.snapshot_manager import SkillProfile, SnapshotData


def _make_snapshot(
    position: str,
    required: list[str],
    preferred: list[str],
    snap_id: str = "snap-1",
    date: datetime | None = None,
) -> SnapshotData:
    """Helper to create a SnapshotData for testing."""
    return SnapshotData(
        id=snap_id,
        position_name=position,
        snapshot_date=date or datetime(2026, 6, 1, tzinfo=UTC),
        required_skills=[SkillProfile(name=s) for s in required],
        preferred_skills=[SkillProfile(name=s) for s in preferred],
        source_count=5,
    )


class TestDiffEngineBasic:
    """Basic diff scenarios."""

    def setup_method(self) -> None:
        self.engine = DiffEngine()

    def test_no_changes(self) -> None:
        """Identical snapshots produce only RETAINED changes."""
        older = _make_snapshot("Backend", ["Python", "SQL"], ["Docker"], "s1")
        newer = _make_snapshot("Backend", ["Python", "SQL"], ["Docker"], "s2")
        result = self.engine.diff(older, newer)
        assert result.total_changes == 0
        assert result.retained_count == 3

    def test_new_required_skill(self) -> None:
        """A new required skill appears as ADDED_REQUIRED."""
        older = _make_snapshot("Backend", ["Python"], [], "s1")
        newer = _make_snapshot("Backend", ["Python", "Go"], [], "s2")
        result = self.engine.diff(older, newer)
        added = [c for c in result.changes if c.change_type == ChangeType.ADDED_REQUIRED]
        assert len(added) == 1
        assert added[0].skill_name == "Go"

    def test_removed_skill(self) -> None:
        """A removed skill appears as REMOVED."""
        older = _make_snapshot("Backend", ["Python", "Perl"], [], "s1")
        newer = _make_snapshot("Backend", ["Python"], [], "s2")
        result = self.engine.diff(older, newer)
        removed = [c for c in result.changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].skill_name == "Perl"

    def test_promoted_preferred_to_required(self) -> None:
        """A skill moving from preferred to required is PROMOTED."""
        older = _make_snapshot("Backend", ["Python"], ["Docker"], "s1")
        newer = _make_snapshot("Backend", ["Python", "Docker"], [], "s2")
        result = self.engine.diff(older, newer)
        promoted = [c for c in result.changes if c.change_type == ChangeType.PROMOTED]
        assert len(promoted) == 1
        assert promoted[0].skill_name == "Docker"
        assert promoted[0].old_requirement == "preferred"
        assert promoted[0].new_requirement == "required"

    def test_demoted_required_to_preferred(self) -> None:
        """A skill moving from required to preferred is DEMOTED."""
        older = _make_snapshot("Backend", ["Python", "SQL"], [], "s1")
        newer = _make_snapshot("Backend", ["Python"], ["SQL"], "s2")
        result = self.engine.diff(older, newer)
        demoted = [c for c in result.changes if c.change_type == ChangeType.DEMOTED]
        assert len(demoted) == 1
        assert demoted[0].skill_name == "SQL"
        assert demoted[0].old_requirement == "required"
        assert demoted[0].new_requirement == "preferred"

    def test_new_preferred_skill(self) -> None:
        """A new preferred skill appears as ADDED_PREFERRED."""
        older = _make_snapshot("Backend", ["Python"], [], "s1")
        newer = _make_snapshot("Backend", ["Python"], ["Kubernetes"], "s2")
        result = self.engine.diff(older, newer)
        added = [c for c in result.changes if c.change_type == ChangeType.ADDED_PREFERRED]
        assert len(added) == 1
        assert added[0].skill_name == "Kubernetes"


class TestDiffEngineEdgeCases:
    """Edge cases and boundary conditions."""

    def setup_method(self) -> None:
        self.engine = DiffEngine()

    def test_first_snapshot_no_older(self) -> None:
        """When older is None, all skills are treated as added."""
        newer = _make_snapshot("Backend", ["Python", "SQL"], ["Docker"], "s1")
        result = self.engine.diff(None, newer)
        assert result.snapshot_from_id is None
        assert result.added_count == 3
        assert result.retained_count == 0

    def test_empty_snapshots(self) -> None:
        """Both snapshots empty → no changes."""
        older = _make_snapshot("Backend", [], [], "s1")
        newer = _make_snapshot("Backend", [], [], "s2")
        result = self.engine.diff(older, newer)
        assert len(result.changes) == 0

    def test_complex_mixed_changes(self) -> None:
        """Realistic scenario with multiple change types."""
        older = _make_snapshot(
            "Backend",
            required=["Python", "SQL", "Java"],
            preferred=["Docker", "Redis"],
            snap_id="s1",
        )
        newer = _make_snapshot(
            "Backend",
            required=["Python", "Docker", "Go", "Kubernetes"],
            preferred=["SQL", "Redis", "TypeScript"],
            snap_id="s2",
        )
        result = self.engine.diff(older, newer)

        # Python: retained as required
        # SQL: demoted (required → preferred)
        # Java: removed
        # Docker: promoted (preferred → required)
        # Redis: retained as preferred
        # Go: added required
        # Kubernetes: added required
        # TypeScript: added preferred

        assert result.retained_count == 2  # Python, Redis
        assert result.promoted_count == 1  # Docker
        assert result.demoted_count == 1  # SQL
        assert result.removed_count == 1  # Java
        added_req = [c for c in result.changes if c.change_type == ChangeType.ADDED_REQUIRED]
        added_pref = [c for c in result.changes if c.change_type == ChangeType.ADDED_PREFERRED]
        assert len(added_req) == 2  # Go, Kubernetes
        assert len(added_pref) == 1  # TypeScript
        assert result.total_changes == 5  # 1+1+1+2+0 (non-retained)

    def test_diff_result_summary(self) -> None:
        """Verify summary dict matches change counts."""
        older = _make_snapshot("X", ["A", "B"], ["C"], "s1")
        newer = _make_snapshot("X", ["A", "D"], ["C", "E"], "s2")
        result = self.engine.diff(older, newer)
        assert result.summary["retained"] == 2  # A(required), C(preferred)
        assert result.summary["removed"] == 1  # B
        assert result.summary["added_required"] == 1  # D
        assert result.summary["added_preferred"] == 1  # E

    def test_diff_all_consecutive(self) -> None:
        """diff_all computes diffs for consecutive pairs."""
        s1 = _make_snapshot("X", ["A"], [], "s1", datetime(2026, 1, 1, tzinfo=UTC))
        s2 = _make_snapshot("X", ["A", "B"], [], "s2", datetime(2026, 4, 1, tzinfo=UTC))
        s3 = _make_snapshot("X", ["A", "B", "C"], [], "s3", datetime(2026, 7, 1, tzinfo=UTC))
        results = self.engine.diff_all([s1, s2, s3])
        assert len(results) == 2
        assert results[0].added_count == 1  # B
        assert results[1].added_count == 1  # C

    def test_diff_all_single_snapshot(self) -> None:
        """diff_all with single snapshot returns first-snapshot diff."""
        s1 = _make_snapshot("X", ["A", "B"], [], "s1")
        results = self.engine.diff_all([s1])
        assert len(results) == 1
        assert results[0].snapshot_from_id is None
        assert results[0].added_count == 2

    def test_diff_all_empty(self) -> None:
        """diff_all with empty list returns empty."""
        results = self.engine.diff_all([])
        assert results == []
