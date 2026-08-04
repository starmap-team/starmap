"""Fixture data Pydantic models."""
from pydantic import BaseModel, Field


class SkillFixture(BaseModel):
    name: str
    category: str = "hard_skill"
    aliases: list[str] = Field(default_factory=list)


class PositionSkillRef(BaseModel):
    name: str
    category: str = "hard_skill"


class PositionFixture(BaseModel):
    name: str
    industry: str = "信息技术/互联网"
    level: str = "senior"
    skills: list[PositionSkillRef] = Field(default_factory=list)


class KnowledgeAreaFixture(BaseModel):
    name: str
    description: str = ""


class ToolFixture(BaseModel):
    name: str
    category: str = ""
    description: str = ""


class EvolvesToRelation(BaseModel):
    source: str = Field(alias="from")
    target: str = Field(alias="to")


class PrerequisiteRelation(BaseModel):
    source: str
    target: str


class RelationsFixture(BaseModel):
    evolves_to: list[EvolvesToRelation] = Field(default_factory=list)
    prerequisite: list[PrerequisiteRelation] = Field(default_factory=list)
