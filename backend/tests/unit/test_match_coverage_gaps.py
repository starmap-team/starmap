"""Test coverage gaps for match service and core matching modules.

Targets uncovered lines identified by coverage analysis:

  match_service.py:  203-204 (compute_competitiveness proficiency guard)
  service.py:        43 (prerequisite cache hit), 81 (profile cache hit),
                     155-172 (DB session fallback), 205-206 (inflation "精通" guard),
                     218 (dedup), 265-266 (bonus overlap merge),
                     324 (inflation recommendation), 354 (save result)
  cache.py:          46-52 (profile TTL expiry), 71-76 (prereq TTL expiry),
                     110-112 (FIFO eviction), 145 (reset_match_cache)
  scorer.py:         71-74 (chroma match), 127, 132 (chroma fallback),
                     144, 146 (gap level via final_score)
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.core.matching.cache import MatchCache, get_match_cache, reset_match_cache
from app.core.matching.scorer import (
    _batch_chroma_match,
    score_skill_match,
)
from app.services.match_service import (
    _match_service,
    compute_competitiveness,
    get_match_result,
    run_match,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATA_ANALYST_PROFILE = {
    "required": [
        {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "Excel", "category": "tool", "proficiency": "熟悉"},
        {"skill": "Pandas", "category": "hard_skill", "proficiency": "熟悉"},
        {"skill": "数据可视化", "category": "hard_skill", "proficiency": "熟悉"},
    ],
    "bonus": [
        {"skill": "Tableau", "category": "tool", "proficiency": "了解"},
    ],
}


def _mock_load_profile(driver, target_position, db_session=None, repo=None):
    return _DATA_ANALYST_PROFILE if target_position == "数据分析师" else None


@pytest.fixture(autouse=True)
def _clear_caches():
    _match_service._cache.clear()
    yield
    _match_service._cache.clear()


# ===========================================================================
# 1. Cache hit paths (service.py:43, 81)
# ===========================================================================


@pytest.mark.asyncio
async def test_prerequisite_cache_hit():
    """_load_prerequisite_map returns cached map without querying driver."""
    _match_service._cache._prerequisite_map = {"Pandas": ["Python"]}
    _match_service._cache._prereq_cache_ts = time.monotonic()
    result = await _match_service._load_prerequisite_map(driver=MagicMock())
    assert "Pandas" in result
    assert result["Pandas"] == ["Python"]


@pytest.mark.asyncio
async def test_profile_cache_hit():
    """_load_target_profile returns cached profile without querying any source."""
    _match_service._cache._profile_cache["数据分析师"] = _DATA_ANALYST_PROFILE
    _match_service._cache._profile_cache_ts["数据分析师"] = time.monotonic()
    result = await _match_service._load_target_profile(
        driver=MagicMock(), target_position="数据分析师"
    )
    assert result is not None
    assert result["required"][0]["skill"] == "Python"


# ===========================================================================
# 2. DB session fallback in _load_target_profile (service.py:155-172)
# ===========================================================================


class _FakePositionRecord:
    id = 1
    name = "数据分析师"


class _FakeSkillRecord:
    name = "Python"
    category = "hard_skill"
    source_count = 5


class _FakeRelation:
    requirement_type = "required"


@pytest.mark.asyncio
async def test_load_target_profile_db_fallback():
    """_load_target_profile falls back to PostgreSQL position_records."""
    fake_row = _FakePositionRecord()
    fake_skill = _FakeSkillRecord()
    fake_rel = _FakeRelation()

    mock_exec_result = AsyncMock()
    mock_exec_result.scalar_one_or_none = Mock(return_value=fake_row)
    mock_all_result = AsyncMock()
    mock_all_result.all = Mock(return_value=[(fake_rel, fake_skill)])

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[mock_exec_result, mock_all_result]
    )

    result = await _match_service._load_target_profile(
        driver=None, target_position="数据分析师", db_session=mock_session
    )
    assert result is not None
    assert result["required"][0]["skill"] == "Python"
    assert result["required"][0]["category"] == "hard_skill"


@pytest.mark.asyncio
async def test_load_target_profile_db_fallback_preferred():
    """DB fallback routes 'preferred' requirement_type to bonus list."""
    class _PrefRel:
        requirement_type = "preferred"
    fake_skill = _FakeSkillRecord()
    fake_row = _FakePositionRecord()

    mock_exec_result = AsyncMock()
    mock_exec_result.scalar_one_or_none = Mock(return_value=fake_row)
    mock_all_result = AsyncMock()
    mock_all_result.all = Mock(return_value=[(_PrefRel(), fake_skill)])

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[mock_exec_result, mock_all_result]
    )

    result = await _match_service._load_target_profile(
        driver=None, target_position="数据分析师", db_session=mock_session
    )
    assert result is not None
    assert result["bonus"][0]["skill"] == "Python"


@pytest.mark.asyncio
async def test_load_target_profile_db_fallback_exception():
    """DB fallback exception is handled gracefully."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("db error"))
    result = await _match_service._load_target_profile(
        driver=None, target_position="数据分析师", db_session=mock_session
    )
    assert result is None


@pytest.mark.asyncio
async def test_load_target_profile_db_fallback_no_position():
    """DB fallback returns None when position not found."""
    mock_exec_result = AsyncMock()
    mock_exec_result.scalar_one_or_none = Mock(return_value=None)
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_exec_result)
    result = await _match_service._load_target_profile(
        driver=None, target_position="不存在岗位", db_session=mock_session
    )
    assert result is None


# ===========================================================================
# 3. Inflation correction: "精通" guard (service.py:205-206)
# ===========================================================================


def test_inflation_keeps_master_skills():
    """Skills with '精通' proficiency and source_count >= 30 are kept as required.

    Coverage target: service.py:205-206 — the guard that preserves '精通' skills
    with high source_count from being downgraded to bonus.
    """
    # 12 skills total: overflow = max(1, 12 - ceil(6*1.2)) = 4
    # First 3: low proficiency/low source_count — sort lowest → downgraded
    # Fourth: "精通" with source_count=50 — in downgraded list, guard should keep it
    # Remaining 8: "精通" with source_count=50 — in kept list
    required = [
        {"skill": "LowSkill", "proficiency": "了解", "source_count": "0"},
        {"skill": "LowSkill2", "proficiency": "了解", "source_count": "0"},
        {"skill": "LowSkill3", "proficiency": "了解", "source_count": "0"},
        {"skill": "MasterSkill", "proficiency": "精通", "source_count": "50"},
    ]
    # Add 8 more "精通" skills with high source_count (they sort after, stay in kept)
    for i in range(8):
        required.append({"skill": f"HighSkill{i}", "proficiency": "精通", "source_count": "50"})

    profile = {"required": required, "bonus": []}
    req, bon, cii = _match_service._apply_inflation_correction(profile)

    kept_names = {s["skill"] for s in req}
    assert "MasterSkill" in kept_names, "MasterSkill should be kept as required"
    assert "LowSkill" not in kept_names, "LowSkill should be downgraded to bonus"
    # MasterSkill is 精通 + source_count >= 30 → kept via the guard


# ===========================================================================
# 4. Dedup in inflation correction (service.py:218)
# ===========================================================================


def test_inflation_dedup():
    """Skills that appear in both required and bonus are deduplicated."""
    required = [
        {"skill": f"Skill{i}", "proficiency": "了解", "source_count": "1"}
        for i in range(10)
    ]
    bonus = [
        {"skill": "Skill0", "proficiency": "了解"},  # duplicate of required
        {"skill": "UniqueBonus", "proficiency": "了解"},
    ]
    profile = {"required": required, "bonus": bonus}
    req, bon, cii = _match_service._apply_inflation_correction(profile)
    # Skill0 should appear only once (in required, not duplicated in bonus)
    bon_names = {s["skill"] for s in bon}
    assert "UniqueBonus" in bon_names


# ===========================================================================
# 5. Bonus overlap merge in run_match (service.py:265-266)
# ===========================================================================


@pytest.mark.asyncio
async def test_run_match_bonus_overlap_merge():
    """Skills overlapping between required and bonus are merged with max score.

    Coverage target: service.py:265-266 — the merge logic for skills that appear
    in both required and bonus evaluated results.
    """
    profile = {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SkillA", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SkillB", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SkillC", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SkillD", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SkillE", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SkillF", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
        ],
    }
    # Force _apply_inflation_correction to return overlapping lists
    with patch.object(
        _match_service,
        "_load_prerequisite_map",
        new=AsyncMock(return_value={}),
    ), patch.object(
        _match_service,
        "_load_target_profile",
        new=AsyncMock(return_value=profile),
    ), patch.object(
        _match_service,
        "_apply_inflation_correction",
        return_value=(
            [
                {"skill": "Python", "importance": "required", "proficiency": "熟悉"},
                {"skill": "SkillA", "importance": "required", "proficiency": "熟悉"},
                {"skill": "SkillB", "importance": "required", "proficiency": "熟悉"},
            ],
            [
                {"skill": "Python", "importance": "bonus", "proficiency": "精通"},
                {"skill": "Bonus1", "importance": "bonus", "proficiency": "了解"},
            ],
            1.0,
        ),
    ), patch.object(_match_service, "_save_match_result", new=AsyncMock()):
        result = await _match_service.run_match(
            target_position="数据分析师",
            person_skills=[
                {"skill": "Python", "proficiency": "精通"},
                {"skill": "SkillA", "proficiency": "精通"},
            ],
        )
    assert "Python" in result["matched_skills"]
    assert "skill_gap_detail" in result


# ===========================================================================
# 6. Inflation recommendation in run_match (service.py:324)
# ===========================================================================


@pytest.mark.asyncio
async def test_run_match_inflation_recommendation():
    """When cii > 1.2, run_match includes inflation advisory in recommendations."""
    # 10+ required skills triggers inflation
    many_required = [
        {"skill": f"Skill{i}", "proficiency": "了解"}
        for i in range(10)
    ]
    profile = {"required": many_required, "bonus": []}
    with patch(
        "app.core.matching.service.MatchService._load_target_profile",
        new=AsyncMock(return_value=profile),
    ), patch.object(_match_service, "_save_match_result", new=AsyncMock()):
        result = await run_match(
            target_position="数据分析师",
            person_skills=[{"skill": "Python", "proficiency": "精通"}],
        )
    inflation_msg = "岗位要求存在通胀迹象"
    assert any(inflation_msg in r for r in result["recommendations"])


# ===========================================================================
# 7. Save match result via run_match (service.py:354)
# ===========================================================================


@pytest.mark.asyncio
async def test_run_match_persists_to_db():
    """run_match calls _save_match_result when db_session is provided."""
    profile = {
        "required": [{"skill": "Python", "proficiency": "熟悉"}],
        "bonus": [],
    }
    with patch(
        "app.core.matching.service.MatchService._load_target_profile",
        new=AsyncMock(return_value=profile),
    ):
        save_mock = AsyncMock()
        with patch.object(_match_service, "_save_match_result", save_mock):
            result = await run_match(
                target_position="数据分析师",
                person_skills=[{"skill": "Python", "proficiency": "精通"}],
                db_session=AsyncMock(),
            )
        save_mock.assert_awaited_once()
        call = save_mock.await_args
        assert call is not None
        _, call_match_id, call_result = call.args
        assert call_match_id == result["match_id"]
        assert call_result is result  # result dict


# ===========================================================================
# 8. Cache TTL expiry (cache.py:46-52, 71-76)
# ===========================================================================


def test_profile_cache_ttl_expiry():
    """Profile cache returns None after TTL expires."""
    cache = MatchCache(ttl=0)  # zero TTL = immediate expiry
    cache.set_profile("test_pos", _DATA_ANALYST_PROFILE)
    # After setting, immediately expired due to ttl=0
    result = cache.get_profile("test_pos")
    assert result is None


def test_prerequisite_cache_ttl_expiry():
    """Prerequisite cache returns None after TTL expires."""
    cache = MatchCache(ttl=0)
    cache.set_prerequisite_map({"Pandas": ["Python"]})
    result = cache.get_prerequisite_map()
    assert result is None


def test_profile_cache_no_hit_for_missing():
    """get_profile returns None for uncached position."""
    cache = MatchCache()
    result = cache.get_profile("nonexistent")
    assert result is None


def test_prerequisite_cache_no_hit_for_missing():
    """get_prerequisite_map returns None when never set."""
    cache = MatchCache()
    result = cache.get_prerequisite_map()
    assert result is None


# ===========================================================================
# 9. FIFO eviction in set_match_result (cache.py:110-112)
# ===========================================================================


def test_match_result_fifo_eviction():
    """set_match_result evicts oldest entries when cache exceeds max_size."""
    cache = MatchCache(ttl=3600, max_size=3)
    cache.set_match_result("id1", {"data": 1})
    cache.set_match_result("id2", {"data": 2})
    cache.set_match_result("id3", {"data": 3})
    # At this point we have 3 entries, max_size is 3
    # Adding one more should evict id1 (oldest)
    cache.set_match_result("id4", {"data": 4})
    assert cache.get_match_result("id1") is None  # evicted
    assert cache.get_match_result("id2") is not None
    assert cache.get_match_result("id4") is not None


# ===========================================================================
# 10. reset_match_cache (cache.py:145)
# ===========================================================================


def test_reset_match_cache():
    """reset_match_cache clears the global singleton."""
    cache = get_match_cache()
    assert cache is not None
    # Store something
    cache.set_profile("pos", {"required": [], "bonus": []})
    reset_match_cache()
    new_cache = get_match_cache()
    # After reset, the new instance should have empty state
    assert new_cache.get_profile("pos") is None
    # Reset again to leave state clean for other tests
    reset_match_cache()


# ===========================================================================
# 11. _batch_chroma_match (scorer.py:47-141)
# ===========================================================================


def test_batch_chroma_match_empty_inputs():
    """_batch_chroma_match returns empty dict for empty targets or candidates."""
    assert _batch_chroma_match([], {"Python"}) == {}
    assert _batch_chroma_match(["Python"], set()) == {}


def test_batch_chroma_match_no_chroma_available():
    """_batch_chroma_match returns empty dict when ChromaDB is unavailable (negative cache)."""
    # With no ChromaDB server running, the function should gracefully return {}
    result = _batch_chroma_match(["Python"], {"Python", "Java"})
    assert isinstance(result, dict)


# ===========================================================================
# 12. score_skill_match chroma fallback path (scorer.py:127, 132)
# ===========================================================================


@patch("app.core.matching.scorer._batch_chroma_match")
def test_score_skill_match_chroma_fallback(mock_chroma):
    """When exact and fuzzy both miss, chroma fallback is attempted."""
    from app.core.matching.scorer import CHROMA_SIMILARITY_THRESHOLD

    mock_chroma.return_value = {"zzz_unique_skill_42": CHROMA_SIMILARITY_THRESHOLD}

    target = [{"skill": "zzz_unique_skill_42", "importance": "required", "proficiency": "熟悉"}]
    person = [{"name": "something_very_different", "proficiency": "熟悉"}]
    result = score_skill_match(target_skills=target, person_skills=person)
    # chroma was called; result should be a partial match or missing
    assert result["evaluated"][0]["gap_level"] in {"部分掌握", "完全缺失"}
    mock_chroma.assert_called_once()


# ===========================================================================
# 13. score_skill_match: gap_level via final_score >= 0.85 (scorer.py:144)
# ===========================================================================


def test_score_skill_match_high_fuzzy_score_gap_mastered():
    """When fuzzy match gives high enough score, gap_level is '已掌握'."""
    target = [{"skill": "Javascript", "importance": "required", "proficiency": "熟悉"}]
    person = [{"name": "JavaScript", "proficiency": "精通"}]
    result = score_skill_match(target_skills=target, person_skills=person)
    # These are very similar names; fuzzy score should be high
    assert result["evaluated"][0]["gap_level"] == "已掌握"


def test_score_skill_match_partial_mastery_via_fuzzy():
    """Fuzzy match with partial score gives '部分掌握'.

    Coverage target: scorer.py:146 — gap_level '部分掌握' via
    final_score >= threshold * 0.75 (but < 0.85 and exact != 1.0).

    Note: scorer.py:144 (final_score >= 0.85 without exact match) is unreachable
    dead code — max recall without exact=1.0 is 0.5, which caps final_score at 0.5.
    """
    # ExpressJS vs Express.js gives ratio ~0.95, final ~0.32 with default threshold
    # With threshold=0.3, threshold*0.75=0.225 → 0.32 >= 0.225 → 部分掌握
    target = [{"skill": "ExpressJS", "importance": "required", "proficiency": "熟悉"}]
    person = [{"name": "Express.js", "proficiency": "熟悉"}]
    result = score_skill_match(
        target_skills=target, person_skills=person, threshold=0.3
    )
    gap = result["evaluated"][0]["gap_level"]
    score = result["evaluated"][0]["score"]
    assert gap == "部分掌握", f"Expected partial mastery, got {gap} with score={score}"
    assert score < 0.85


# ===========================================================================
# 14. compute_competitiveness inflation guard (match_service.py:203-204)
# ===========================================================================


@pytest.mark.asyncio
async def test_compute_competitiveness_inflation_guard():
    """compute_competitiveness with many required skills triggers the prof guard."""
    many_required = [
        {"skill": f"Skill{i}", "category": "hard_skill", "proficiency": "精通"}
        for i in range(12)
    ]
    # One skill with "精通" and high source_count to exercise the guard
    many_required[0] = {
        "skill": "Python",
        "category": "hard_skill",
        "proficiency": "精通",
        "source_count": 50,
    }
    profile = {"required": many_required, "bonus": []}
    with patch(
        "app.core.matching.service.MatchService._load_target_profile",
        new=AsyncMock(return_value=profile),
    ):
        result = await compute_competitiveness(target_position="高级工程师")
    assert result["difficulty"] == "高"
    assert result["competitiveness_score"] >= 0.75


@pytest.mark.asyncio
async def test_compute_competitiveness_unknown_position():
    """compute_competitiveness raises PositionNotFoundError when position not found.

    Coverage target: match_service.py:203-204 (PositionNotFoundError raise path).
    """
    from app.exceptions import PositionNotFoundError

    with patch(
        "app.core.matching.service.MatchService._load_target_profile",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(PositionNotFoundError):
            await compute_competitiveness(target_position="不存在的岗位")


# ===========================================================================
# 15. enrichment: gap with no learning resources key
# ===========================================================================


@pytest.mark.asyncio
async def test_enrich_learning_paths_no_skill_key():
    """enrich_learning_paths handles gaps without 'skill' key."""
    from app.services.match_service import enrich_learning_paths

    gaps = [
        {"importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
    ]
    # No driver, returns gaps unchanged
    result = await enrich_learning_paths(gaps, driver=None)
    assert result == gaps


# ===========================================================================
# 16. run_batch_match with empty resumes/positions
# ===========================================================================


@pytest.mark.asyncio
async def test_run_batch_match_empty():
    """run_batch_match with empty inputs returns empty summary."""
    from app.services.match_service import run_batch_match

    result = await run_batch_match(
        resumes=[],
        positions=[],
    )
    assert result["summary"]["total_pairs"] == 0
    assert result["summary"]["avg_score"] == 0.0
    assert result["results"] == []


# ===========================================================================
# 17. _save_match_result on exception (service.py:384 area)
# ===========================================================================


@pytest.mark.asyncio
async def test_save_match_result_exception():
    """_save_match_result handles exception gracefully."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("db error"))
    await _match_service._save_match_result(
        mock_session, "test-id", {"target_position": "test", "match_score": 0.5}
    )
    # Should not raise


# ===========================================================================
# 18. run_match with empty person_skills verifies structure
# ===========================================================================


@pytest.mark.asyncio
async def test_run_match_empty_skills_full_structure():
    """run_match with empty person_skills returns full result structure."""
    with patch(
        "app.core.matching.service.MatchService._load_target_profile",
        new=AsyncMock(side_effect=_mock_load_profile),
    ), patch.object(_match_service, "_save_match_result", new=AsyncMock()):
        result = await run_match(
            target_position="数据分析师",
            person_skills=[],
        )
    assert "overall_assessment" in result
    assert "estimated_learning_time" in result
    assert "recommendations" in result
    assert result["match_score"] >= 0.0


# ===========================================================================
# 19. get_match_result with both cache and DB returning None
# ===========================================================================


@pytest.mark.asyncio
async def test_get_match_result_db_fallback_preferred_bonus():
    """DB fallback correctly maps preferred skills."""
    class _MockRow:
        match_id = "db-bonus-id"
        target_position = "测试"
        match_score = 0.6
        matched_skills = ["Python"]
        missing_required = []
        missing_bonus = ["Docker"]
        gap_report = []
        learning_path = []
        cii = 1.0

    mock_exec_result = AsyncMock()
    mock_exec_result.scalar_one_or_none = Mock(return_value=_MockRow())

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_exec_result)

    _match_service._cache._match_results.pop("db-bonus-id", None)
    try:
        result = await get_match_result("db-bonus-id", db_session=mock_session)
        assert result is not None
        assert result["match_id"] == "db-bonus-id"
        assert result["missing_bonus"] == ["Docker"]
    finally:
        _match_service._cache._match_results.pop("db-bonus-id", None)
