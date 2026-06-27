"""Evolution subsystem — Track position skill changes over time.

Modules:
- snapshot_manager: Create/store/retrieve position skill snapshots
- diff_engine: Compute skill changes between snapshots
- trust_integration: Weighted trust scoring with exponential decay
- hallucination_guard: Three-layer hallucination defense
- emergence_finder: Z-score emerging skill detection
- path_recommender: EVOLVES_TO discovery via Jaccard similarity
- trend_detector: Temporal trend analysis
- orchestrator: 8-step pipeline coordinating all components
"""

from app.core.evolution.diff_engine import ChangeType, DiffEngine, DiffResult, SkillChange
from app.core.evolution.hallucination_guard import (
    GuardResult,
    HallucinationGuard,
    LLMJudgment,
    VerificationStatus,
)
from app.core.evolution.snapshot_manager import (
    SkillProfile,
    SnapshotData,
    SnapshotManager,
)
from app.core.evolution.trust_integration import (
    TrustFactors,
    TrustLevel,
    TrustResult,
    TrustScorer,
)

__all__ = [
    "ChangeType",
    "DiffEngine",
    "DiffResult",
    "GuardResult",
    "HallucinationGuard",
    "LLMJudgment",
    "SkillChange",
    "SkillProfile",
    "SnapshotData",
    "SnapshotManager",
    "TrustFactors",
    "TrustLevel",
    "TrustResult",
    "TrustScorer",
    "VerificationStatus",
]
