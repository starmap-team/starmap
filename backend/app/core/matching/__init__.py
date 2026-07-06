"""Matching module public API.

Provides backward-compatible imports for the refactored matching system.
"""

from app.core.matching.cache import MatchCache, get_match_cache, reset_match_cache
from app.core.matching.path_builder import build_learning_path
from app.core.matching.scorer import score_skill_match
from app.core.matching.service import MatchService

__all__ = [
    "MatchCache",
    "get_match_cache",
    "reset_match_cache",
    "build_learning_path",
    "score_skill_match",
    "MatchService",
]
