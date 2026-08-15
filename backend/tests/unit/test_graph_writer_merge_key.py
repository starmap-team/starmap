"""Phase 23 Task 2 — MERGE key name→canonical_id (checkpoint:decision) tests.

断言：
- merge_position / merge_skill 的 MERGE 键含 canonical_id（query 嗅探）
- 缺 canonical_id 时 raise GraphProjectionError（不再静默产生孤儿）
- create_requires_relationship 端点按 canonical_id MATCH（保留 name 兼容）
- get_position_skills 读路径按 canonical_id MATCH
- run_build_graph_from_extractions 传给 batch_write_extractions 的 canonical_ids_list 非空
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.extraction.graph_writer import (
    create_requires_relationship,
    get_position_skills,
    merge_position,
    merge_skill,
)
from app.exceptions import GraphProjectionError
from app.tasks import stage3_services as s

# ── Fake Neo4j session / driver ─────────────────────────────────────────────


class _FakeAsyncResult:
    def __init__(self, records: list) -> None:
        self._records = list(records)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._records):
            raise StopAsyncIteration
        rec = self._records[self._idx]
        self._idx += 1
        return rec

    async def single(self):
        return self._records[0] if self._records else None


class _FakeAsyncSession:
    def __init__(self, run_side_effect=None):
        self._run_side_effect = run_side_effect
        self.calls: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def run(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._run_side_effect is not None:
            if callable(self._run_side_effect):
                return self._run_side_effect(*args, **kwargs)
            return self._run_side_effect
        return _FakeAsyncResult([])


class _FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


def _capturing_session(query_branch):
    """Session that branches on query string and records the last query + params."""

    def smart_run(*args, **kwargs):
        captured = query_branch[0]
        captured["query"] = args[0] if args else ""
        captured["kwargs"] = kwargs
        return _FakeAsyncResult(query_branch[1])

    return _FakeAsyncSession(run_side_effect=smart_run)


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    async def _instant(*a, **kw):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


# ── merge_position / merge_skill MERGE key 嗅探 ─────────────────────────────


class TestMergeKeySniff:
    @pytest.mark.asyncio
    async def test_merge_position_merges_by_canonical_id(self) -> None:
        captured: dict = {}
        session = _capturing_session((captured, [{"p": {"name": "Dev"}}]))
        await merge_position(_FakeDriver(session), {"name": "Dev"}, canonical_id="pos-1")

        q = captured["query"]
        assert "MERGE (p:Position {canonical_id: $canonical_id})" in q
        assert "{name: $name}" not in q  # name 不再是 MERGE 键
        assert captured["kwargs"]["canonical_id"] == "pos-1"
        # name 降级为 SET 属性
        assert "p.name = $name" in q

    @pytest.mark.asyncio
    async def test_merge_skill_merges_by_canonical_id(self) -> None:
        captured: dict = {}
        session = _capturing_session((captured, [{"s": {"name": "Python"}}]))
        with patch("app.core.trust.entity_trust.EntityTrustScorer") as mock_scorer:
            mock_scorer.return_value.score.return_value = 0.5
            await merge_skill(_FakeDriver(session), "Python", {"source_count": 5}, canonical_id="sk-1")

        q = captured["query"]
        assert "MERGE (s:Skill {canonical_id: $canonical_id})" in q
        assert "{name: $name}" not in q
        assert "s.name = $name" in q  # name 降级为 SET 属性

    @pytest.mark.asyncio
    async def test_merge_position_missing_canonical_id_raises(self) -> None:
        session = _capturing_session(({}, [{"p": {"name": "Dev"}}]))
        with pytest.raises(GraphProjectionError, match="requires canonical_id"):
            await merge_position(_FakeDriver(session), {"name": "Dev"})

    @pytest.mark.asyncio
    async def test_merge_skill_missing_canonical_id_raises(self) -> None:
        session = _capturing_session(({}, [{"s": {"name": "Python"}}]))
        with pytest.raises(GraphProjectionError, match="requires canonical_id"):
            await merge_skill(_FakeDriver(session), "Python")

    @pytest.mark.asyncio
    async def test_same_id_idempotent_key(self) -> None:
        """同 canonical_id → MERGE 命中同一节点（键语义），不同 id 各自独立节点。"""
        captured: dict = {}
        session = _capturing_session((captured, [{"p": {"name": "Dev"}}]))
        # 同 name 同 id 两次 merge → 键相同（幂等）
        await merge_position(_FakeDriver(session), {"name": "Dev"}, canonical_id="pos-1")
        await merge_position(_FakeDriver(session), {"name": "Dev"}, canonical_id="pos-1")
        # 同 name 不同 id → 键不同 → 各自独立节点（MERGE 键 = canonical_id）
        await merge_position(_FakeDriver(session), {"name": "Dev"}, canonical_id="pos-2")
        assert captured["kwargs"]["canonical_id"] == "pos-2"
        # 两次 id 均出现在查询参数中（未发生 name 合并）
        session2 = _capturing_session(({}, [{"p": {"name": "Dev"}}]))
        await merge_position(_FakeDriver(session2), {"name": "Dev"}, canonical_id="pos-1")
        await merge_position(_FakeDriver(session2), {"name": "Dev"}, canonical_id="pos-2")
        assert session2.calls[0][1]["canonical_id"] == "pos-1"
        assert session2.calls[1][1]["canonical_id"] == "pos-2"


# ── REQUIRES 端点 / 读路径按 canonical_id MATCH ─────────────────────────────


class TestRelationshipEndpoint:
    @pytest.mark.asyncio
    async def test_create_requires_matches_by_canonical_id(self) -> None:
        captured: dict = {}
        session = _capturing_session((captured, [{"r": {"weight": 1.0}}]))
        await create_requires_relationship(
            _FakeDriver(session), "Dev", "Python", level="advanced",
            position_canonical_id="pos-1", skill_canonical_id="sk-1",
        )
        q = captured["query"]
        assert "MATCH (p:Position {canonical_id: $position_canonical_id})" in q
        assert "MATCH (s:Skill {canonical_id: $skill_canonical_id})" in q
        assert captured["kwargs"]["position_canonical_id"] == "pos-1"
        assert captured["kwargs"]["skill_canonical_id"] == "sk-1"

    @pytest.mark.asyncio
    async def test_create_requires_name_fallback_compat(self) -> None:
        """未传 canonical_id → 保留 name MATCH 兼容（读/补丁路径）。"""
        captured: dict = {}
        session = _capturing_session((captured, [{"r": {"weight": 1.0}}]))
        await create_requires_relationship(_FakeDriver(session), "Dev", "Python")
        q = captured["query"]
        assert "MATCH (p:Position {name: $position_name})" in q
        assert "MATCH (s:Skill {name: $skill_name})" in q

    @pytest.mark.asyncio
    async def test_get_position_skills_matches_by_canonical_id(self) -> None:
        records = [{"skill_name": "Python", "level": "advanced", "required": True}]
        captured: dict = {}
        session = _capturing_session((captured, records))
        r = await get_position_skills(_FakeDriver(session), "Dev", position_canonical_id="pos-1")
        assert len(r["required"]) == 1
        assert "MATCH (p:Position {canonical_id: $position_canonical_id})" in captured["query"]

    @pytest.mark.asyncio
    async def test_get_position_skills_name_fallback(self) -> None:
        records = [{"skill_name": "Go", "level": "beginner", "required": False}]
        captured: dict = {}
        session = _capturing_session((captured, records))
        r = await get_position_skills(_FakeDriver(session), "Dev")
        assert len(r["preferred"]) == 1
        assert "MATCH (p:Position {name: $name})" in captured["query"]


# ── run_build_graph_from_extractions 补传 canonical_ids_list ────────────────


class _RowsResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _ScalarsResult:
    def __init__(self, items: list) -> None:
        self._scalars = _Scalars(items)

    def scalars(self) -> _Scalars:
        return self._scalars


class _Scalars:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class _BuildSession:
    """run_build_graph_from_extractions 专用 fake session：按表名分支返回结果。"""

    def __init__(self, record, pos_rows: list) -> None:
        self._record = record
        self._pos_rows = pos_rows

    async def __aenter__(self) -> _BuildSession:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, stmt):
        sql = str(stmt)
        if "jd_extraction_records" in sql:
            return _ScalarsResult([self._record])
        if "position_records" in sql:
            return _RowsResult(self._pos_rows)
        if "skill_records" in sql and "INSERT" not in sql:
            return _RowsResult([])
        return _ScalarsResult([])

    async def commit(self) -> None:
        pass


class _DummyDriverCtx:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> bool:
        return False


class TestRunBuildGraphCanonicalIds:
    @pytest.mark.asyncio
    async def test_passes_canonical_ids_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pos_id = uuid.uuid4()
        record = SimpleNamespace(
            id=1,
            extracted_skills=None,
            job_title="SRE",
            experience_years=5,
            education="BS",
            created_at=SimpleNamespace(),
            to_extraction_payload=lambda: {
                "position_name": "SRE",
                "required_skills": [{"name": "Python"}],
                "preferred_skills": [],
                "experience_required": 5,
                "education_required": "BS",
            },
        )
        fake_session = _BuildSession(record, pos_rows=[("SRE", pos_id)])

        def fake_sessionmaker() -> _BuildSession:
            return fake_session

        monkeypatch.setattr("app.db.session.get_async_engine", lambda: SimpleNamespace(dispose=AsyncMock()))
        monkeypatch.setattr(s, "async_sessionmaker", lambda *_a, **_kw: fake_sessionmaker)
        monkeypatch.setattr(s, "GraphConfig", lambda: SimpleNamespace(get_driver=lambda: _DummyDriverCtx()))

        captured: dict = {}

        async def fake_batch_write_extractions(extractions, driver, canonical_ids_list=None) -> list:
            captured["canonical_ids_list"] = canonical_ids_list
            captured["extractions"] = extractions
            return [{"triples_merged": 3, "relationships_touched": 2}]

        monkeypatch.setattr(s, "batch_write_extractions", fake_batch_write_extractions)

        result = await s.run_build_graph_from_extractions(limit=10)

        assert result["status"] == "completed"
        assert captured["canonical_ids_list"], "canonical_ids_list 必须非空（Task 2 关键配套）"
        cids = captured["canonical_ids_list"][0]
        assert cids["position_id"] == str(pos_id)
        assert captured["extractions"][0]["position_name"] == "SRE"
