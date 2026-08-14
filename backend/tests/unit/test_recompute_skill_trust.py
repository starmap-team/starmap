"""Coverage: services/graph_sync.py recompute_skill_trust — 全量重算 Skill.trust_score (Phase 19)。

验证 §6.2 四因子重算写回 Neo4j：幂等、正确传 trust、driver None 降级。
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.graph_sync import recompute_skill_trust

NOW = datetime.now(UTC)


class _FakeAsyncResult:
    def __init__(self) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncResult:
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def run(self, *args: Any, **kwargs: Any) -> None:
        pass


class _FakeNeo4jSession:
    def __init__(self) -> None:
        self.runs: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def __aenter__(self) -> _FakeNeo4jSession:
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def run(self, *args: Any, **kwargs: Any) -> None:
        self.runs.append((args, kwargs))


class _FakeDriver:
    def __init__(self) -> None:
        self.session_obj = _FakeNeo4jSession()

    def session(self) -> _FakeNeo4jSession:
        return self.session_obj


class _FakeSession:
    """PG session: 第一次 execute 返回技能行, 第二次返回置信度行。"""

    def __init__(self, skills: list[Any], confs: list[Any]) -> None:
        self._skills = skills
        self._confs = confs
        self._calls = 0

    async def execute(self, _stmt: Any) -> SimpleNamespace:
        self._calls += 1
        if self._calls == 1:
            return SimpleNamespace(all=lambda: self._skills)
        return SimpleNamespace(all=lambda: self._confs)


def _skill(name: str, source_count: int, last: Any) -> SimpleNamespace:
    return SimpleNamespace(id="cid-1" if name == "Python" else "cid-2", name=name, source_count=source_count, last_detected_at=last)


def _conf(title: str, confidence: float) -> tuple[str, float | None]:
    # SQLAlchemy Row 可按位置解包 (title, confidence)
    return (title, confidence)


class TestRecomputeSkillTrust:
    async def test_driver_none_is_noop(self) -> None:
        out = await recompute_skill_trust(_FakeSession([], []), None)
        assert out == {"skills": 0, "updated": 0}

    async def test_writes_trust_for_each_skill(self) -> None:
        driver = _FakeDriver()
        skills = [
            _skill("Python", 10, NOW),     # 高频 + 有置信度
            _skill("Go", 1, NOW),          # 低频
        ]
        confs = [_conf("Python", 0.9)]
        out = await recompute_skill_trust(_FakeSession(skills, confs), driver)
        assert out["skills"] == 2
        assert out["updated"] == 2
        assert len(driver.session_obj.runs) == 2

        # Python: source=10→1.0, conf=0.9, cross=1.0, time=1.0 → 0.3+0.27+0.25+0.15=0.97
        py_run = driver.session_obj.runs[0]
        assert py_run[1]["cid"] == "cid-1"
        assert py_run[1]["trust"] == pytest.approx(0.97, abs=0.001)
        # Go: source=1→0.316, conf 缺省→0.5, cross=0, time=1.0 → 0.095+0.15+0.15=0.395
        go_run = driver.session_obj.runs[1]
        assert go_run[1]["cid"] == "cid-2"
        assert 0.3 < go_run[1]["trust"] < 0.5

    async def test_idempotent_same_inputs(self) -> None:
        driver1, driver2 = _FakeDriver(), _FakeDriver()
        skills = [_skill("Python", 5, NOW)]
        confs = [_conf("Python", 0.8)]
        out1 = await recompute_skill_trust(_FakeSession(skills, confs), driver1)
        out2 = await recompute_skill_trust(_FakeSession(skills, confs), driver2)
        assert out1 == out2
        assert driver1.session_obj.runs[0][1]["trust"] == driver2.session_obj.runs[0][1]["trust"]

    async def test_no_confidence_falls_back_neutral(self) -> None:
        driver = _FakeDriver()
        skills = [_skill("Rust", 0, None)]  # 无来源、无置信、无检测时间
        out = await recompute_skill_trust(_FakeSession(skills, []), driver)
        assert out["updated"] == 1
        # source=0→0, conf=None→0.5, cross=0, time=None→0 → 0.15
        assert driver.session_obj.runs[0][1]["trust"] == pytest.approx(0.15, abs=0.001)
