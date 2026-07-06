"""SimHash-based deduplication service for JD records.

Two-pass dedup strategy:
  1. **Exact dedup** via Redis content-hash lookup (first pass)
  2. **Fuzzy dedup** via SimHash with character 3-grams (second pass)

The SimHash implementation uses character-level n-grams (n=3) which is more
robust for short texts and mixed Chinese/English content than word-level
tokenisation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from loguru import logger  # noqa: I001 — keep stdlib → third-party grouping

# ---------------------------------------------------------------------------
# Core SimHash primitives
# ---------------------------------------------------------------------------

def _char_ngrams(text: str, n: int = 3) -> list[str]:
    """Extract character n-grams from *text*.

    Whitespace is collapsed and the text is lowercased before extraction so
    that formatting differences are minimised.
    """
    normalised = " ".join((text or "").lower().split())
    if len(normalised) < n:
        return [normalised] if normalised else []
    return [normalised[i : i + n] for i in range(len(normalised) - n + 1)]


def _hash64(token: str) -> int:
    """Return a 64-bit hash for a single token using MD5."""
    h = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


def simhash(text: str, hash_bits: int = 64) -> int:
    """Compute a SimHash fingerprint for *text* using character 3-grams.

    Parameters
    ----------
    text:
        The input string (typically a JD description).
    hash_bits:
        Number of bits in the output hash (default 64).

    Returns
    -------
    int
        A *hash_bits*-bit SimHash fingerprint.  Returns 0 for empty input.
    """
    ngrams = _char_ngrams(text, n=3)
    if not ngrams:
        return 0

    v = [0] * hash_bits
    for gram in ngrams:
        h = _hash64(gram)
        for i in range(hash_bits):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i, weight in enumerate(v):
        if weight > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Return the Hamming distance between two integer hashes."""
    return bin(hash1 ^ hash2).count("1")


def is_near_duplicate(hash1: int, hash2: int, threshold: int = 3) -> bool:
    """Return True if *hash1* and *hash2* are within *threshold* bits."""
    return hamming_distance(hash1, hash2) <= threshold


# ---------------------------------------------------------------------------
# Record-level dedup helpers
# ---------------------------------------------------------------------------

@dataclass
class DedupRecord:
    """Lightweight wrapper that carries a record alongside its SimHash."""

    record: Any
    simhash_value: int


def _content_hash(text: str) -> str:
    """SHA-256 hex digest for exact-match dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _redis_exact_dedup(
    records: list[Any],
    text_getter: Any,
    redis_client: Any,
    redis_key_prefix: str = "dedup:exact:",
) -> tuple[list[Any], list[Any]]:
    """First pass: exact dedup via Redis content-hash set.

    Parameters
    ----------
    records:
        Iterable of record objects.
    text_getter:
        A callable that extracts the text from a record.
    redis_client:
        An async Redis client (or ``None`` to skip this pass).
    redis_key_prefix:
        Key prefix used in Redis.

    Returns
    -------
    (unique_records, duplicate_records)
    """
    if redis_client is None:
        return list(records), []

    unique: list[Any] = []
    duplicates: list[Any] = []

    for rec in records:
        text = text_getter(rec)
        chash = _content_hash(text)
        key = f"{redis_key_prefix}{chash}"
        exists = await redis_client.exists(key)
        if exists:
            duplicates.append(rec)
        else:
            # Mark as seen with a 7-day TTL
            await redis_client.setex(key, 7 * 86400, "1")
            unique.append(rec)

    return unique, duplicates


def _simhash_fuzzy_dedup(
    records: list[Any],
    text_getter: Any,
    threshold: int = 3,
) -> tuple[list[Any], list[Any]]:
    """Second pass: fuzzy dedup via SimHash + Hamming distance.

    For each record, compute a SimHash and compare against all previously
    accepted hashes.  If the Hamming distance to any accepted hash is <=
    *threshold*, the record is marked as a near-duplicate.

    Parameters
    ----------
    records:
        Records that survived exact dedup.
    text_getter:
        Callable to extract comparison text from a record.
    threshold:
        Maximum Hamming distance to consider near-duplicate.

    Returns
    -------
    (unique_records, duplicate_records)
    """
    unique: list[Any] = []
    duplicates: list[Any] = []
    accepted_hashes: list[int] = []

    for rec in records:
        text = text_getter(rec)
        h = simhash(text)
        dup = any(is_near_duplicate(h, ah, threshold) for ah in accepted_hashes)
        if dup:
            duplicates.append(rec)
        else:
            accepted_hashes.append(h)
            unique.append(rec)

    return unique, duplicates


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def dedup_jd_records(
    records: list[Any],
    text_getter: Any = None,
    redis_client: Any = None,
    threshold: int = 3,
) -> tuple[list[Any], list[Any]]:
    """Deduplicate JD records using exact-then-fuzzy two-pass strategy.

    Parameters
    ----------
    records:
        List of record objects to deduplicate.
    text_getter:
        Callable that extracts comparison text from a record.
        Defaults to ``lambda r: getattr(r, 'clean_text', '') or ''``.
    redis_client:
        Optional async Redis client for exact dedup persistence.
    threshold:
        SimHash Hamming distance threshold for fuzzy dedup.

    Returns
    -------
    (unique_records, duplicate_records)
        *duplicate_records* includes both exact and fuzzy duplicates.
    """
    if text_getter is None:

        def _default_text_getter(r: Any) -> str:
            return getattr(r, "clean_text", "") or ""

        text_getter = _default_text_getter

    if not records:
        return [], []

    # --- Pass 1: Exact dedup (Redis) ---
    after_exact, exact_dups = await _redis_exact_dedup(
        records, text_getter, redis_client,
    )
    logger.info(
        "Exact dedup: {} total -> {} unique, {} exact duplicates",
        len(records), len(after_exact), len(exact_dups),
    )

    # --- Pass 2: Fuzzy dedup (SimHash) ---
    unique, fuzzy_dups = _simhash_fuzzy_dedup(
        after_exact, text_getter, threshold=threshold,
    )
    logger.info(
        "Fuzzy dedup: {} after exact -> {} unique, {} fuzzy duplicates",
        len(after_exact), len(unique), len(fuzzy_dups),
    )

    all_duplicates = exact_dups + fuzzy_dups
    return unique, all_duplicates
