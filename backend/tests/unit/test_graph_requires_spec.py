"""Phase 23 Task 6 — REQUIRES 边属性契约收敛（DC-05）tests.

以 ``r.requirement_type ∈ {'required','preferred'}`` 为唯一真值：
- ``create_requires_relationship`` SET 写 ``r.requirement_type``（与演化投影
  ``graph_projection._PROJECT_QUERY`` 对齐，两条写路径契约一致）；
- ``get_position_skills`` 优先读 ``r.requirement_type``，历史边（无该属性）回退
  ``r.required``（缺省 True 兼容）。

存量数据一次性回填（幂等，兼容旧边）——Neo4j 侧执行一次即可：
    MATCH (:Position)-[r:REQUIRES]->(:Skill)
    WHERE r.requirement_type IS NULL
    SET r.requirement_type = CASE WHEN coalesce(r.required, true)
                                  THEN 'required' ELSE 'preferred' END

断言清单：
- SET 子句含 ``r.requirement_type = $requirement_type``（canonical_id + name 回退两分支）
- RETURN 子句含 ``r.requirement_type AS requirement_type``
- requirement_type='preferred' 假 record → 读为 preferred
- 历史边无 requirement_type → 回退 r.required（True→required / False→preferred）
"""
from __future__ import annotations

import pytest

from app.core.extraction.graph_writer import create_requires_relationship, get_position_skills

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

    async def __aexit__(self, *_args: object) -> bool:
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


def _capturing_session(records: list) -> tuple[dict, _FakeAsyncSession]:
    """Capture the last query string + kwargs while returning fixed records."""
    captured: dict = {}

    def smart_run(*args, **kwargs):
        captured["query"] = args[0] if args else ""
        captured["kwargs"] = kwargs
        return _FakeAsyncResult(records)

    return captured, _FakeAsyncSession(run_side_effect=smart_run)


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    async def _instant(*_a, **_kw):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


# ── 写路径：create_requires_relationship SET 契约 ───────────────────────────


class TestRequiresWriteContract:
    @pytest.mark.asyncio
    async def test_set_contains_requirement_type_canonical_branch(self) -> None:
        captured, session = _capturing_session([{"r": {"weight": 1.0}}])
        await create_requires_relationship(
            _FakeDriver(session), "Dev", "Python", level="advanced", required=True,
            position_canonical_id="pos-1", skill_canonical_id="sk-1",
        )
        q = captured["query"]
        assert "r.requirement_type = $requirement_type" in q
        assert captured["kwargs"]["requirement_type"] == "required"

    @pytest.mark.asyncio
    async def test_set_contains_requirement_type_name_fallback(self) -> None:
        captured, session = _capturing_session([{"r": {"weight": 1.0}}])
        await create_requires_relationship(
            _FakeDriver(session), "Dev", "Python", level="beginner", required=False,
        )
        q = captured["query"]
        assert "r.requirement_type = $requirement_type" in q
        assert captured["kwargs"]["requirement_type"] == "preferred"

    @pytest.mark.asyncio
    async def test_requirement_type_derived_from_required_when_omitted(self) -> None:
        """未传 requirement_type → 从 required 派生，保证双写路径契约一致。"""
        captured, session = _capturing_session([{"r": {"weight": 1.0}}])
        await create_requires_relationship(
            _FakeDriver(session), "Dev", "Python", required=False,
            position_canonical_id="pos-1", skill_canonical_id="sk-1",
        )
        assert captured["kwargs"]["requirement_type"] == "preferred"

    @pytest.mark.asyncio
    async def test_explicit_requirement_type_wins(self) -> None:
        captured, session = _capturing_session([{"r": {"weight": 1.0}}])
        await create_requires_relationship(
            _FakeDriver(session), "Dev", "Python", required=True,
            requirement_type="preferred",
            position_canonical_id="pos-1", skill_canonical_id="sk-1",
        )
        assert captured["kwargs"]["requirement_type"] == "preferred"


# ── 读路径：get_position_skills 优先读 requirement_type ─────────────────────


class TestRequiresReadContract:
    @pytest.mark.asyncio
    async def test_return_contains_requirement_type_canonical_branch(self) -> None:
        captured, session = _capturing_session(
            [{"skill_name": "Python", "level": "advanced", "requirement_type": "required", "required": True}]
        )
        await get_position_skills(_FakeDriver(session), "Dev", position_canonical_id="pos-1")
        assert "r.requirement_type AS requirement_type" in captured["query"]

    @pytest.mark.asyncio
    async def test_return_contains_requirement_type_name_branch(self) -> None:
        captured, session = _capturing_session(
            [{"skill_name": "Python", "level": "advanced", "requirement_type": "required", "required": True}]
        )
        await get_position_skills(_FakeDriver(session), "Dev")
        assert "r.requirement_type AS requirement_type" in captured["query"]

    @pytest.mark.asyncio
    async def test_preferred_requirement_type_reads_as_preferred(self) -> None:
        """requirement_type='preferred' 的边（演化写回）必须归入 preferred——不再被读成 required。"""
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult(
                [{"skill_name": "Go", "level": "beginner", "requirement_type": "preferred", "required": False}]
            )
        )
        r = await get_position_skills(_FakeDriver(session), "Dev", position_canonical_id="pos-1")
        assert len(r["preferred"]) == 1 and r["preferred"][0]["name"] == "Go"
        assert len(r["required"]) == 0

    @pytest.mark.asyncio
    async def test_required_requirement_type_reads_as_required(self) -> None:
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult(
                [{"skill_name": "Python", "level": "advanced", "requirement_type": "required", "required": True}]
            )
        )
        r = await get_position_skills(_FakeDriver(session), "Dev", position_canonical_id="pos-1")
        assert len(r["required"]) == 1 and r["required"][0]["name"] == "Python"
        assert len(r["preferred"]) == 0

    @pytest.mark.asyncio
    async def test_missing_requirement_type_falls_back_to_required_true(self) -> None:
        """历史边（无 requirement_type）→ 回退 r.required=True → required。"""
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult(
                [{"skill_name": "Python", "level": "advanced", "required": True}]
            )
        )
        r = await get_position_skills(_FakeDriver(session), "Dev")
        assert len(r["required"]) == 1 and len(r["preferred"]) == 0

    @pytest.mark.asyncio
    async def test_missing_requirement_type_falls_back_to_required_false(self) -> None:
        """历史边 → 回退 r.required=False → preferred。"""
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult(
                [{"skill_name": "Go", "level": "beginner", "required": False}]
            )
        )
        r = await get_position_skills(_FakeDriver(session), "Dev")
        assert len(r["preferred"]) == 1 and len(r["required"]) == 0

    @pytest.mark.asyncio
    async def test_missing_requirement_type_and_required_defaults_required(self) -> None:
        """历史边既无 requirement_type 也无 required → 缺省 True → required（兼容）。"""
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult([{"skill_name": "Python", "level": "advanced"}])
        )
        r = await get_position_skills(_FakeDriver(session), "Dev")
        assert len(r["required"]) == 1 and len(r["preferred"]) == 0

    @pytest.mark.asyncio
    async def test_requirement_type_preferred_overrides_stale_required_true(self) -> None:
        """requirement_type 优先：旧边 required=True 但 requirement_type='preferred' → preferred。"""
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult(
                [{"skill_name": "Go", "level": "beginner", "requirement_type": "preferred", "required": True}]
            )
        )
        r = await get_position_skills(_FakeDriver(session), "Dev")
        assert len(r["preferred"]) == 1 and len(r["required"]) == 0
