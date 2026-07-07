"""技能匹配评分模块。

提供多维度的技能匹配评分算法，包括精确匹配、模糊匹配、向量匹配和熟练度覆盖。
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.core.extraction.normalize import normalize_skill

# 技能熟练度量化映射表
PROFICIENCY_SCORE = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}

# 模糊匹配阈值
FUZZY_MATCH_THRESHOLD = 0.7

# ChromaDB 语义相似度阈值
CHROMA_SIMILARITY_THRESHOLD = 0.85


def _canonical_skill_name(name: str) -> str:
    """Canonicalize a skill name using the unified normalization pipeline.

    Delegates to normalize.py's normalize_skill (alias lookup).
    Falls back to the original name if no alias match found.
    """
    result = normalize_skill(name, use_vector=False)
    return result.normalized or name.strip()


def _semantic_similarity(left: str, right: str) -> float:
    """Calculate semantic similarity between two skill names.

    Supports exact match (1.0) and fuzzy match (SequenceMatcher).
    When fuzzy match exceeds FUZZY_MATCH_THRESHOLD, returns the actual ratio.
    """
    left_name = _canonical_skill_name(left).lower()
    right_name = _canonical_skill_name(right).lower()
    if left_name == right_name:
        return 1.0
    ratio = SequenceMatcher(a=left_name, b=right_name).ratio()
    if ratio >= FUZZY_MATCH_THRESHOLD:
        return ratio
    return ratio


def _chroma_match_against_candidates(
    target_name: str,
    candidate_canonical_names: set[str],
) -> float | None:
    """Query ChromaDB once for target_name and check against all candidates.

    Args:
        target_name: Target skill canonical name.
        candidate_canonical_names: Set of candidate canonical names.

    Returns:
        CHROMA_SIMILARITY_THRESHOLD if match found, None otherwise.
    """
    if not candidate_canonical_names:
        return None
    try:
        from app.core.extraction.normalize import normalize_by_vector

        result = normalize_by_vector(
            target_name,
            chroma_client=None,
            threshold=CHROMA_SIMILARITY_THRESHOLD,
        )
        if result is not None and result in candidate_canonical_names:
            return CHROMA_SIMILARITY_THRESHOLD
        return None
    except Exception:
        return None


def score_skill_match(
    *,
    target_skills: list[dict[str, str]],
    person_skills: list[dict[str, Any]],
    threshold: float = 0.6,
) -> dict[str, Any]:
    """Score skill match between target position and person.

    Args:
        target_skills: Target position skills with "skill", "importance", "proficiency".
        person_skills: Person skills with "skill"/"name" and "proficiency".
        threshold: Match threshold, default 0.6.

    Returns:
        Dict with "evaluated" list containing scored skills.
    """
    # Build person skill indexes
    person_level_map: dict[str, float] = {}
    person_name_map: dict[str, str] = {}
    for item in person_skills:
        raw_name = str(item.get("name") or item.get("skill") or "").strip()
        if not raw_name:
            continue
        canonical = _canonical_skill_name(raw_name)
        person_name_map[canonical] = raw_name
        person_level_map[canonical] = PROFICIENCY_SCORE.get(
            str(item.get("proficiency", "熟悉")), 0.65
        )

    set(person_level_map)
    candidate_canonical_set = set(person_level_map.keys())

    def _score_one(item: dict[str, str]) -> dict[str, Any]:
        """Score a single target skill."""
        target_name = _canonical_skill_name(item["skill"])
        target_level = PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65)

        # Exact match
        exact = 1.0 if target_name in person_level_map else 0.0

        # Semantic similarity
        best_semantic = max(
            (_semantic_similarity(target_name, candidate) for candidate in person_name_map.values()),
            default=0.0,
        )

        # ChromaDB fallback
        chroma_match = 0.0
        if exact == 0.0 and best_semantic < FUZZY_MATCH_THRESHOLD:
            chroma_sim = _chroma_match_against_candidates(target_name, candidate_canonical_set)
            if chroma_sim is not None and chroma_sim > chroma_match:
                chroma_match = chroma_sim

        # Fuzzy match
        fuzzy_match = 1.0 if best_semantic >= FUZZY_MATCH_THRESHOLD else best_semantic
        if chroma_match >= CHROMA_SIMILARITY_THRESHOLD and fuzzy_match < 1.0:
            fuzzy_match = max(fuzzy_match, chroma_match * 0.9)

        # Calculate scores
        recall_score = (0.5 * exact) + (0.3 * fuzzy_match) + (0.2 * best_semantic)
        user_level = person_level_map.get(target_name, 0.0)
        proficiency_coverage = min(1.0, user_level / target_level) if target_level else 1.0
        final_score = min(1.0, recall_score * (0.65 + (0.35 * proficiency_coverage)))

        # Gap level determination
        if exact == 1.0:
            gap_level = "已掌握"
        elif final_score >= 0.85:
            gap_level = "已掌握"
        elif final_score >= threshold * 0.75:
            gap_level = "部分掌握"
        else:
            gap_level = "完全缺失"

        return {
            "skill": target_name,
            "importance": item["importance"],
            "gap_level": gap_level,
            "score": round(final_score, 4),
            "learning_path": [target_name],
        }

    evaluated = [_score_one(item) for item in target_skills]
    return {"evaluated": evaluated}
