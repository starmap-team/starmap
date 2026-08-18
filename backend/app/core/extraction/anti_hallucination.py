"""Anti-hallucination checker for skill extraction.

Extracted from jd_extract.py to provide independent verification that
extracted skills are plausible, filtering out weird/garbage skills and
adjusting confidence scores based on pattern matching.
"""

import re
from typing import Any

from pydantic import BaseModel, Field


class AntiHallucinationResult(BaseModel):
    """Anti-hallucination validation result."""

    is_valid: bool = Field(default=True)
    hallucinated_skills: list[str | dict[str, Any]] = Field(default_factory=list)
    missing_skills: list[str | dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


def normalize_skill_list(skills: list[str | dict[str, Any]]) -> list[str]:
    """Normalize skill list items to strings (extract 'name' key if dict)."""
    result = []
    for s in skills:
        if isinstance(s, dict):
            result.append(str(s.get("name", str(s))))
        else:
            result.append(str(s))
    return result


def normalize_str_list(items: list[Any]) -> list[str]:
    """Normalize list items, extracting string values from dicts.

    MiMo reasoning model may return dicts with {name, reasoning}
    instead of plain strings — normalise ALL list[str] fields.
    """
    if not items:
        return []
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(item.get("name") or item.get("skill")
                          or item.get("issue") or str(item))
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(str(item))
    return result


class AntiHallucinationChecker:
    """Checks extracted skills for hallucination patterns.

    Applies lightweight rule-based checks before / in addition to the
    LLM-based validation step.
    """

    MIN_SKILL_LENGTH = 2
    MAX_SKILL_LENGTH = 100
    _GARBAGE_PATTERN = re.compile(r"[<>{}|\\^~`]")
    _VALID_SKILL_PATTERN = re.compile(
        r"^[a-zA-Z0-9一-鿿][a-zA-Z0-9一-鿿\s.\-+#/:()]*$"
    )

    def check_skill(
        self, skill_name: str, raw_name: str, confidence: float
    ) -> tuple[bool, float]:
        """Returns (is_valid, adjusted_confidence).

        Args:
            skill_name: Normalized skill name.
            raw_name: Original raw skill name from extraction.
            confidence: Original confidence score (0.0-1.0).

        Returns:
            Tuple of (is_valid, adjusted_confidence).
        """
        name = skill_name.strip()

 # Minimum length check
        if len(name) < self.MIN_SKILL_LENGTH:
            return False, 0.0

 # Maximum length check
        if len(name) > self.MAX_SKILL_LENGTH:
            return False, 0.0

 # Garbage character check
        if self._GARBAGE_PATTERN.search(name):
            return False, 0.0

 # Valid skill name pattern
        if not self._VALID_SKILL_PATTERN.match(name):
            return False, 0.0

        return True, confidence
