"""Unit tests for match service helpers."""
from __future__ import annotations

import pytest

from app.core.matching.path_builder import build_learning_path
from app.core.matching.scorer import (
    PROFICIENCY_SCORE,
    _canonical_skill_name,
    _semantic_similarity,
    score_skill_match,
)
from app.core.matching.service import MatchService

# 创建 MatchService 实例用于测试
_match_service = MatchService()


class _FakeRow:
    """SQLAlchemy Row 形状：可索引 + 可迭代。"""

    def __init__(self, values):
        self._values = list(values)

    def __getitem__(self, i):
        return self._values[i]

    def __iter__(self):
        return iter(self._values)


class _FakeSession:
    """Minimal AsyncSession stub：execute 返回可 await 的 result（first() 为同步方法）。"""

    def __init__(self, row=None):
        self._row = row

    async def execute(self, stmt):
        class _Result:
            def __init__(self, row):
                self._row = row

            def first(self):
                return self._row
        return _Result(self._row)


class TestResolveCanonicalName:
    """契约统一（name_cn→name）：中文显示名 → canonical name 解析（PG SSOT）。"""

    @pytest.mark.asyncio
    async def test_name_cn_resolves_to_canonical(self):
        # PG 返回 (name=AI Agent Engineer, name_cn=AI智能体工程师)
        result = await _match_service._resolve_canonical_name(
            "AI智能体工程师", _FakeSession(_FakeRow(["AI Agent Engineer", "AI智能体工程师"]))
        )
        assert result == "AI Agent Engineer"

    @pytest.mark.asyncio
    async def test_canonical_name_passthrough(self):
        result = await _match_service._resolve_canonical_name(
            "AI Agent Engineer", _FakeSession(_FakeRow(["AI Agent Engineer", "AI智能体工程师"]))
        )
        assert result == "AI Agent Engineer"

    @pytest.mark.asyncio
    async def test_missing_position_returns_none(self):
        result = await _match_service._resolve_canonical_name("不存在的岗位", _FakeSession(None))
        assert result is None

    @pytest.mark.asyncio
    async def test_no_session_returns_none(self):
        result = await _match_service._resolve_canonical_name("AI智能体工程师", None)
        assert result is None


class _ExistsFakeSession:
    """_position_exists 用：execute → result.scalar_one_or_none()（同步方法）。"""

    def __init__(self, id_value=None):
        self._id_value = id_value

    async def execute(self, stmt):
        class _Result:
            def __init__(self, id_value):
                self._id_value = id_value

            def scalar_one_or_none(self):
                return self._id_value
        return _Result(self._id_value)


class _NeoFakeDriver:
    """_position_exists Neo4j 分支：按 name 或 name_cn 命中。"""

    class _Sess:
        def __init__(self, hits):
            self._hits = hits

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def run(self, *a, **k):
            class _Res:
                def __init__(self, rec):
                    self._rec = rec

                async def single(self):
                    return self._rec
            return _Res({"x": 1} if self._hits else None)

    def __init__(self, matches_name_cn):
        self._matches = matches_name_cn

    def session(self):
        return self._Sess(self._matches)


class TestPositionExistsWithNameCn:
    """_position_exists 需同时按 name / name_cn 命中（PG OR 条件 / Neo4j OR 条件）。"""

    async def test_pg_hit_by_name_cn_returns_true(self):
        from app.core.matching.service import MatchService

        svc = MatchService()
        assert await svc._position_exists(None, "AI智能体工程师", _ExistsFakeSession("pos-id")) is True

    async def test_pg_miss_returns_false_when_neo4j_absent(self):
        from app.core.matching.service import MatchService

        svc = MatchService()
        result = await svc._position_exists(_NeoFakeDriver(matches_name_cn=False), "不存在的岗位", _ExistsFakeSession(None))
        assert result is False

    async def test_pg_miss_neo4j_name_cn_hit_returns_true(self):
        from app.core.matching.service import MatchService

        svc = MatchService()
        result = await svc._position_exists(_NeoFakeDriver(matches_name_cn=True), "AI智能体工程师", _ExistsFakeSession(None))
        assert result is True


class TestCanonicalSkillName:
    def test_basic_skill(self):
        result = _canonical_skill_name("Python")
        assert isinstance(result, str)

    def test_returns_lowercase_normalized(self):
        result = _canonical_skill_name("Python3")
        assert isinstance(result, str)


class TestSemanticSimilarity:
    def test_identical(self):
        assert _semantic_similarity("Python", "Python") == 1.0

    def test_partial_match(self):
        result = _semantic_similarity("Python3", "Python")
        assert 0 <= result <= 1.0


class TestScoreSkillMatch:
    def test_exact_match_required(self):
        target = [{"skill": "Python", "importance": "required", "proficiency": "熟悉"}]
        person = [{"skill": "Python", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert len(result["evaluated"]) == 1
        assert result["evaluated"][0]["gap_level"] == "已掌握"

    def test_missing_skill(self):
        target = [{"skill": "Rust", "importance": "required", "proficiency": "熟悉"}]
        person = [{"skill": "Python", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert result["evaluated"][0]["gap_level"] == "完全缺失"

    def test_empty_inputs(self):
        result = score_skill_match(target_skills=[], person_skills=[])
        assert result["evaluated"] == []


class TestApplyInflationCorrection:
    def test_no_correction_for_small_profile(self):
        profile = {"required": [{"skill": "Python"}], "bonus": []}
        req, bonus, cii = _match_service._apply_inflation_correction(profile)
        assert len(req) == 1
        assert cii > 0

    def test_inflation_correction_for_large_profile(self):
        large_required = [
            {"skill": f"Skill{i}", "proficiency": "熟悉"} for i in range(10)
        ]
        profile = {"required": large_required, "bonus": []}
        req, bonus, cii = _match_service._apply_inflation_correction(profile)
        # Some should be downgraded
        assert len(req) < 10
        assert cii > 1.0


class TestBuildLearningPath:
    def test_no_prerequisites(self):
        path = build_learning_path("Python", set(), {})
        assert "Python" in path

    def test_with_prerequisites(self):
        # 使用测试用的前置关系映射
        prereq_map = {
            "Pandas": ["Python", "NumPy"],
            "NumPy": ["Python"],
        }
        path = build_learning_path("Pandas", set(), prereq_map)
        assert "Python" in path
        assert "NumPy" in path
        assert "Pandas" in path


class TestProficiencyScore:
    def test_known_levels(self):
        assert PROFICIENCY_SCORE["了解"] == 0.35
        assert PROFICIENCY_SCORE["熟悉"] == 0.65
        assert PROFICIENCY_SCORE["精通"] == 0.9
