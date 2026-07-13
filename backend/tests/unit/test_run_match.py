"""Tests for run_match function in match_service."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.match_service import (
    _match_service,
    compute_competitiveness,
    enrich_learning_paths,
    get_match_result,
    run_batch_match,
    run_match,
    score_skill_match,
)  # noqa: I001


# Clear profile cache before each test to avoid cross-test contamination
@pytest.fixture(autouse=True)
def _clear_profile_cache():
    _match_service._cache.clear()
    yield
    _match_service._cache.clear()


# Sample target profiles used by tests
_DATA_ANALYST_PROFILE = {
    "required": [
        {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "Excel", "category": "tool", "proficiency": "熟悉"},
        {"skill": "统计学", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "Pandas", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "数据可视化", "category": "hard_skill", "proficiency": "熟悉"},
    ],
    "bonus": [
        {"skill": "Tableau", "category": "tool", "proficiency": "了解"},
        {"skill": "Machine Learning", "category": "hard_skill", "proficiency": "了解"},
    ],
}

_FRONTEND_PROFILE = {
    "required": [
        {"skill": "JavaScript", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
    ],
    "bonus": [],
}

_BACKEND_PROFILE = {
    "required": [
        {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "Redis", "category": "hard_skill", "proficiency": "了解"},
    ],
    "bonus": [
        {"skill": "Docker", "category": "tool", "proficiency": "了解"},
    ],
}

_PROFILES = {
    "数据分析师": _DATA_ANALYST_PROFILE,
    "前端开发工程师": _FRONTEND_PROFILE,
    "后端开发工程师": _BACKEND_PROFILE,
}


def _mock_load_target_profile(driver, target_position, db_session=None, repo=None):
    """Return a profile for known positions, or None for unknown.

    _load_target_profile now returns None (not raises) when position is not found.
    The HTTPException(404) is raised by run_match / compute_competitiveness.
    """
    profile = _PROFILES.get(target_position)
    return profile


@pytest.mark.asyncio
async def test_run_match_simple():
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
        result = await run_match(
            target_position="数据分析师",
            person_skills=[
                {"skill": "Python", "proficiency": "熟悉"},
                {"skill": "SQL", "proficiency": "熟悉"},
            ],
        )
    assert "match_id" in result
    assert "match_score" in result
    assert "skill_gap_detail" in result
    assert result["target_position"] == "数据分析师"
    assert result["match_score"] >= 0


@pytest.mark.asyncio
async def test_run_match_no_skills():
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
        result = await run_match(
            target_position="前端开发工程师",
            person_skills=[],
        )
    assert result["match_score"] >= 0
    assert result["missing_required"]


@pytest.mark.asyncio
async def test_run_match_unknown_position():
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
        from app.exceptions import PositionNotFoundError

        with pytest.raises(PositionNotFoundError):
            await run_match(
                target_position="UnknownXYZ Position",
                person_skills=[{"skill": "Python", "proficiency": "熟悉"}],
            )


@pytest.mark.asyncio
async def test_run_match_high_proficiency():
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
        result = await run_match(
            target_position="后端开发工程师",
            person_skills=[
                {"skill": "Python", "proficiency": "精通"},
                {"skill": "FastAPI", "proficiency": "熟悉"},
                {"skill": "Docker", "proficiency": "熟悉"},
            ],
        )
    assert result["match_score"] > 0.3


@pytest.mark.asyncio
async def test_run_match_with_thresholds():
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
        result = await run_match(
            target_position="数据分析师",
            person_skills=[{"skill": "Python", "proficiency": "熟悉"}],
            threshold=0.8,
        )
    assert "match_score" in result


# ---------------------------------------------------------------------------
# Tests for _load_target_profile (covers repo, driver, db_session tiers)
# ---------------------------------------------------------------------------


class TestLoadTargetProfileViaRepo:
    @pytest.mark.asyncio
    async def test_repo_returns_profile(self):
        """When repo has the profile, _load_target_profile returns it."""
        mock_repo = AsyncMock()
        mock_repo.get_position_profile = AsyncMock(return_value=type("P", (), {
            "required_skills": [{"name": "Python", "category": "hard_skill", "proficiency": "熟悉"}],
            "bonus_skills": [{"name": "Docker", "category": "tool", "proficiency": "了解"}],
        })())
        result = await _match_service._load_target_profile(driver=None, target_position="后端开发工程师", repo=mock_repo)
        assert result["required"][0]["skill"] == "Python"
        assert result["bonus"][0]["skill"] == "Docker"

    @pytest.mark.asyncio
    async def test_repo_returns_empty_skills_falls_through(self):
        """When repo returns profile with no required_skills, falls through to next tier and returns None."""
        mock_repo = AsyncMock()
        mock_repo.get_position_profile = AsyncMock(return_value=type("P", (), {
            "required_skills": [],
            "bonus_skills": [],
        })())
        result = await _match_service._load_target_profile(driver=None, target_position="空岗位", repo=mock_repo)
        assert result is None

    @pytest.mark.asyncio
    async def test_repo_exception_falls_through(self):
        """When repo raises an exception, falls through to next tier and returns None."""
        mock_repo = AsyncMock()
        mock_repo.get_position_profile = AsyncMock(side_effect=RuntimeError("connection error"))
        result = await _match_service._load_target_profile(driver=None, target_position="某岗位", repo=mock_repo)
        assert result is None


class TestLoadTargetProfileViaDriver:
    @pytest.mark.asyncio
    async def test_driver_returns_skills(self):
        """When Neo4j driver returns skills, _load_target_profile returns them."""
        with patch("app.core.matching.service.fetch_position_graph", new=AsyncMock(return_value={
            "skills": [
                {"name": "Python", "properties": {"name": "Python", "category": "hard_skill", "proficiency": "熟悉", "importance": "required"}},
                {"name": "Docker", "properties": {"name": "Docker", "category": "tool", "proficiency": "了解", "importance": "bonus"}},
            ],
        })):
            mock_driver = object()
            result = await _match_service._load_target_profile(driver=mock_driver, target_position="后端开发工程师")
            assert result["required"][0]["skill"] == "Python"
            assert result["bonus"][0]["skill"] == "Docker"

    @pytest.mark.asyncio
    async def test_driver_returns_empty_skills_falls_through(self):
        """When Neo4j returns no skills, falls through and returns None."""
        with patch("app.core.matching.service.fetch_position_graph", new=AsyncMock(return_value={"skills": []})):
            mock_driver = object()
            result = await _match_service._load_target_profile(driver=mock_driver, target_position="空岗位")
            assert result is None

    @pytest.mark.asyncio
    async def test_driver_exception_falls_through(self):
        """When Neo4j raises an exception, falls through and returns None."""
        with patch("app.core.matching.service.fetch_position_graph", new=AsyncMock(side_effect=RuntimeError("neo4j error"))):
            mock_driver = object()
            result = await _match_service._load_target_profile(driver=mock_driver, target_position="某岗位")
            assert result is None


class TestLoadTargetProfileViaDB:
    @pytest.mark.asyncio
    async def test_db_session_not_used_as_fallback(self):
        """PostgreSQL fallback has been removed; db_session alone returns None."""
        fake_session = AsyncMock()
        result = await _match_service._load_target_profile(driver=None, target_position="后端开发工程师", db_session=fake_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_sources_returns_none(self):
        """When no data sources are available, returns None (not raises)."""
        result = await _match_service._load_target_profile(driver=None, target_position="不存在岗位", db_session=None)
        assert result is None


class TestLoadTargetProfilePriority:
    @pytest.mark.asyncio
    async def test_repo_takes_priority_over_driver(self):
        """Repo is checked first; if it has data, driver is not queried."""
        mock_repo = AsyncMock()
        mock_repo.get_position_profile = AsyncMock(return_value=type("P", (), {
            "required_skills": [{"name": "Python", "category": "hard_skill", "proficiency": "熟悉"}],
            "bonus_skills": [],
        })())

        with patch("app.core.matching.service.fetch_position_graph", new=AsyncMock(return_value={
            "skills": [{"name": "Java", "properties": {"name": "Java", "category": "hard_skill", "proficiency": "熟悉"}}],
        })):
            mock_driver = object()
            result = await _match_service._load_target_profile(driver=mock_driver, target_position="后端", repo=mock_repo)
            assert result["required"][0]["skill"] == "Python"


# ---------------------------------------------------------------------------
# Tests for compute_competitiveness, run_batch_match, enrich_learning_paths
# ---------------------------------------------------------------------------


class TestComputeCompetitiveness:
    @pytest.mark.asyncio
    async def test_basic_competitiveness(self):
        """compute_competitiveness returns valid structure."""
        with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
            result = await compute_competitiveness(target_position="数据分析师")
        assert "competitiveness_score" in result
        assert "difficulty" in result
        assert "description" in result
        assert "skill_count" in result
        assert "bottleneck_skills" in result
        assert 0.0 <= result["competitiveness_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_competitiveness_with_profile(self):
        """compute_competitiveness with a known profile returns reasonable values."""
        with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
            result = await compute_competitiveness(target_position="后端开发工程师")
        assert result["position"] == "后端开发工程师"
        assert result["required_count"] > 0
        assert result["skill_details"]  # should have skill details


class TestRunBatchMatch:
    @pytest.mark.asyncio
    async def test_batch_match_basic(self):
        """run_batch_match with multiple resumes and positions."""
        with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
            result = await run_batch_match(
                resumes=[
                    {"resume_id": "r1", "person_skills": [{"name": "Python", "proficiency": "精通"}]},
                    {"resume_id": "r2", "person_skills": [{"name": "SQL", "proficiency": "熟悉"}]},
                ],
                positions=["数据分析师", "前端开发工程师"],
            )
        assert "results" in result
        assert "matrix" in result
        assert "summary" in result
        assert len(result["results"]) == 4  # 2 resumes x 2 positions
        assert len(result["matrix"]) == 2  # 2 resume rows
        assert result["summary"]["total_pairs"] == 4

    @pytest.mark.asyncio
    async def test_batch_match_with_unknown_position(self):
        """run_batch_match handles unknown positions gracefully (score=0)."""
        with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
            result = await run_batch_match(
                resumes=[{"resume_id": "r1", "person_skills": [{"name": "Python", "proficiency": "精通"}]}],
                positions=["UnknownPosition"],
            )
        # Unknown position causes PositionNotFoundError, which is caught and scored as 0
        assert len(result["results"]) == 0  # failed matches are not added to results
        assert result["matrix"][0][0] == 0.0  # unknown position → score 0


class TestEnrichLearningPaths:
    @pytest.mark.asyncio
    async def test_no_driver_returns_unchanged(self):
        """enrich_learning_paths with no driver returns gaps unchanged."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        result = await enrich_learning_paths(gaps, driver=None)
        assert result == gaps

    @pytest.mark.asyncio
    async def test_empty_gaps_returns_empty(self):
        """enrich_learning_paths with empty gaps returns empty list."""
        result = await enrich_learning_paths([], driver=object())
        assert result == []


# ---------------------------------------------------------------------------
# Tests for save_match_result and get_match_result (DB persistence)
# ---------------------------------------------------------------------------


class TestSaveMatchResult:
    @pytest.mark.asyncio
    async def test_save_with_mock_session(self):
        """save_match_result executes SQL without error on mock session."""
        from unittest.mock import Mock

        fake_session = AsyncMock()
        fake_session.execute = AsyncMock(return_value=Mock())
        fake_session.commit = AsyncMock()

        result = {
            "target_position": "数据分析师",
            "match_score": 0.85,
            "matched_skills": ["Python"],
            "missing_required": [],
            "missing_bonus": [],
            "skill_gap_detail": [],
            "cii": 1.0,
        }
        await _match_service._save_match_result(fake_session, "test-match-id", result)
        fake_session.execute.assert_awaited()
        fake_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_save_handles_exception_gracefully(self):
        """save_match_result does not raise on DB error."""
        fake_session = AsyncMock()
        fake_session.execute = AsyncMock(side_effect=RuntimeError("db error"))

        result = {
            "target_position": "数据分析师",
            "match_score": 0.5,
            "matched_skills": [],
            "missing_required": ["Python"],
            "missing_bonus": [],
            "skill_gap_detail": [],
        }
        # Should not raise
        await _match_service._save_match_result(fake_session, "test-match-id", result)


class TestGetMatchResult:
    @pytest.mark.asyncio
    async def test_in_memory_cache_hit(self):
        """get_match_result returns from in-memory cache."""
        # Directly populate the in-memory cache
        test_result = {"match_id": "cached-test-id", "target_position": "测试", "match_score": 0.9}
        _match_service._cache._match_results["cached-test-id"] = test_result
        try:
            result = await get_match_result("cached-test-id")
            assert result is not None
            assert result["match_id"] == "cached-test-id"
        finally:
            _match_service._cache._match_results.pop("cached-test-id", None)

    @pytest.mark.asyncio
    async def test_miss_returns_none(self):
        """get_match_result returns None for unknown match_id."""
        result = await get_match_result("nonexistent-id-12345")
        assert result is None


# ---------------------------------------------------------------------------
# Tests for enrich_learning_paths with driver
# ---------------------------------------------------------------------------
class TestEnrichLearningPathsWithDriver:
    @pytest.mark.asyncio
    async def test_with_mock_driver_session(self):
        """enrich_learning_paths queries Neo4j for learning resources."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver = AsyncMock()
        mock_driver.session = Mock(return_value=mock_session)

        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        result = await enrich_learning_paths(gaps, driver=mock_driver)
        assert len(result) == 1
        assert result[0]["skill"] == "Python"
        assert result[0]["learning_resources"] == []

    @pytest.mark.asyncio
    async def test_with_resources_attached(self):
        """enrich_learning_paths attaches learning resources from Neo4j."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[
            {"skill_name": "Python", "resource_name": "Python Tutorial", "url": "https://example.com", "type": "course"},
        ])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver = AsyncMock()
        mock_driver.session = Mock(return_value=mock_session)

        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        result = await enrich_learning_paths(gaps, driver=mock_driver)
        assert result[0]["learning_resources"][0]["name"] == "Python Tutorial"

    @pytest.mark.asyncio
    async def test_driver_exception_returns_gaps_unchanged(self):
        """enrich_learning_paths returns unchanged gaps on driver exception."""
        mock_driver = AsyncMock()
        mock_driver.session = Mock(side_effect=RuntimeError("neo4j down"))

        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        result = await enrich_learning_paths(gaps, driver=mock_driver)
        assert result == gaps


# ---------------------------------------------------------------------------
# Tests for _assessment_text
# ---------------------------------------------------------------------------
class TestAssessmentText:
    def test_high_score_no_missing(self):
        assert "强匹配" in _match_service._assessment_text(0.85, 0)

    def test_medium_score(self):
        assert "关键缺口" in _match_service._assessment_text(0.65, 2)

    def test_low_score(self):
        assert "明显差距" in _match_service._assessment_text(0.3, 5)


# ---------------------------------------------------------------------------
# Tests for _estimate_learning_time
# ---------------------------------------------------------------------------
class TestEstimateLearningTime:
    def test_short_time(self):
        gaps = [{"importance": "required", "gap_level": "完全缺失"}]
        result = _match_service._estimate_learning_time(gaps)
        assert "周" in result

    def test_long_time(self):
        # 5 required gaps at 完全缺失 = 15 weeks → months
        gaps = [{"importance": "required", "gap_level": "完全缺失"} for _ in range(5)]
        result = _match_service._estimate_learning_time(gaps)
        assert "个月" in result

    def test_partial_mastery(self):
        gaps = [{"importance": "required", "gap_level": "部分掌握"}]
        result = _match_service._estimate_learning_time(gaps)
        assert "周" in result

    def test_already_mastered(self):
        gaps = [{"importance": "required", "gap_level": "已掌握"}]
        result = _match_service._estimate_learning_time(gaps)
        assert "周" in result

    def test_bonus_gap(self):
        gaps = [{"importance": "bonus", "gap_level": "完全缺失"}]
        result = _match_service._estimate_learning_time(gaps)
        assert "周" in result


# ---------------------------------------------------------------------------
# Tests for _apply_inflation_correction
# ---------------------------------------------------------------------------
class TestApplyInflationCorrection:
    def test_no_inflation(self):
        """Small required list stays unchanged."""
        profile = {
            "required": [{"skill": "Python", "proficiency": "熟悉"}],
            "bonus": [{"skill": "Docker", "proficiency": "了解"}],
        }
        req, bon, cii = _match_service._apply_inflation_correction(profile)
        assert len(req) == 1
        assert cii <= 1.2

    def test_inflation_downgrades(self):
        """Large required list triggers inflation correction."""
        required = [{"skill": f"Skill{i}", "proficiency": "了解"} for i in range(10)]
        bonus = [{"skill": "Bonus1", "proficiency": "了解"}]
        profile = {"required": required, "bonus": bonus}
        req, bon, cii = _match_service._apply_inflation_correction(profile)
        assert len(req) < 10  # some downgraded to bonus
        assert cii > 1.2

    def test_empty_required(self):
        """Empty required list returns cii=1.0."""
        profile = {"required": [], "bonus": []}
        req, bon, cii = _match_service._apply_inflation_correction(profile)
        assert cii == 1.0


# ---------------------------------------------------------------------------
# Tests for _build_learning_path
# ---------------------------------------------------------------------------
class TestBuildLearningPath:
    def test_no_prerequisites(self):
        from app.core.matching.path_builder import build_learning_path
        result = build_learning_path("Python", set(), {})
        assert "Python" in result

    def test_with_prerequisites(self):
        from app.core.matching.path_builder import build_learning_path
        prereq_map = {"Pandas": ["Python", "NumPy"], "NumPy": ["Python"]}
        result = build_learning_path("Pandas", set(), prereq_map)
        assert "Python" in result
        assert "NumPy" in result
        assert "Pandas" in result
        # Python should come before NumPy and Pandas
        assert result.index("Python") < result.index("Pandas")

    def test_owned_skills_excluded(self):
        from app.core.matching.path_builder import build_learning_path
        prereq_map = {"Pandas": ["Python"]}
        result = build_learning_path("Pandas", {"Python"}, prereq_map)
        assert "Python" not in result
        assert "Pandas" in result


# ---------------------------------------------------------------------------
# Tests for _canonical_skill_name
# ---------------------------------------------------------------------------
class TestCanonicalSkillName:
    def test_normal_name(self):
        from app.core.matching.scorer import _canonical_skill_name
        result = _canonical_skill_name("Python")
        assert result == "Python"

    def test_whitespace_stripped(self):
        from app.core.matching.scorer import _canonical_skill_name
        result = _canonical_skill_name("  Python  ")
        assert result.strip() == "Python"


# ---------------------------------------------------------------------------
# Tests for _load_prerequisite_map
# ---------------------------------------------------------------------------
class TestLoadPrerequisiteMap:
    @pytest.mark.asyncio
    async def test_no_driver_returns_early(self):
        # Should not raise with no driver
        await _match_service._load_prerequisite_map(None)

    @pytest.mark.asyncio
    async def test_with_mock_driver(self):
        # Build a proper async iterator for the Neo4j result
        records = [{"src": "Pandas", "tgt": "Python"}]

        class AsyncIter:
            def __init__(self, items):
                self._items = iter(items)
            def __aiter__(self):
                return self
            async def __anext__(self):
                try:
                    return next(self._items)
                except StopIteration:
                    raise StopAsyncIteration from None

        mock_result = AsyncMock()
        mock_result.__aiter__ = Mock(return_value=AsyncIter(records))
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver = AsyncMock()
        mock_driver.session = Mock(return_value=mock_session)

        # Reset cache
        _match_service._cache.clear()
        try:
            result = await _match_service._load_prerequisite_map(mock_driver)
            # Should have loaded prerequisite
            assert "Pandas" in result
        finally:
            _match_service._cache.clear()

    @pytest.mark.asyncio
    async def test_driver_exception_handled(self):
        mock_driver = AsyncMock()
        mock_driver.session = Mock(side_effect=RuntimeError("neo4j down"))

        _match_service._cache.clear()
        try:
            # Should not raise
            await _match_service._load_prerequisite_map(mock_driver)
        finally:
            _match_service._cache.clear()


# ---------------------------------------------------------------------------
# Tests for score_skill_match edge cases
# ---------------------------------------------------------------------------
class TestScoreSkillMatch:
    def test_empty_name_skipped(self):
        """Items with empty name/skill are skipped."""
        target_skills = [{"skill": "Python", "importance": "required", "proficiency": "熟悉"}]
        person_skills = [{"name": "", "proficiency": "精通"}]
        result = score_skill_match(target_skills=target_skills, person_skills=person_skills)
        assert len(result["evaluated"]) == 1
        # Empty name means person has no recognized skills -> gap
        assert result["evaluated"][0]["gap_level"] == "完全缺失"

    def test_exact_match_lower_proficiency_is_mastered(self):
        """B16 回归：精确命中某技能即使熟练度低于岗位要求，也应判为"已掌握"。

        旧逻辑：final_score 受熟练度惩罚降到 ~0.838 < 0.85 → 错判"部分掌握"，
        导致 matched_skills 虚低、missing_required 虚高。
        修复后：exact == 1.0 直接判为"已掌握"。
        """
        target_skills = [{"skill": "Python", "importance": "required", "proficiency": "精通"}]
        person_skills = [{"name": "Python", "proficiency": "了解"}]
        result = score_skill_match(target_skills=target_skills, person_skills=person_skills)
        assert result["evaluated"][0]["gap_level"] == "已掌握"

    def test_partial_mastery_via_fuzzy_match(self):
        """模糊匹配（非精确命中）落入部分掌握区间时判为"部分掌握"。

        用一个相似但非别名的技能名，使 exact=0、fuzzy 命中，
        验证非精确匹配仍按 final_score 分级。
        """
        # "Javascript" 与 "JavaScript" 经规范化后小写一致 → exact=1。
        # 改用真正仅模糊相似的名称以触发 partial 路径。
        target_skills = [{"skill": "Python", "importance": "required", "proficiency": "熟悉"}]
        person_skills = [{"name": "Python3", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target_skills, person_skills=person_skills)
        gap = result["evaluated"][0]["gap_level"]
        # 模糊匹配（非 exact）应落入 已掌握/部分掌握 之一，不应是完全缺失
        assert gap in {"已掌握", "部分掌握"}

    def test_fuzzy_match(self):
        """Similar skill names produce a fuzzy match."""
        target_skills = [{"skill": "JavaScript", "importance": "required", "proficiency": "熟悉"}]
        person_skills = [{"name": "Javascript", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target_skills, person_skills=person_skills)
        assert result["evaluated"][0]["score"] > 0


# ---------------------------------------------------------------------------
# Tests for get_match_result DB fallback
# ---------------------------------------------------------------------------
class TestGetMatchResultDBFallback:
    @pytest.mark.asyncio
    async def test_db_fallback_with_mock_session(self):
        """get_match_result reads from PostgreSQL when memory cache misses."""
        _match_service._cache._match_results.pop("db-test-id", None)

        # Mock a MatchResult ORM object with the right attributes
        mock_row = type("MatchResult", (), {
            "match_id": "db-test-id",
            "target_position": "数据分析师",
            "match_score": 0.75,
            "matched_skills": ["Python"],
            "missing_required": ["SQL"],
            "missing_bonus": [],
            "gap_report": [{"skill": "SQL", "gap_level": "完全缺失", "learning_path": ["SQL"]}],
            "learning_path": [["SQL"]],
            "cii": 1.0,
        })()

        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none = Mock(return_value=mock_row)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        try:
            result = await get_match_result("db-test-id", db_session=mock_session)
            assert result is not None
            assert result["match_id"] == "db-test-id"
            assert result["target_position"] == "数据分析师"
            assert "db-test-id" in _match_service._cache._match_results
        finally:
            _match_service._cache._match_results.pop("db-test-id", None)

    @pytest.mark.asyncio
    async def test_db_fallback_no_result(self):
        """get_match_result returns None when DB has no result."""
        _match_service._cache._match_results.pop("db-miss-id", None)

        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none = Mock(return_value=None)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        result = await get_match_result("db-miss-id", db_session=mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_db_fallback_exception_returns_none(self):
        """get_match_result returns None on DB exception."""
        _match_service._cache._match_results.pop("db-err-id", None)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB down"))

        result = await get_match_result("db-err-id", db_session=mock_session)
        assert result is None


# ---------------------------------------------------------------------------
# Tests for compute_competitiveness high difficulty
# ---------------------------------------------------------------------------
class TestComputeCompetitivenessHigh:
    @pytest.mark.asyncio
    async def test_high_difficulty(self):
        """Position with many required skills gets high difficulty."""
        from app.services.match_service import compute_competitiveness

        many_required_profile = {
            "required": [
                {"skill": f"Skill{i}", "category": "hard_skill", "proficiency": "精通"}
                for i in range(12)
            ],
            "bonus": [],
        }
        with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(return_value=many_required_profile)):
            with patch("app.core.matching.service.MatchService._load_prerequisite_map", new=AsyncMock()):
                result = await compute_competitiveness(target_position="高级工程师")
        assert result["difficulty"] == "高"
        assert result["competitiveness_score"] >= 0.75


# Tests for _get_pg_session and get_match_result LRU eviction were removed
# (C1, C2). _get_pg_session no longer exists post-MatchService refactor;
# cache eviction is now handled by MatchCache._max_size and tested in
# tests/unit/test_matching_cache.py.
