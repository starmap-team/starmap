"""Multi-source data fusion engine.

Provides:
- SimHash-based deduplication for crawled job descriptions
- Source authority weighting for cross-source aggregation
- Cross-validation: at least N independent sources must confirm a fact
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# SimHash-based deduplication
#
# Phase 6 D-08: this module used to ship its own SimHash implementation side-by-side
# with ``app.core.pipeline.simhash``. Per D-08..D-10 the canonical implementation lives in
# ``app.core.pipeline.simhash``; this file is now a thin re-export layer that preserves the
# historical 5-name public surface (``_tokenize`` / ``_simhash`` / ``compute_simhash``
# / ``is_near_duplicate`` / ``deduplicate_records`` / ``_hamming_distance``) used by
# downstream callers (executor, dedup_service). Signature compatibility:
# - ``_simhash(tokens, hash_bits=64)`` here wraps simhash._simhash_raw(tokens) with the
#   default 64-bit width preserved so callers that pass hash_bits=64 get the same result.
# - ``is_near_duplicate(text_a, text_b, threshold=6)`` takes two strings here (legacy
#   pre-D-08 behavior), so we hash each before delegating.
# ---------------------------------------------------------------------------
from app.core.pipeline.simhash import (
    _hamming_distance,
    _simhash_raw,
    _tokenize,
)


def _simhash(tokens: list[str], hash_bits: int = 64) -> int:
    """Thin wrapper around ``simhash._simhash_raw`` honoring the historic ``hash_bits`` kwarg.

    simhash._simhash_raw always operates at the canonical 64-bit width; callers passing
    hash_bits != 64 get the 64-bit result rather than a wrong-width fingerprint.
    """
    del hash_bits  # shim kwarg kept for backwards compatibility
    return _simhash_raw(tokens)


def compute_simhash(text: str) -> int:
    """Public helper: return SimHash fingerprint for *text*."""
    return _simhash_raw(_tokenize(text))


def is_near_duplicate(
    text_a: str,
    text_b: str,
    threshold: int = 6,
) -> bool:
    """Return True if two texts are near-duplicates (Hamming distance <= threshold)."""
    ha = compute_simhash(text_a)
    hb = compute_simhash(text_b)
    return _hamming_distance(ha, hb) <= threshold


def deduplicate_records(
    records: list[dict[str, Any]],
    text_key: str = "raw_text",
    threshold: int = 6,
) -> list[dict[str, Any]]:
    """Remove near-duplicate records based on SimHash of *text_key*.

    Preserves the first occurrence. Returns the de-duplicated list.
    """
    seen_hashes: list[int] = []
    unique: list[dict[str, Any]] = []

    for rec in records:
        text = rec.get(text_key, "")
        h = _simhash_raw(_tokenize(text))
        dup = False
        for seen in seen_hashes:
            if _hamming_distance(h, seen) <= threshold:
                dup = True
                break
        if not dup:
            seen_hashes.append(h)
            unique.append(rec)

    return unique


# ---------------------------------------------------------------------------
# Source authority weighting
# ---------------------------------------------------------------------------

@dataclass
class SourceWeight:
    """Weight descriptor for a single data source."""

    name: str
    authority_score: float = 0.5  # 0.0 – 1.0
    record_count: int = 0


def weighted_merge(
    source_values: dict[str, float],
    source_weights: dict[str, float],
) -> float:
    """Compute the authority-weighted average of per-source values.

    Parameters
    ----------
    source_values : dict[source_name -> value]
    source_weights : dict[source_name -> weight (0-1)]

    Returns
    -------
    float : weighted average, 0.0 if no sources contribute.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for name, value in source_values.items():
        w = source_weights.get(name, 0.5)
        weighted_sum += value * w
        total_weight += w
    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

@dataclass
class CrossValidationResult:
    """Outcome of cross-validating a fact across multiple sources."""

    fact: str
    confirming_sources: list[str] = field(default_factory=list)
    rejecting_sources: list[str] = field(default_factory=list)
    is_confirmed: bool = False
    confidence: float = 0.0


def cross_validate(
    fact: str,
    source_claims: dict[str, bool],
    min_confirmations: int = 2,
    source_weights: dict[str, float] | None = None,
) -> CrossValidationResult:
    """Validate a fact across independent sources.

    Parameters
    ----------
    fact : human-readable description of the fact being validated
    source_claims : source_name -> True (confirms) / False (rejects)
    min_confirmations : minimum number of independent sources to confirm
    source_weights : optional authority weights per source

    Returns
    -------
    CrossValidationResult with confirmation status and weighted confidence.
    """
    confirming = [s for s, v in source_claims.items() if v]
    rejecting = [s for s, v in source_claims.items() if not v]
    is_confirmed = len(confirming) >= min_confirmations

    # Compute weighted confidence
    if source_weights is None:
        source_weights = {}
    confirm_weight = sum(source_weights.get(s, 0.5) for s in confirming)
    reject_weight = sum(source_weights.get(s, 0.5) for s in rejecting)
    total = confirm_weight + reject_weight
    confidence = confirm_weight / total if total > 0 else 0.0

    return CrossValidationResult(
        fact=fact,
        confirming_sources=confirming,
        rejecting_sources=rejecting,
        is_confirmed=is_confirmed,
        confidence=round(confidence, 4),
    )


# ---------------------------------------------------------------------------
# Convenience: full fusion pipeline
# ---------------------------------------------------------------------------

def fuse_crawl_results(
    records: list[dict[str, Any]],
    source_weights: dict[str, float] | None = None,
    dedup_threshold: int = 6,
    min_cross_confirm: int = 2,
) -> dict[str, Any]:
    """Run the complete fusion pipeline on raw crawl results.

    Steps:
    1. Deduplicate via SimHash
    2. Weight records by source authority
    3. Cross-validate key fields

    Returns a summary dict with counts and fused records.
    """
    if source_weights is None:
        source_weights = {}

    # Step 1: dedup
    deduped = deduplicate_records(records, threshold=dedup_threshold)

    # Step 2: group by a normalised title+company key for cross-validation
    groups: dict[str, list[dict[str, Any]]] = {}
    for rec in deduped:
        key = _normalize_key(rec.get("title", ""), rec.get("company", ""))
        groups.setdefault(key, []).append(rec)

    fused: list[dict[str, Any]] = []
    cross_validated_count = 0
    for _key, group in groups.items():
        sources_in_group = {r.get("source", "unknown") for r in group}
        is_confirmed = len(sources_in_group) >= min_cross_confirm
        if is_confirmed:
            cross_validated_count += 1
        # Pick the record from the highest-authority source
        best = max(
            group,
            key=lambda r: source_weights.get(r.get("source", ""), 0.5),
        )
        best["cross_validated"] = is_confirmed
        best["source_count"] = len(sources_in_group)
        fused.append(best)

    return {
        "input_count": len(records),
        "after_dedup": len(deduped),
        "dedup_removed": len(records) - len(deduped),
        "groups": len(groups),
        "cross_validated": cross_validated_count,
        "fused_records": fused,
    }


def _normalize_key(title: str, company: str) -> str:
    """Create a normalised grouping key from title + company."""
    t = re.sub(r"\s+", "", title.lower())
    c = re.sub(r"\s+", "", company.lower())
    return f"{t}|{c}"
