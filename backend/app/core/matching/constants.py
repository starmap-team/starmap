"""Shared constants for the matching & learning modules.

Single source of truth for proficiency scores, node labels, and other
domain constants that were previously duplicated across modules.
"""

# ── Proficiency scoring ──
PROFICIENCY_SCORE: dict[str, float] = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}

# ── Neo4j node labels allowed for creation/query ──
ALLOWED_NODE_LABELS: frozenset[str] = frozenset(
    {"Position", "Skill", "KnowledgeArea", "Tool", "Domain", "Industry",
     "Certificate", "LearningResource"}
)

# ── Senior-level keywords for position classification ──
SENIOR_KEYWORDS: frozenset[str] = frozenset(
    {"高级", "资深", "专家", "主管", "经理", "总监", "架构师", "senior", "lead", "principal"}
)
