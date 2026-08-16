"""写入门禁单元测试 — backend/app/core/extraction/ingestion_gate.py.

验证三道门槛（prevention）：
1. 来源门槛：source_count < min_sources → 降级 preferred（防单点幻觉）
2. 信任度门槛：hallucination_score 过高 / confidence 过低 → 跳过不入图
3. required 上限：required 已达 cap → 新技能强制进 preferred（截断膨胀）
"""
from __future__ import annotations

from app.core.extraction.ingestion_gate import (
    DEFAULT_MAX_HALLUCINATION_SCORE,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_SOURCES_REQUIRED,
    DEFAULT_REQUIRED_CAP,
    apply_ingestion_gate,
)


def _skill(name: str, **overrides: object) -> dict:
    entry: dict[str, object] = {"name": name, "source_count": 3, "confidence": 0.9}
    entry.update(overrides)
    return entry


class TestSourceThreshold:
    def test_single_source_demoted_to_preferred(self) -> None:
        """source_count=1（单条 JD 出现）→ 从 required 降级 preferred."""
        result = apply_ingestion_gate(
            required_skills=[_skill("Python", source_count=1)],
            preferred_skills=[],
        )
        assert result["required"] == []
        assert len(result["preferred"]) == 1
        assert result["preferred"][0]["name"] == "Python"
        assert result["preferred"][0]["required"] is False
        assert result["preferred"][0]["demoted_reason"] == "low_source_count"
        assert result["stats"]["demoted_low_source"] == 1

    def test_multi_source_stays_required(self) -> None:
        result = apply_ingestion_gate(
            required_skills=[_skill("Python", source_count=3)],
            preferred_skills=[],
        )
        assert len(result["required"]) == 1
        assert result["required"][0]["name"] == "Python"


class TestTrustThreshold:
    def test_high_hallucination_dropped(self) -> None:
        result = apply_ingestion_gate(
            required_skills=[_skill("幻觉技能", hallucination_score=0.9)],
            preferred_skills=[],
        )
        assert result["required"] == []
        assert result["preferred"] == []
        assert len(result["dropped"]) == 1
        assert result["dropped"][0]["reason"] == "low_trust"

    def test_low_confidence_dropped(self) -> None:
        result = apply_ingestion_gate(
            required_skills=[_skill("低置信技能", confidence=0.1)],
            preferred_skills=[],
        )
        assert result["dropped"][0]["name"] == "低置信技能"

    def test_high_confidence_kept(self) -> None:
        result = apply_ingestion_gate(
            required_skills=[_skill("Python", confidence=0.9)],
            preferred_skills=[],
        )
        assert len(result["required"]) == 1


class TestRequiredCap:
    def test_cap_forces_new_skills_to_preferred(self) -> None:
        """required 已达 cap=2 → 第 3 个技能强制进 preferred."""
        skills = [
            _skill("A", source_count=3),
            _skill("B", source_count=3),
            _skill("C", source_count=3),
        ]
        result = apply_ingestion_gate(skills, [], required_cap=2)
        assert len(result["required"]) == 2
        assert len(result["preferred"]) == 1
        assert result["preferred"][0]["name"] == "C"
        assert result["preferred"][0]["demoted_reason"] == "required_cap"
        assert result["stats"]["capped"] == 1

    def test_cap_not_reached_all_kept(self) -> None:
        skills = [_skill("A"), _skill("B")]
        result = apply_ingestion_gate(skills, [], required_cap=DEFAULT_REQUIRED_CAP)
        assert len(result["required"]) == 2


class TestDefaults:
    def test_defaults_are_sane(self) -> None:
        assert DEFAULT_MIN_SOURCES_REQUIRED >= 2
        assert DEFAULT_MAX_HALLUCINATION_SCORE <= 0.7
        assert DEFAULT_MIN_CONFIDENCE >= 0.3
        assert DEFAULT_REQUIRED_CAP >= 5  # CII 基线 6 附近，防过度收缩


class TestMixedInput:
    def test_string_entries_supported(self) -> None:
        """向后兼容：str 技能条目（无 source_count/confidence）默认放行 required."""
        result = apply_ingestion_gate(["Python", "FastAPI"], [])
        assert len(result["required"]) == 2

    def test_empty_inputs(self) -> None:
        result = apply_ingestion_gate([], [])
        assert result["required"] == []
        assert result["preferred"] == []
        assert result["dropped"] == []
