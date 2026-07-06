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
    """业务说明：测试辅助函数，用于快速创建职位技能快照数据。"""
    return SnapshotData(
        id=snap_id,
        position_name=position,
        snapshot_date=date or datetime(2026, 6, 1, tzinfo=UTC),
        required_skills=[SkillProfile(name=s) for s in required],
        preferred_skills=[SkillProfile(name=s) for s in preferred],
        source_count=5,
    )


class TestDiffEngineBasic:
    """业务说明：DiffEngine基础功能测试类，覆盖常见的技能变更场景。"""

    def setup_method(self) -> None:
        # 技术说明：每个测试方法执行前初始化DiffEngine实例
        self.engine = DiffEngine()

    def test_no_changes(self) -> None:
        """业务说明：测试完全相同的两个快照，预期不产生任何变更，所有技能均为保留状态。"""
        older = _make_snapshot("Backend", ["Python", "SQL"], ["Docker"], "s1")
        newer = _make_snapshot("Backend", ["Python", "SQL"], ["Docker"], "s2")
        result = self.engine.diff(older, newer)
        # 技术说明：验证无变更时统计指标正确
        assert result.total_changes == 0
        assert result.retained_count == 3

    def test_new_required_skill(self) -> None:
        """业务说明：测试新增必需技能场景，Go从无到有，应标记为ADDED_REQUIRED。"""
        older = _make_snapshot("Backend", ["Python"], [], "s1")
        newer = _make_snapshot("Backend", ["Python", "Go"], [], "s2")
        result = self.engine.diff(older, newer)
        added = [c for c in result.changes if c.change_type == ChangeType.ADDED_REQUIRED]
        # 技术说明：验证新增技能数量和名称
        assert len(added) == 1
        assert added[0].skill_name == "Go"

    def test_removed_skill(self) -> None:
        """业务说明：测试技能移除场景，Perl从有到无，应标记为REMOVED。"""
        older = _make_snapshot("Backend", ["Python", "Perl"], [], "s1")
        newer = _make_snapshot("Backend", ["Python"], [], "s2")
        result = self.engine.diff(older, newer)
        removed = [c for c in result.changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].skill_name == "Perl"

    def test_promoted_preferred_to_required(self) -> None:
        """业务说明：测试技能从 preferred 提升为 required 的场景，Docker应标记为PROMOTED。"""
        older = _make_snapshot("Backend", ["Python"], ["Docker"], "s1")
        newer = _make_snapshot("Backend", ["Python", "Docker"], [], "s2")
        result = self.engine.diff(older, newer)
        promoted = [c for c in result.changes if c.change_type == ChangeType.PROMOTED]
        # 技术说明：验证提升技能及其前后状态
        assert len(promoted) == 1
        assert promoted[0].skill_name == "Docker"
        assert promoted[0].old_requirement == "preferred"
        assert promoted[0].new_requirement == "required"

    def test_demoted_required_to_preferred(self) -> None:
        """业务说明：测试技能从 required 降级为 preferred 的场景，SQL应标记为DEMOTED。"""
        older = _make_snapshot("Backend", ["Python", "SQL"], [], "s1")
        newer = _make_snapshot("Backend", ["Python"], ["SQL"], "s2")
        result = self.engine.diff(older, newer)
        demoted = [c for c in result.changes if c.change_type == ChangeType.DEMOTED]
        # 技术说明：验证降级技能及其前后状态
        assert len(demoted) == 1
        assert demoted[0].skill_name == "SQL"
        assert demoted[0].old_requirement == "required"
        assert demoted[0].new_requirement == "preferred"

    def test_new_preferred_skill(self) -> None:
        """业务说明：测试新增 preferred 技能场景，Kubernetes应标记为ADDED_PREFERRED。"""
        older = _make_snapshot("Backend", ["Python"], [], "s1")
        newer = _make_snapshot("Backend", ["Python"], ["Kubernetes"], "s2")
        result = self.engine.diff(older, newer)
        added = [c for c in result.changes if c.change_type == ChangeType.ADDED_PREFERRED]
        assert len(added) == 1
        assert added[0].skill_name == "Kubernetes"


class TestDiffEngineEdgeCases:
    """业务说明：DiffEngine边界条件测试类，覆盖特殊场景和边界情况。"""

    def setup_method(self) -> None:
        # 技术说明：每个测试方法执行前初始化DiffEngine实例
        self.engine = DiffEngine()

    def test_first_snapshot_no_older(self) -> None:
        """业务说明：测试首次快照场景（older为None），所有技能应被标记为新增。"""
        newer = _make_snapshot("Backend", ["Python", "SQL"], ["Docker"], "s1")
        result = self.engine.diff(None, newer)
        # 技术说明：验证首次快照时from_id为None，所有技能均为新增
        assert result.snapshot_from_id is None
        assert result.added_count == 3
        assert result.retained_count == 0

    def test_empty_snapshots(self) -> None:
        """业务说明：测试两个空快照对比场景，预期不产生任何变更。"""
        older = _make_snapshot("Backend", [], [], "s1")
        newer = _make_snapshot("Backend", [], [], "s2")
        result = self.engine.diff(older, newer)
        assert len(result.changes) == 0

    def test_complex_mixed_changes(self) -> None:
        """业务说明：测试复杂混合变更场景，模拟真实业务中多种变更类型同时发生的情况。
        
        场景描述：
        - 老快照：required=[Python, SQL, Java], preferred=[Docker, Redis]
        - 新快照：required=[Python, Docker, Go, Kubernetes], preferred=[SQL, Redis, TypeScript]
        """
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

        # 业务说明：验证各技能的变更状态
        # Python: retained as required
        # SQL: demoted (required → preferred)
        # Java: removed
        # Docker: promoted (preferred → required)
        # Redis: retained as preferred
        # Go: added required
        # Kubernetes: added required
        # TypeScript: added preferred

        # 技术说明：验证各类变更统计数量
        assert result.retained_count == 2  # Python, Redis
        assert result.promoted_count == 1  # Docker
        assert result.demoted_count == 1  # SQL
        assert result.removed_count == 1  # Java
        added_req = [c for c in result.changes if c.change_type == ChangeType.ADDED_REQUIRED]
        added_pref = [c for c in result.changes if c.change_type == ChangeType.ADDED_PREFERRED]
        assert len(added_req) == 2  # Go, Kubernetes
        assert len(added_pref) == 1  # TypeScript
        assert result.total_changes == 6  # 2+1+1+1+1 (non-retained): 2 added_req, 1 added_pref, 1 removed, 1 promoted, 1 demoted

    def test_diff_result_summary(self) -> None:
        """业务说明：测试变更摘要统计功能，验证summary字典与变更计数一致。"""
        older = _make_snapshot("X", ["A", "B"], ["C"], "s1")
        newer = _make_snapshot("X", ["A", "D"], ["C", "E"], "s2")
        result = self.engine.diff(older, newer)
        # 技术说明：验证summary中各类变更统计正确
        assert result.summary["retained"] == 2  # A(required), C(preferred)
        assert result.summary["removed"] == 1  # B
        assert result.summary["added_required"] == 1  # D
        assert result.summary["added_preferred"] == 1  # E

    def test_diff_all_consecutive(self) -> None:
        """业务说明：测试连续快照差异计算功能，验证多个快照间的连续对比。"""
        s1 = _make_snapshot("X", ["A"], [], "s1", datetime(2026, 1, 1, tzinfo=UTC))
        s2 = _make_snapshot("X", ["A", "B"], [], "s2", datetime(2026, 4, 1, tzinfo=UTC))
        s3 = _make_snapshot("X", ["A", "B", "C"], [], "s3", datetime(2026, 7, 1, tzinfo=UTC))
        results = self.engine.diff_all([s1, s2, s3])
        # 技术说明：验证连续对比结果数量和新增技能
        assert len(results) == 2
        assert results[0].added_count == 1  # B
        assert results[1].added_count == 1  # C

    def test_diff_all_single_snapshot(self) -> None:
        """业务说明：测试单个快照的diff_all处理，应返回首次快照差异。"""
        s1 = _make_snapshot("X", ["A", "B"], [], "s1")
        results = self.engine.diff_all([s1])
        # 技术说明：验证单个快照时from_id为None，所有技能为新增
        assert len(results) == 1
        assert results[0].snapshot_from_id is None
        assert results[0].added_count == 2

    def test_diff_all_empty(self) -> None:
        """业务说明：测试空列表的diff_all处理，应返回空结果。"""
        results = self.engine.diff_all([])
        assert results == []
