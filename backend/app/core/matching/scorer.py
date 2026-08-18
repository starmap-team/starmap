"""技能匹配评分模块。

提供多维度的技能匹配评分算法，包括精确匹配、模糊匹配、向量匹配和熟练度覆盖。
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, cast

from loguru import logger

from app.config import settings
from app.core.constants import DEFAULT_PROFICIENCY, GAP_LEVEL_MASTERED, GAP_LEVEL_MISSING, GAP_LEVEL_PARTIAL
from app.core.extraction.normalize import normalize_skill
from app.core.matching.constants import PROFICIENCY_SCORE
from app.exceptions import StarMapError

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


def _batch_chroma_match(
    target_names: list[str],
    candidate_canonical_names: set[str],
) -> dict[str, float]:
    """Query ChromaDB in a single batch for multiple target names.

    Replaces per-skill calls to normalize_by_vector with one batch query,
    reducing N ChromaDB round-trips to 1.

    Args:
        target_names: List of target skill canonical names needing ChromaDB fallback.
        candidate_canonical_names: Set of candidate canonical names to match against.

    Returns:
        Dict mapping target_name -> chroma_match_score for matched skills.
    """
    if not target_names or not candidate_canonical_names:
        return {}

    try:
        from app.core.extraction.normalize import (
            CHROMA_COLLECTION_NAME,
            _is_chroma_marked_unavailable,
            _mark_chroma_unavailable,
            get_embedding,
        )
    except ImportError:
        return {}

 # Negative-cache fast-fail
    if _is_chroma_marked_unavailable():
        return {}

    try:
        import chromadb
    except ImportError:
        _mark_chroma_unavailable("chromadb-not-installed")
        return {}

 # Connect to ChromaDB
    try:
        chroma_client = chromadb.HttpClient(
            host=settings.chroma_host, port=settings.chroma_port,
        )
    except StarMapError:
        raise
    except Exception as exc:
 # Chroma is an OPTIONAL semantic boost; connection failure must not
 # break matching — degrade to lexical scoring ( conformance).
        logger.warning("Chroma unavailable (connect), degrading to lexical match: {}", exc)
        _mark_chroma_unavailable(f"chroma-connect:{exc}")
        return {}

    collection_name = CHROMA_COLLECTION_NAME
    try:
        collection = chroma_client.get_collection(collection_name)
    except StarMapError:
        raise
    except Exception as exc:
 # 404 here = embedding collection not provisioned; degrade gracefully
 # and negative-cache so subsequent calls fast-fail to lexical scoring.
        logger.warning("Chroma collection '{}' unavailable, degrading to lexical match: {}", collection_name, exc)
        _mark_chroma_unavailable(f"chroma-collection-missing:{exc}")
        return {}

 # Batch embed all target names
    query_embeddings: list[list[float]] = []
    valid_targets: list[str] = []
    for name in target_names:
        emb = get_embedding(name)
        if emb:
            query_embeddings.append(emb)
            valid_targets.append(name)

    if not query_embeddings:
        return {}

 # Single batch query
    try:
        results = collection.query(
            query_embeddings=cast("Any", query_embeddings),
            n_results=1,
            include=cast("Any", ["distances", "metadatas"]),
        )
    except StarMapError:
        raise
    except Exception as exc:
        logger.warning("Chroma query failed, degrading to lexical match: {}", exc)
        _mark_chroma_unavailable(f"chroma-query:{exc}")
        return {}

 # Parse batch results
    matches: dict[str, float] = {}
    distances = results.get("distances")
    metadatas = results.get("metadatas")

    if distances is None or metadatas is None:
        return {}

    for i, target in enumerate(valid_targets):
        if i >= len(distances) or not distances[i]:
            continue
        distance = distances[i][0]
        similarity = 1.0 - distance
        if similarity >= CHROMA_SIMILARITY_THRESHOLD:
            metadata = metadatas[i][0] if i < len(metadatas) and metadatas[i] else {}
            matched_name = metadata.get("standard_name") if metadata else None
            if matched_name and matched_name in candidate_canonical_names:
                matches[target] = CHROMA_SIMILARITY_THRESHOLD

    return matches


def _chroma_match_against_candidates(
    target_name: str,
    candidate_canonical_names: set[str],
) -> float | None:
    """Query ChromaDB for a single target name against candidate set.

    Kept for backward compatibility with existing tests. Internally delegates
    to _batch_chroma_match for single-item queries.

    Args:
        target_name: Target skill canonical name.
        candidate_canonical_names: Set of candidate canonical names.

    Returns:
        CHROMA_SIMILARITY_THRESHOLD if match found, None otherwise.
    """
    try:
        result = _batch_chroma_match([target_name], candidate_canonical_names)
        return result.get(target_name)
    except StarMapError:
        raise
    except Exception as exc:
 # Defensive: inner call already degrades; never let an optional
 # semantic boost abort the whole match ( conformance).
        logger.warning("Chroma single-match failed, degrading: {}", exc)
        return None


def score_skill_match(
    *,
    target_skills: list[dict[str, str]],
    person_skills: list[dict[str, Any]],
    threshold: float = settings.match_threshold,
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
            str(item.get("proficiency", DEFAULT_PROFICIENCY)), PROFICIENCY_SCORE[DEFAULT_PROFICIENCY]
        )

    candidate_canonical_set = set(person_level_map.keys())

 # : compute exact + semantic scores; collect ChromaDB fallback targets
    intermediate: list[dict[str, Any]] = []
    chroma_targets: list[str] = []

    for item in target_skills:
        target_name = _canonical_skill_name(item["skill"])
        target_level = PROFICIENCY_SCORE.get(item.get("proficiency", DEFAULT_PROFICIENCY), PROFICIENCY_SCORE[DEFAULT_PROFICIENCY])

 # Exact match
        exact = 1.0 if target_name in person_level_map else 0.0

 # Semantic similarity
        best_semantic = max(
            (_semantic_similarity(target_name, candidate) for candidate in person_name_map.values()),
            default=0.0,
        )

 # Track whether ChromaDB fallback is needed
        needs_chroma = exact == 0.0 and best_semantic < FUZZY_MATCH_THRESHOLD
        if needs_chroma:
            chroma_targets.append(target_name)

        intermediate.append({
            "item": item,
            "target_name": target_name,
            "target_level": target_level,
            "exact": exact,
            "best_semantic": best_semantic,
            "needs_chroma": needs_chroma,
        })

 # : single batch ChromaDB query for all fallback targets
    chroma_results = _batch_chroma_match(chroma_targets, candidate_canonical_set)

 # : compute final scores with ChromaDB results
    evaluated: list[dict[str, Any]] = []
    for entry in intermediate:
        target_name = entry["target_name"]
        target_level = entry["target_level"]
        exact = entry["exact"]
        best_semantic = entry["best_semantic"]
        item = entry["item"]

 # ChromaDB match (from batch results)
        chroma_match = 0.0
        if entry["needs_chroma"] and target_name in chroma_results:
            chroma_match = chroma_results[target_name]

 # Fuzzy match
        fuzzy_match = 1.0 if best_semantic >= FUZZY_MATCH_THRESHOLD else best_semantic
        if chroma_match >= CHROMA_SIMILARITY_THRESHOLD and fuzzy_match < 1.0:
            fuzzy_match = max(fuzzy_match, chroma_match * 0.9)

 # Calculate scores
        recall_score = (0.5 * exact) + (0.3 * fuzzy_match) + (0.2 * best_semantic)
        user_level = person_level_map.get(target_name, 0.0)
        proficiency_coverage = min(1.0, user_level / target_level) if target_level else 1.0
 # P0-AUDIT-FIX (2026-08-13): the old formula `recall_score * (0.65 + 0.35*coverage)`
 # guaranteed final_score >= 0.65 * recall_score even when coverage=0,
 # so missing skills with any fuzzy/best_semantic signal were inflated
 # into PARTIAL/MASTERED territory. Make coverage=0 the honest case:
 # final_score == recall_score (no proficiency bonus).
        if proficiency_coverage <= 0.0:
            final_score = recall_score
        else:
            final_score = min(1.0, recall_score * (0.65 + (0.35 * proficiency_coverage)))

 # Gap level determination
        if exact == 1.0:
            gap_level = GAP_LEVEL_MASTERED
        elif final_score >= 0.85:
            gap_level = GAP_LEVEL_MASTERED
        elif final_score >= threshold * 0.75:
            gap_level = GAP_LEVEL_PARTIAL
        else:
            gap_level = GAP_LEVEL_MISSING

        evaluated.append({
            "skill": target_name,
            "importance": item["importance"],
            "gap_level": gap_level,
            "score": round(final_score, 4),
            "learning_path": [target_name],
        })

    return {"evaluated": evaluated}
