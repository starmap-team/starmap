"""RepairEngine 单测 (P2 数据统一方案).

覆盖: detect_orphans 严格口径（含 no_canonical_id / unlinked 判定）、
sync_orphan_queue 去重、execute_cleanup 审批删除+审计、ensure_projection 幂等。
使用 fake Neo4j driver + fake PG session（不依赖真实 PG/Neo4j）。
"""
from __future__ import annotations

import uuid
from typing import Any

from app.services.repair_engine import (
    STATUS_CLEANED,
    STATUS_PENDING,
    STATUS_REJECTED,
    OrphanScanResult,
    RepairEngine,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeRecord:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


class _FakeCypherResult:
    def __init__(self, records: list[_FakeRecord]) -> None:
        self._records = records

    def single(self) -> _FakeRecord | None:
        return self._records[0] if self._records else None

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for r in self._records:
                yield r
        return gen()


class _FakeNeo4jSession:
    """按查询内容返回剧本化结果。"""

    def __init__(self, position_nodes: list[dict[str, Any]], skill_nodes: list[dict[str, Any]]) -> None:
        self._position_nodes = position_nodes
        self._skill_nodes = skill_nodes
        self.runs: list[str] = []

    async def run(self, query: str, **params: Any) -> _FakeCypherResult:
        self.runs.append(query)
        if "n:Position" in query or "n:Position " in query or "MATCH (n:Position)" in query:
            return _FakeCypherResult([
                _FakeRecord({
                    "cid": n.get("canonical_id"),
                    "name": n.get("name"),
                    "in_degree": n.get("in_degree", 0),
                }) for n in self._position_nodes
            ])
        if "n:Skill" in query:
            return _FakeCypherResult([
                _FakeRecord({
                    "cid": n.get("canonical_id"),
                    "name": n.get("name"),
                    "in_degree": n.get("in_degree", 0),
                }) for n in self._skill_nodes
            ])
        return _FakeCypherResult([])

    async def __aenter__(self) -> _FakeNeo4jSession:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False


class _FakeDriver:
    def __init__(self, session: _FakeNeo4jSession) -> None:
        self._session = session

    def session(self) -> _FakeNeo4jSession:
        return self._session


class _FakePgSession:
    """fake AsyncSession：execute(select(...)) 按实体返回结果。"""

    def __init__(self, positions: list[Any], skills: list[Any], queue_rows: list[Any] | None = None) -> None:
        self._positions = positions
        self._skills = skills
        self._queue = queue_rows or []
        self.added: list[Any] = []
        self.committed = False

    async def execute(self, stmt: Any) -> Any:
        # 识别 select 目标表
        from sqlalchemy import Select

        from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
        from app.models.orphan_cleanup import OrphanCleanupQueue

        if isinstance(stmt, Select):
            target = None
            for ent in stmt.column_descriptions:
                target = ent.get("entity", ent.get("type"))
                break
            if target is PositionRecord:
                return _FakeScalarResult(self._positions, columns=["id"])
            if target is SkillRecord:
                return _FakeScalarResult(self._skills, columns=["id"])
            if target is OrphanCleanupQueue:
                return _FakeScalarResult(self._queue, columns=["row"])
            if target is PositionSkillRelation:
                return _FakeScalarResult([], columns=["row"])
        return _FakeScalarResult([], columns=[])

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True
        # 模拟入队：把 added 的 OrphanCleanupQueue 追加进 _queue
        self._queue.extend(self.added)
        self.added = []


class _FakeScalarResult:
    def __init__(self, rows: list[Any], columns: list[str]) -> None:
        self._rows = rows
        self._columns = columns

    def all(self) -> list[Any]:
        return self._rows

    def scalars(self) -> _FakeScalarResult:
        return self

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None


class _Row:
    """fake ORM row 基元：支持 r[0]/r[1] 下标（模拟 column select 的 tuple 行）。"""

    def __init__(self, id: Any, name: str | None = None) -> None:
        self.id = id
        self.name = name

    def __getitem__(self, key: Any) -> Any:
        return {0: self.id, 1: self.name, "id": self.id, "name": self.name}[key]


class _QueueRow:
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDetectOrphans:
    async def test_orphan_with_stale_canonical_id(self) -> None:
        """canonical_id 指向不存在的 PG 行 → 孤儿 (orphan_canonical_id)。"""
        pg = _FakePgSession(positions=[_Row(uuid.uuid4(), "A")], skills=[])
        driver = _FakeDriver(_FakeNeo4jSession(
            position_nodes=[{"canonical_id": "dead-cid", "name": "Old", "in_degree": 0}],
            skill_nodes=[],
        ))
        scan = await RepairEngine(driver).detect_orphans(pg)
        assert isinstance(scan, OrphanScanResult)
        assert scan.orphan_positions == 1
        assert scan.items[0].reason == "orphan_canonical_id"
        assert scan.items[0].canonical_id == "dead-cid"

    async def test_node_without_canonical_id_unmatched_is_orphan(self) -> None:
        """无 canonical_id 且 name 不匹配 PG → 孤儿 (no_canonical_id)。"""
        pg = _FakePgSession(positions=[_Row(uuid.uuid4(), "Real Position")], skills=[])
        driver = _FakeDriver(_FakeNeo4jSession(
            position_nodes=[{"canonical_id": None, "name": "Ghost Node", "in_degree": 0}],
            skill_nodes=[],
        ))
        scan = await RepairEngine(driver).detect_orphans(pg)
        assert scan.orphan_positions == 1
        assert scan.items[0].reason == "no_canonical_id"

    async def test_node_without_canonical_id_name_matches_is_unlinked_not_orphan(self) -> None:
        """无 canonical_id 但 name 匹配 PG 行 → 未链接（自动修复目标），非孤儿。"""
        pid = uuid.uuid4()
        pg = _FakePgSession(positions=[_Row(pid, "Backend Engineer")], skills=[])
        driver = _FakeDriver(_FakeNeo4jSession(
            position_nodes=[{"canonical_id": None, "name": "Backend Engineer", "in_degree": 0}],
            skill_nodes=[],
        ))
        scan = await RepairEngine(driver).detect_orphans(pg)
        assert scan.orphan_positions == 0
        assert scan.unlinked_positions == 1

    async def test_referenced_orphan_has_in_degree(self) -> None:
        """孤儿被引用（in_degree>0）→ referenced_by 记录，供审批 UI 警示。"""
        pg = _FakePgSession(positions=[], skills=[])
        driver = _FakeDriver(_FakeNeo4jSession(
            position_nodes=[],
            skill_nodes=[{"canonical_id": "ghost-skill", "name": "GhostSkill", "in_degree": 3}],
        ))
        scan = await RepairEngine(driver).detect_orphans(pg)
        assert scan.orphan_skills == 1
        assert scan.items[0].referenced_by == 3


class TestSyncOrphanQueue:
    async def test_dedup_pending_entries(self) -> None:
        """同一孤儿重复同步不重复入队。"""

        existing = _QueueRow(
            id=uuid.uuid4(), node_type="position", name="Ghost", canonical_id="dead",
            reason="orphan_canonical_id", status=STATUS_PENDING, created_at=None,
            reviewed_at=None, reviewed_by=None, detail={},
        )
        pg = _FakePgSession(positions=[], skills=[], queue_rows=[existing])
        driver = _FakeDriver(_FakeNeo4jSession(
            position_nodes=[{"canonical_id": "dead", "name": "Ghost", "in_degree": 0}],
            skill_nodes=[],
        ))
        result = await RepairEngine(driver).sync_orphan_queue(pg)
        # 不重复入队: 队列仍只有 1 条 pending（存量条目仅刷新 referenced_by，非新增）
        assert len(pg._queue) == 1
        assert result == 1  # 1 条存量条目被刷新（P3a: 返回 new + updated）


class TestExecuteCleanup:
    async def test_approve_deletes_and_audits(self, monkeypatch: Any) -> None:
        """approve → DETACH DELETE + 状态 cleaned + 审计日志。"""

        queue_id = uuid.uuid4()
        item = _QueueRow(
            id=queue_id, node_type="position", name="Ghost", canonical_id="dead",
            reason="orphan_canonical_id", status=STATUS_PENDING, created_at=None,
            reviewed_at=None, reviewed_by=None, detail={},
        )
        pg = _FakePgSession(positions=[], skills=[], queue_rows=[item])

        # driver 的 run 返回单条删除计数
        driver = _FakeDriver(_FakeNeo4jSession(position_nodes=[], skill_nodes=[]))

        async def _run(query: str, **params: Any) -> Any:
            if "DETACH DELETE" in query:
                return _FakeCypherResult([_FakeRecord({"deleted": 1})])
            return _FakeCypherResult([])
        driver.session().run = _run  # type: ignore[method-assign]

        audit_entries: list[str] = []

        def _fake_audit(entry: Any) -> None:
            audit_entries.append(entry.action)

        # audit_log 在 execute_cleanup 内 `from app.utils.audit import ...` 局部导入
        monkeypatch.setattr("app.utils.audit.audit_log", _fake_audit)

        result = await RepairEngine(driver).execute_cleanup(
            pg, queue_id, action="approve", actor="admin:u1",
        )
        assert result["status"] == STATUS_CLEANED
        assert result["deleted"] == 1
        assert "orphan_cleanup_approve" in audit_entries

    async def test_reject_marks_only(self) -> None:
        """reject → 仅标记状态，不删除。"""

        queue_id = uuid.uuid4()
        item = _QueueRow(
            id=queue_id, node_type="skill", name="GhostSkill", canonical_id=None,
            reason="no_canonical_id", status=STATUS_PENDING, created_at=None,
            reviewed_at=None, reviewed_by=None, detail={},
        )
        pg = _FakePgSession(positions=[], skills=[], queue_rows=[item])
        driver = _FakeDriver(_FakeNeo4jSession(position_nodes=[], skill_nodes=[]))

        result = await RepairEngine(driver).execute_cleanup(
            pg, queue_id, action="reject", actor="admin:u1",
        )
        assert result["status"] == STATUS_REJECTED


class TestEnsureProjection:
    async def test_only_projects_missing(self) -> None:
        """已投影的节点跳过；缺失的补齐（幂等）。"""
        from app.models.extraction_models import PositionRecord

        pos = PositionRecord(id=uuid.uuid4(), name="New Pos", review_status="approved")
        pg = _FakePgSession(positions=[pos], skills=[])
        # Neo4j 已有该节点 canonical_id → 应跳过
        driver = _FakeDriver(_FakeNeo4jSession(
            position_nodes=[{"canonical_id": str(pos.id), "name": pos.name, "in_degree": 0}],
            skill_nodes=[],
        ))
        result = await RepairEngine(driver).ensure_projection(pg)
        assert result["nodes_projected"] == 0
        assert result["errors"] == []
