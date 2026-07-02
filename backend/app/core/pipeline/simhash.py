"""SimHash-based near-duplicate detection for crawled records.

Provides:
- compute_simhash(text) -> 64-bit fingerprint
- is_near_duplicate(hash1, hash2, threshold) -> bool (Hamming-distance check)
- deduplicate_records(records) -> deduplicated list

NOTE: A heavier implementation lives in data_fusion.py; this module exposes
      the minimal, hash-centric API expected by the Sprint-1.2 endpoints.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HASH_BITS = 64


def _tokenize(text: str) -> list[str]:
    """Whitespace + punctuation tokenizer for Chinese / English mixed text."""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    return text.lower().split()


def _simhash_raw(tokens: list[str]) -> int:
    """Compute a SimHash fingerprint from a pre-tokenized list."""
    v = [0] * _HASH_BITS
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(_HASH_BITS):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(_HASH_BITS):
        if v[i] >= 0:
            fingerprint |= 1 << i
    return fingerprint


def _hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two integers."""
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_simhash(text: str) -> int:
    """Return a 64-bit SimHash fingerprint for *text*."""
    return _simhash_raw(_tokenize(text))


def is_near_duplicate(hash1: int, hash2: int, threshold: int = 3) -> bool:
    """Return True when two fingerprints are within *threshold* Hamming distance."""
    return _hamming_distance(hash1, hash2) <= threshold


def deduplicate_records(
    records: list[dict[str, Any]],
    text_key: str = "raw_text",
    threshold: int = 3,
) -> list[dict[str, Any]]:
    """Remove near-duplicate records based on SimHash of *text_key*.

    Preserves first occurrence.  Returns the de-duplicated list.
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
