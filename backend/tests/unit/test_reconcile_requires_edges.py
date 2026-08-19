"""Phase 23 Task 3 — /admin/reconcile-neo4j REQUIRES 边对账 (IC-05) + skills_synced bug.

Covers:
- 边计数（Neo4j REQUIRES vs PG approved PSR）
- ±0.5% 容差内 → ok；超容差/节点差≤1 → warn；否则 critical（参数化健康三档）
- PG 计数限定 review_status='approved'
- ReconcileResult 新字段存在
- ProjectionResult.skills_upserted 分离（修 skills_synced 复制粘贴 bug）
- GraphProjector.reconcile_all 边层补缺（approved PSR → apply_batch relations）
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.admin import reconcile_neo4j_endpoint
from app.schemas.admin import ReconcileResult
from app.services.graph_projector import GraphProjector

# ── Fake Neo4j driver（按查询分支返回计数）─────────────────────────────────


class _FakeNeo4jSession:
    def __init__(self, pos: int, skl: int, requires: int) -> None:
        self._counts = {"pos": pos, "skl": skl, "requires": requires}

    async def __aenter__(self) -> _FakeNeo4jSession:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def run(self, query: str, **kwargs):
        q = str(query)
        if "REQUIRES" in q:
            c = self._counts["requires"]
        elif ":Position" in q:
            c = self._counts["pos"]
        elif ":Skill" in q:
            c = self._counts["skl"]
        else:
            c = 0
        return SimpleNamespace(single=AsyncMock(return_value={"c": c}))


class _FakeDriver:
    def __init__(self, pos: int, skl: int, requires: int) -> None:
        self._pos, self._skl, self._requires = pos, skl, requires

    def session(self) -> _FakeNeo4jSession:
        return _FakeNeo4jSession(self._pos, self._skl, self._requires)


# ── Fake PG session（按 SQL 分支返回 scalar 计数）───────────────────────────


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar(self) -> int:
        return self._value


class _FakePgSession:
    def __init__(self, pos: int, skl: int, pg_requires: int) -> None:
        self._pos, self._skl, self._pg_requires = pos, skl, pg_requires
        self.captured_stmts: list[str] = []

    async def __aenter__(self) -> _FakePgSession:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, stmt):
        sql = str(stmt)
        self.captured_stmts.append(sql)
        if "position_skill_relations" in sql and "review_status" in sql:
            return _ScalarResult(self._pg_requires)
        if "position_records" in sql:
            return _ScalarResult(self._pos)
        if "skill_records" in sql:
            return _ScalarResult(self._skl)
        return _ScalarResult(0)  # audit INSERT

    async def commit(self) -> None:
        pass


def _patch_projector(monkeypatch: pytest.MonkeyPatch, **result_kwargs) -> None:
    """Patch GraphProjector.reconcile_all to return a fake ProjectionResult.

    reconcile_neo4j_endpoint 在函数体内 `from app.services.graph_projector import
    GraphProjector`（调用时解析）→ patch 源头模块。
    """
    fake_result = SimpleNamespace(**{
        "nodes_upserted": 0,
        "skills_upserted": 0,
        "orphans_pruned": 0,
        "edges_upserted": 0,
        **result_kwargs,
    })
    mock_cls = MagicMock()
    mock_cls.return_value.reconcile_all = AsyncMock(return_value=fake_result)
    monkeypatch.setattr("app.services.graph_projector.GraphProjector", mock_cls)


async def _run_endpoint(session: _FakePgSession, driver: _FakeDriver) -> ReconcileResult:
    return await reconcile_neo4j_endpoint(session=session, driver=driver)


class TestReconcileEdgeCounting:
    @pytest.mark.asyncio
    async def test_returns_edge_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Neo4j REQUIRES vs PG approved PSR 计数正确进入结果。"""
        _patch_projector(monkeypatch, nodes_upserted=3, skills_upserted=5, orphans_pruned=0)
        session = _FakePgSession(pos=10, skl=20, pg_requires=100)
        driver = _FakeDriver(pos=10, skl=20, requires=97)  # diff=3, tolerance=1

        result = await _run_endpoint(session, driver)

        assert isinstance(result, ReconcileResult)
        assert result.requires_in_neo4j == 97
        assert result.requires_in_pg == 100
        assert result.requires_diff == 3
        assert result.health == "warn"  # 3 > tolerance(1)

    @pytest.mark.asyncio
    async def test_pg_query_limits_to_approved_positions(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PG 侧计数必须限定 review_status='approved'（Neo4j 只投影 approved）。"""
        _patch_projector(monkeypatch)
        session = _FakePgSession(pos=10, skl=20, pg_requires=50)
        driver = _FakeDriver(pos=10, skl=20, requires=50)

        await _run_endpoint(session, driver)

        psr_stmt = next(
            s for s in session.captured_stmts
            if "position_skill_relations" in s and "review_status" in s
        )
        assert "review_status" in psr_stmt
        assert "position_records" in psr_stmt  # JOIN position_records

    @pytest.mark.asyncio
    async def test_skills_synced_uses_skills_upserted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """skills_synced 必须来自 ProjectionResult.skills_upserted（bug 修复）。"""
        _patch_projector(monkeypatch, nodes_upserted=7, skills_upserted=3)
        session = _FakePgSession(pos=10, skl=20, pg_requires=50)
        driver = _FakeDriver(pos=10, skl=20, requires=50)

        result = await _run_endpoint(session, driver)

        assert result.skills_synced == 3
        assert result.skills_synced != 7  # 不再误用 nodes_upserted
        assert result.positions_synced == 7


class TestReconcileHealthTiers:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("neo4j_pos", "pg_pos", "neo4j_skl", "pg_skl", "neo4j_req", "pg_req", "expected"),
        [
            # ok: 节点全等 + 边在 ±0.5% 容差内（pg=1000 → tolerance=5, diff=3）
            (100, 100, 200, 200, 997, 1000, "ok"),
            # warn: 边超容差（diff=6 > tolerance=5）
            (100, 100, 200, 200, 994, 1000, "warn"),
            # warn: 节点差 ≤1
            (101, 100, 200, 200, 1000, 1000, "warn"),
            # critical: 节点差 >1 且边在容差内
            (105, 100, 200, 200, 1000, 1000, "critical"),
            # warn: 边超容差（即使节点差 >1，"边超容差"即 warn）
            (105, 100, 205, 200, 990, 1000, "warn"),
        ],
    )
    async def test_health_tiers(
        self, monkeypatch: pytest.MonkeyPatch,
        neo4j_pos: int, pg_pos: int, neo4j_skl: int, pg_skl: int,
        neo4j_req: int, pg_req: int, expected: str,
    ) -> None:
        _patch_projector(monkeypatch)
        session = _FakePgSession(pos=pg_pos, skl=pg_skl, pg_requires=pg_req)
        driver = _FakeDriver(pos=neo4j_pos, skl=neo4j_skl, requires=neo4j_req)

        result = await _run_endpoint(session, driver)

        assert result.health == expected


class TestProjectionResultSkillsUpserted:
    @pytest.mark.asyncio
    async def test_apply_batch_separates_position_and_skill_counts(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Position 分支 → nodes_upserted；Skill 分支 → skills_upserted（计数分离）。"""
        class _RunResult:
            pass

        captured: list = []

        class _Neo4jSession:
            async def __aenter__(self) -> _Neo4jSession:
                return self

            async def __aexit__(self, *_a: object) -> bool:
                return False

            async def run(self, query: str, **kwargs):
                captured.append((query, kwargs))
                return SimpleNamespace()

        class _Driver:
            def session(self) -> _Neo4jSession:
                return _Neo4jSession()

        projector = GraphProjector(_Driver())
        result = await projector.apply_batch(
            positions=[{"canonical_id": "p1", "name": "Dev"}],
            skills=[{"canonical_id": "s1", "name": "Python"}],
        )

        assert result.nodes_upserted == 1
        assert result.skills_upserted == 1
        assert result.edges_upserted == 0
        # to_dict 同步含 skills_upserted
        assert result.to_dict()["skills_upserted"] == 1

    @pytest.mark.asyncio
    async def test_reconcile_requires_edges_backfills_approved_edges(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """边层补缺：PG approved PSR → apply_batch relations（只补不删，无 DELETE）。"""
        class _PgSession:
            async def execute(self, stmt):
                rows = [
                    ("pos-1", "sk-1", "required", 0.9),
                    ("pos-1", "sk-2", "preferred", 0.7),
                ]
                return SimpleNamespace(all=lambda: rows)

            async def __aenter__(self) -> _PgSession:
                return self

            async def __aexit__(self, *_a: object) -> bool:
                return False

        edge_calls: list = []
        deletes: list = []

        class _Neo4jSession:
            async def __aenter__(self) -> _Neo4jSession:
                return self

            async def __aexit__(self, *_a: object) -> bool:
                return False

            async def run(self, query: str, **kwargs):
                if "DELETE" in str(query):
                    deletes.append(str(query))
                return SimpleNamespace()

        class _Driver:
            def session(self) -> _Neo4jSession:
                return _Neo4jSession()

        projector = GraphProjector(_Driver())
        original_apply_batch = GraphProjector.apply_batch

        async def spy_apply_batch(self, **kwargs):
            if kwargs.get("relations"):
                edge_calls.extend(kwargs["relations"])
            return await original_apply_batch(self, **kwargs)

        monkeypatch.setattr(GraphProjector, "apply_batch", spy_apply_batch)

        result = await projector._reconcile_requires_edges(_PgSession())

        assert result.edges_upserted == 2
        assert len(edge_calls) == 2
        assert edge_calls[0]["position_canonical_id"] == "pos-1"
        assert edge_calls[0]["skill_canonical_id"] == "sk-1"
        assert edge_calls[1]["requirement_type"] == "preferred"
        # 只补缺不自动删：边对账路径无任何 DELETE 语句
        assert deletes == []


class TestReconcileResultSchema:
    def test_schema_has_edge_fields(self) -> None:
        """ReconcileResult 新字段存在且类型正确。"""
        fields = ReconcileResult.model_fields
        assert "requires_in_neo4j" in fields
        assert "requires_in_pg" in fields
        assert "requires_diff" in fields
        # 约束：ge=0 且含 description
        assert fields["requires_diff"].metadata
        result = ReconcileResult()
        assert result.requires_in_neo4j == 0
        assert result.requires_in_pg == 0
        assert result.requires_diff == 0


class TestReconcileAllApprovedGate:
    """Phase 23 核验修复 (M1b 闭环): reconcile_all 节点快照必须限定 approved。

    Bug: reconcile_all 的 pg_pos_ids 快照曾取全量岗位（含 pending_review），导致
    每次 reconcile 把待审岗位回灌图谱（孤儿剪枝后又被回填，Neo4j 184→359）。
    修复后 PositionRecord 快照查询必须含 review_status == 'approved' 过滤。
    """

    def test_pg_position_snapshot_filters_approved(self) -> None:
        """捕获 reconcile_all 内 PositionRecord 快照 SQL，断言含 approved 过滤。"""

        captured: list[str] = []

        class _FakePgSession:
            async def execute(self, stmt: object, *a: object, **k: object):
                captured.append(str(stmt))
                return SimpleNamespace(all=lambda: [])  # 无快照 → 无回填无剪枝

        class _FakeNeo4jRun:
            def __init__(self) -> None:
                self._rows: list = []

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self._rows:
                    raise StopAsyncIteration
                return self._rows.pop(0)

        class _FakeNeo4jSession:
            async def __aenter__(self) -> _FakeNeo4jSession:
                return self

            async def __aexit__(self, *_a: object) -> bool:
                return False

            async def run(self, query: str, **kwargs):
                return _FakeNeo4jRun()

        class _FakeDriver:
            def session(self):
                # Phase 24: reconcile_all 新增 null-cid 孤儿清理会多次开 session——
                # 无限返回新 session（此前 pop 固定 2 个越界）
                return _FakeNeo4jSession()

        projector = GraphProjector.__new__(GraphProjector)
        projector._driver = _FakeDriver()

        import asyncio

        asyncio.run(projector.reconcile_all(_FakePgSession()))

        # 找到 PositionRecord 快照查询并断言 approved 过滤
        pos_queries = [c for c in captured if "position_records" in c and "id" in c]
        assert pos_queries, "reconcile_all 必须查询 position_records"
        for q in pos_queries:
            if "SELECT position_records.id" in q or "FROM position_records" in q:
                # 快照查询必须限定 review_status（SQLAlchemy 绑定参数形式）
                assert "review_status" in q, f"PositionRecord 快照查询缺少审核过滤: {q}"
                return
        pytest.fail(f"未找到 PositionRecord 快照查询: {captured}")


class TestReconcileEndpointPgPosApproved:
    """Phase 23 核验修复 (M1b 闭环): reconcile 端点 PG 计数必须限定 approved。

    Bug: admin.py pg_pos 曾取全量岗位计数 (359) vs Neo4j 184 → nodes_equal False
    → 健康度误报 critical。修复后 count 查询必须含 review_status 过滤。
    """

    @pytest.mark.asyncio
    async def test_pg_pos_query_contains_approved_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """嗅探 reconcile_neo4j_endpoint 内 count(PositionRecord) 查询。"""
        captured: list[str] = []

        class _CapturingPgSession(_FakePgSession):
            async def execute(self, stmt: object, *a: object, **k: object):
                captured.append(str(stmt))
                return await super().execute(stmt, *a, **k)

        _patch_projector(monkeypatch, nodes_upserted=0, skills_upserted=0, orphans_pruned=0)
        session = _CapturingPgSession(pos=184, skl=822, pg_requires=1002)
        driver = _FakeDriver(pos=184, skl=822, requires=1002)  # diff=0 → ok

        result = await _run_endpoint(session, driver)

        assert result.health == "ok", f"184=184 diff=0 应为 ok，实际 {result.health}"
        pos_counts = [c for c in captured if "position_records" in c and "count" in c]
        assert pos_counts, f"必须查询 position_records 计数: {captured}"
        assert any("review_status" in c for c in pos_counts), (
            f"position_records 计数查询必须限定 review_status: {pos_counts}"
        )
