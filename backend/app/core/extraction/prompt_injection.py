"""Input-side prompt-injection detector (CONCERN 1.6, Phase 24).

JD / resume text is user-supplied and concatenated into LLM prompts. Without
input sanitization, an injected "Ignore previous instructions" line can steer
extraction (skill hallucination, extraction poisoning). This module detects
adversarial prefixes before prompt assembly and records the refusal so the
caller can reject or quarantine the content.

Deliberately conservative: flags known adversarial-prefix patterns plus
instruction-override keywords, and reports a per-request verdict. The caller
decides the response (reject / strip / proceed-with-warning).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


class InjectionCheckResult(BaseModel):
    """Prompt-injection scan verdict for a single user-supplied block."""

    is_clean: bool = Field(default=True, description="True when no injection pattern matched")
    matched_patterns: list[str] = Field(
        default_factory=list, description="Names of the injection patterns that matched"
    )
    snippet: str = Field(default="", description="First 200 chars of the matched region")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Detection confidence (heuristic)"
    )


# Patterns keyed by stable name. Each is an (regex, weight) pair; a match pushes
# confidence up. Weights are deliberately modest so normal text that mentions
# "instructions" once (e.g. "follow instructions in the job spec") does not
# false-positive — a match requires either a high-weight pattern or several
# low-weight hits.
_INJECTION_PATTERNS: dict[str, tuple[re.Pattern[str], float]] = {
    # Classic prompt-override attacks
    "ignore_previous_instructions": (
        re.compile(r"(?i)\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,60}\b(previous|prior|all|above)\b[^.\n]{0,60}\b(instructions?|prompts?|rules?|context)\b"),
        0.9,
    ),
    "new_instructions": (
        re.compile(r"(?i)\b(now|from now on|instead)\b[^.\n]{0,40}\b(you (are|will)|act as|behave as)\b"),
        0.85,
    ),
    "ignore_rules_above": (
        re.compile(r"(?i)\bignore\b[^.\n]{0,40}\b(rules|guidelines|directives)\b[^.\n]{0,60}\b(above|previously|earlier)\b"),
        0.9,
    ),
    "role_system_prompt": (
        re.compile(r"(?i)\b(system prompt|system message|developer message)\b[^.\n]{0,60}\b(reveal|show|print|output|display)\b"),
        0.85,
    ),
    "reveal_prompt": (
        re.compile(r"(?i)\b(reveal|show|print|display|output|leak|dump)\b[^.\n]{0,40}\b(the )?(full|entire|complete|original|hidden)?\b[^.\n]{0,20}\b(prompt|instructions?|system message)\b"),
        0.8,
    ),
    "adversarial_role_switch": (
        re.compile(r"(?i)\b(you are now|you are not|do not act as|stop being)\b"),
        0.6,
    ),
    "data_poisoning_skill": (
        re.compile(r"(?i)\b(add|list|include)\b[^.\n]{0,40}\b(this (skill|keyword|term))\b[^.\n]{0,60}\b(to (all|every|each))\b"),
        0.7,
    ),
}

_REFUSAL_KEYWORDS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "override your instructions",
    "you are now",
    "system prompt:",
    "reveal your prompt",
    "print your instructions",
)


def scan_prompt_injection(content: str) -> InjectionCheckResult:
    """Scan a user-supplied text block for prompt-injection patterns.

    Returns an :class:`InjectionCheckResult` with a conservative verdict:
    ``is_clean=True`` means no high-confidence pattern matched; the caller may
    still decide to strip matching regions or reject the request entirely.
    """
    result = InjectionCheckResult()
    if not content or not content.strip():
        return result

    # Line-oriented scan keeps snippets readable and avoids regex catastrophic
    # backtracking on very long JD texts (each line scanned independently).
    total_weight = 0.0
    matched: list[str] = []
    snippet = ""

    for line in content.splitlines():
        line_lower = line.lower()
        for name, (pattern, weight) in _INJECTION_PATTERNS.items():
            if pattern.search(line):
                if name not in matched:
                    matched.append(name)
                total_weight += weight
                if not snippet:
                    snippet = line.strip()[:200]
        for kw in _REFUSAL_KEYWORDS:
            if kw in line_lower:
                if "refusal_keyword" not in matched:
                    matched.append("refusal_keyword")
                total_weight += 0.75
                if not snippet:
                    snippet = line.strip()[:200]

    if matched:
        result.is_clean = False
        result.matched_patterns = matched
        result.snippet = snippet
        result.confidence = min(1.0, total_weight)
    return result


def sanitize_prompt_content(content: str, *, max_chars: int = 4000) -> str:
    """Strip matched injection regions before prompt assembly.

    Falls back to truncation if the block is pathological. Callers that want
    strict rejection should check :func:`scan_prompt_injection` first and treat
    ``is_clean=False`` as a hard refusal.
    """
    if not content:
        return content
    cleaned_lines: list[str] = []
    for line in content.splitlines():
        if _INJECTION_PATTERNS["ignore_previous_instructions"][0].search(line) or any(
            kw in line.lower() for kw in _REFUSAL_KEYWORDS
        ):
            continue  # drop the adversarial line
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    if max_chars and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned
