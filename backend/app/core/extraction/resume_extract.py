"""Resume extraction pipeline — independent from JD extraction.

This module provides a dedicated extraction pipeline for resume text,
using resume-specific prompts and parsing logic that understands
resume structure (education, work experience, projects, certifications).

Key differences from JD extraction:
- Resume has chronological structure (timeline-based)
- Skills are inferred from work/project descriptions, not explicitly listed
- Proficiency levels must be inferred (resumes rarely self-assess)
- No "required/preferred" distinction — all skills are candidate's actual skills
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.core.extraction.jd_extract import LLMClient, parse_llm_json_response
from app.core.extraction.normalize import batch_normalize_skills
from app.core.extraction.prompt import get_prompt


@dataclass
class ResumeSkill:
    """A skill extracted from a resume with inferred proficiency."""

    name: str
    inferred_level: str = "熟悉"  # 了解 / 熟悉 / 精通
    inferred_years: float = 0.0
    category: str = "hard_skill"
    evidence: str = ""  # 推断依据
    original_name: str = ""


@dataclass
class WorkExperience:
    """A work experience entry from a resume."""

    company: str = ""
    position: str = ""
    duration: str = ""
    responsibilities: str = ""
    skills_used: list[str] = field(default_factory=list)


@dataclass
class ProjectExperience:
    """A project experience entry from a resume."""

    project_name: str = ""
    description: str = ""
    skills_used: list[str] = field(default_factory=list)


@dataclass
class Education:
    """An education entry from a resume."""

    school: str = ""
    degree: str = ""
    major: str = ""
    graduation_year: int | None = None


@dataclass
class Certification:
    """A certification entry from a resume."""

    name: str = ""
    issuer: str = ""


@dataclass
class ResumeExtractionResult:
    """Structured result of resume extraction."""

    candidate_name: str | None = None
    contact_info: dict[str, str] = field(default_factory=dict)
    education: list[Education] = field(default_factory=list)
    work_experience: list[WorkExperience] = field(default_factory=list)
    project_experience: list[ProjectExperience] = field(default_factory=list)
    skills: list[ResumeSkill] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    raw_text: str = ""

    def to_skill_dicts(self) -> list[dict[str, Any]]:
        """Convert skills to the dict format expected by MatchService."""
        return [
            {
                "name": s.name,
                "proficiency": s.inferred_level,
                "category": s.category,
                "evidence": s.evidence,
            }
            for s in self.skills
        ]


class ResumeExtractionPipeline:
    """Pipeline for extracting structured information from resume text."""

    llm_client: LLMClient = field(default_factory=LLMClient)
    normalize_skills_enabled: bool = True
    use_vector_normalization: bool = False  # Disabled: rely on alias table
    vector_threshold: float = 0.85

    async def run(self, resume_text: str) -> dict[str, Any]:
        """Execute the full resume extraction pipeline.

        Args:
            resume_text: Extracted plaintext from PDF/DOCX resume.

        Returns:
            Dict with 'success', 'data', 'warnings', 'normalization', 'error'.
        """
        result: dict[str, Any] = {
            "success": False,
            "data": None,
            "warnings": [],
            "normalization": [],
            "error": None,
            "prompt_version_used": "v2",
        }

        if not resume_text or not resume_text.strip():
            result["error"] = "Empty resume content"
            return result

        # Step 1: Call LLM with resume-specific prompt
        logger.info("Resume extraction pipeline starting ({} chars)", len(resume_text))
        try:
            _ = get_prompt("resume_extraction", version="v2", resume_content=resume_text)
        except (KeyError, ValueError) as e:
            result["error"] = f"Prompt error: {e}"
            return result

        try:
            raw = await self.llm_client.extract_from_jd(resume_text)
        except Exception as e:
            logger.error("LLM call failed for resume: {}", e)
            result["error"] = f"LLM error: {e}"
            return result

        # Step 2: Parse JSON
        try:
            parsed = parse_llm_json_response(raw["content"]) if isinstance(raw, dict) and "content" in raw else raw
        except Exception as e:
            result["error"] = f"JSON parse error: {e}"
            return result

        # Step 3: Build structured result
        try:
            extraction = self._build_result(parsed)
        except Exception as e:
            logger.warning("Resume result building failed: {}", e)
            result["warnings"].append(f"Result building issue: {e}")
            extraction = ResumeExtractionResult(raw_text=resume_text)

        # Step 4: Normalize skills
        if self.normalize_skills_enabled and extraction.skills:
            skill_names = [s.name for s in extraction.skills]
            normalized_results = batch_normalize_skills(
                skill_names,
                use_vector=self.use_vector_normalization,
                vector_threshold=self.vector_threshold,
            )
            result["normalization"] = [nr.__dict__ for nr in normalized_results]

            for skill, nr in zip(extraction.skills, normalized_results, strict=False):
                if nr.normalized:
                    skill.original_name = skill.name
                    skill.name = nr.normalized

        # Step 5: Build final output
        result["success"] = True
        result["data"] = self._serialize_result(extraction)
        logger.info(
            "Resume extraction complete: {} skills, {} work entries, {} projects",
            len(extraction.skills),
            len(extraction.work_experience),
            len(extraction.project_experience),
        )
        return result

    def _build_result(self, parsed: dict[str, Any]) -> ResumeExtractionResult:
        """Build ResumeExtractionResult from parsed LLM output."""
        result = ResumeExtractionResult(raw_text="")

        result.candidate_name = parsed.get("candidate_name")
        result.contact_info = parsed.get("contact_info") or {}

        # Education
        for edu in parsed.get("education", []):
            if isinstance(edu, dict):
                result.education.append(
                    Education(
                        school=edu.get("school", ""),
                        degree=edu.get("degree", ""),
                        major=edu.get("major", ""),
                        graduation_year=edu.get("graduation_year"),
                    )
                )

        # Work experience
        for work in parsed.get("work_experience", []):
            if isinstance(work, dict):
                result.work_experience.append(
                    WorkExperience(
                        company=work.get("company", ""),
                        position=work.get("position", ""),
                        duration=work.get("duration", ""),
                        responsibilities=work.get("responsibilities", ""),
                        skills_used=work.get("skills_used", []) or [],
                    )
                )

        # Project experience
        for proj in parsed.get("project_experience", []):
            if isinstance(proj, dict):
                result.project_experience.append(
                    ProjectExperience(
                        project_name=proj.get("project_name", ""),
                        description=proj.get("description", ""),
                        skills_used=proj.get("skills_used", []) or [],
                    )
                )

        # Skills (core)
        for skill in parsed.get("skills", []):
            if isinstance(skill, dict):
                result.skills.append(
                    ResumeSkill(
                        name=skill.get("name", ""),
                        inferred_level=skill.get("inferred_level", "熟悉"),
                        inferred_years=float(skill.get("inferred_years", 0) or 0),
                        category=skill.get("category", "hard_skill"),
                        evidence=skill.get("evidence", ""),
                    )
                )

        # Certifications
        for cert in parsed.get("certifications", []):
            if isinstance(cert, dict):
                result.certifications.append(
                    Certification(
                        name=cert.get("name", ""),
                        issuer=cert.get("issuer", ""),
                    )
                )

        return result

    def _serialize_result(self, extraction: ResumeExtractionResult) -> dict[str, Any]:
        """Serialize ResumeExtractionResult to plain dict."""
        return {
            "candidate_name": extraction.candidate_name,
            "contact_info": extraction.contact_info,
            "education": [
                {
                    "school": e.school,
                    "degree": e.degree,
                    "major": e.major,
                    "graduation_year": e.graduation_year,
                }
                for e in extraction.education
            ],
            "work_experience": [
                {
                    "company": w.company,
                    "position": w.position,
                    "duration": w.duration,
                    "responsibilities": w.responsibilities,
                    "skills_used": w.skills_used,
                }
                for w in extraction.work_experience
            ],
            "project_experience": [
                {
                    "project_name": p.project_name,
                    "description": p.description,
                    "skills_used": p.skills_used,
                }
                for p in extraction.project_experience
            ],
            "skills": [
                {
                    "name": s.name,
                    "inferred_level": s.inferred_level,
                    "inferred_years": s.inferred_years,
                    "category": s.category,
                    "evidence": s.evidence,
                    "original_name": s.original_name,
                }
                for s in extraction.skills
            ],
            "certifications": [{"name": c.name, "issuer": c.issuer} for c in extraction.certifications],
        }


async def extract_from_resume(resume_text: str) -> dict[str, Any]:
    """Convenience function to run the full resume extraction pipeline.

    Args:
        resume_text: Extracted plaintext from PDF/DOCX resume.

    Returns:
        Pipeline result dict with keys: success, data, warnings, normalization, error.
    """
    pipeline = ResumeExtractionPipeline()
    return await pipeline.run(resume_text)
