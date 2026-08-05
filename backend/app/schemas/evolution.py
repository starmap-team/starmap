"""演化域 Schema：职业路径规划 (PLAN-014 批次10 迁入集中管理)。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CareerPathNode(BaseModel):
    """A node in the career path graph."""

    position: str
    similarity: float = 0.0
    skill_overlap: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    direction: str = Field(default="forward", description="forward | lateral | up")


class CareerPathResponse(BaseModel):
    """Career path planning response."""

    origin: str
    nodes: list[CareerPathNode] = Field(default_factory=list)
    total_paths: int = 0
