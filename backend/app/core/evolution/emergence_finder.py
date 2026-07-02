"""Emergence Finder — Z-score based emerging skill detection.

Implements the emergence detection algorithm from design.md §4.5:
    z = (f(t) - μ) / σ
    if z > 2.0 AND f(t) > 3 AND independent sources >= 3: mark as emerging
    elif z > 1.5: mark as rising

Sprint 2.3 enhancements:
    - Cross-domain skill analysis (skills appearing in multiple domains)
    - Portability score (how transferable a skill is across domains)
    - Enhanced categorization with domain metadata
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger


class EmergenceLevel(StrEnum):
    """Classification of skill emergence."""

    EMERGING = "emerging"  # z > 2.0, strong signal
    RISING = "rising"  # z > 1.5, moderate signal
    STABLE = "stable"  # normal fluctuation
    DECLINING = "declining"  # z < -1.5


@dataclass
class EmergenceSignal:
    """A single emergence detection result."""

    skill_name: str
    level: EmergenceLevel
    z_score: float
    current_frequency: int
    mean_frequency: float
    std_frequency: float
    source_count: int
    positions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmergenceReport:
    """Complete emergence detection report."""

    emerging: list[EmergenceSignal]
    rising: list[EmergenceSignal]
    stable: list[EmergenceSignal]
    declining: list[EmergenceSignal]
    total_skills_analyzed: int
    window_description: str = ""

    @property
    def all_signals(self) -> list[EmergenceSignal]:
        return self.emerging + self.rising + self.stable + self.declining


# ─── Sprint 2.3: Cross-domain analysis data structures ───


@dataclass
class CrossDomainSkill:
    """A skill that appears across multiple domains."""

    skill_name: str
    domains: list[str] = field(default_factory=list)
    domain_count: int = 0
    portability_score: float = 0.0
    positions_by_domain: dict[str, list[str]] = field(default_factory=dict)
    total_positions: int = 0
    category: str = ""


@dataclass
class PortabilityAnalysis:
    """Detailed portability analysis for a single skill."""

    skill_name: str
    portability_score: float
    domains: list[str] = field(default_factory=list)
    domain_count: int = 0
    positions_by_domain: dict[str, list[str]] = field(default_factory=dict)
    total_positions: int = 0
    transferability_tier: str = "low"  # low / medium / high / universal
    related_skills: list[str] = field(default_factory=list)
    recommendation: str = ""


# Domain keywords used to classify skills into domains
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "IT": [
        "java", "python", "c++", "c#", ".net", "go", "rust", "javascript",
        "typescript", "sql", "git", "linux", "docker", "kubernetes", "微服务",
        "spring", "vue", "react", "angular", "前端", "后端", "全栈",
        "数据库", "redis", "mysql", "postgresql", "mongodb",
    ],
    "AI": [
        "机器学习", "深度学习", "tensorflow", "pytorch", "nlp", "cv",
        "自然语言处理", "计算机视觉", "大模型", "llm", "transformer",
        "bert", "gpt", "算法", "模型训练", "模型部署", "mlops",
        "人工智能", "ai", "强化学习", "生成式ai", "rag",
    ],
    "BigData": [
        "大数据", "hadoop", "spark", "flink", "hive", "数据仓库",
        "etl", "数据分析师", "数据挖掘", "数据治理", "实时计算",
        "kafka", "elasticsearch", "clickhouse", "数据湖", "数据中台",
        "离线计算", "数据建模",
    ],
    "IoT": [
        "物联网", "iot", "嵌入式", "边缘计算", "传感器", "mqtt",
        "工业互联网", "智能制造", "自动化", "机器人", "单片机",
        "arm", "rtos", "物联网平台", "设备管理",
    ],
}


def _classify_skill_domains(skill_name: str, positions: list[str] | None = None) -> list[str]:
    """Classify a skill into domains based on name and associated positions."""
    text = skill_name.lower()
    combined = f"{skill_name} {' '.join(positions or [])}".lower()

    matched_domains: list[str] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text or kw.lower() in combined:
                matched_domains.append(domain)
                break

    # Default to IT for general programming skills
    if not matched_domains:
        general_skills = {
            "python", "java", "sql", "git", "linux", "docker",
            "javascript", "typescript", "c++", "go", "rust",
        }
        if skill_name.lower() in general_skills:
            matched_domains.append("IT")

    return matched_domains or ["IT"]


class EmergenceFinder:
    """Detect emerging skills using Z-score analysis.

    Thresholds (from design.md §4.5):
        z > 2.0 AND f(t) > 3 AND sources >= 3 → emerging
        z > 1.5 → rising
        z < -1.5 → declining
        otherwise → stable
    """

    def __init__(self) -> None:
        from app.config import get_settings
        cfg = get_settings()
        self.EMERGING_Z = cfg.emergence_z_emerging
        self.RISING_Z = cfg.emergence_z_rising
        self.DECLINING_Z = cfg.emergence_z_declining
        self.MIN_FREQUENCY = cfg.emergence_min_frequency
        self.MIN_SOURCES = cfg.emergence_min_sources

    def detect(
        self,
        skill_name: str,
        frequencies: list[int],
        current_frequency: int,
        source_count: int = 1,
        positions: list[str] | None = None,
    ) -> EmergenceSignal:
        """Detect emergence for a single skill.

        Args:
            skill_name: Name of the skill.
            frequencies: Historical frequency values (excluding current).
            current_frequency: Current window frequency.
            source_count: Number of independent sources.
            positions: Positions mentioning this skill.

        Returns:
            EmergenceSignal with classification.
        """
        # Compute statistics from historical data
        if len(frequencies) < 2:
            # Insufficient history — can't compute meaningful z-score
            return EmergenceSignal(
                skill_name=skill_name,
                level=EmergenceLevel.STABLE,
                z_score=0.0,
                current_frequency=current_frequency,
                mean_frequency=float(current_frequency),
                std_frequency=0.0,
                source_count=source_count,
                positions=positions or [],
                metadata={"note": "insufficient_history", "history_len": len(frequencies)},
            )

        mean = sum(frequencies) / len(frequencies)
        variance = sum((f - mean) ** 2 for f in frequencies) / len(frequencies)
        std = math.sqrt(variance)

        # Compute z-score (handle zero std)
        if std < 1e-6:
            # No variance — if current > mean, it's a jump; otherwise stable
            z = 10.0 if current_frequency > mean else 0.0
        else:
            z = (current_frequency - mean) / std

        # Classify
        level = self._classify(z, current_frequency, source_count)

        logger.debug(
            "Emergence '{}': z={:.2f} freq={} mean={:.1f} std={:.2f} level={}",
            skill_name, z, current_frequency, mean, std, level.value,
        )

        # Enrich with domain metadata
        domains = _classify_skill_domains(skill_name, positions)
        metadata: dict[str, Any] = {"domains": domains}

        return EmergenceSignal(
            skill_name=skill_name,
            level=level,
            z_score=round(z, 3),
            current_frequency=current_frequency,
            mean_frequency=round(mean, 2),
            std_frequency=round(std, 2),
            source_count=source_count,
            positions=positions or [],
            metadata=metadata,
        )

    def _classify(
        self,
        z: float,
        frequency: int,
        source_count: int,
    ) -> EmergenceLevel:
        """Classify based on z-score and supporting criteria."""
        if z > self.EMERGING_Z and frequency >= self.MIN_FREQUENCY and source_count >= self.MIN_SOURCES:
            return EmergenceLevel.EMERGING
        if z > self.RISING_Z:
            return EmergenceLevel.RISING
        if z < self.DECLINING_Z:
            return EmergenceLevel.DECLINING
        return EmergenceLevel.STABLE

    def scan(
        self,
        skill_data: dict[str, dict[str, Any]],
    ) -> EmergenceReport:
        """Scan all skills for emergence signals.

        Args:
            skill_data: Dict of skill_name → {
                "frequencies": list[int],  # historical frequencies
                "current": int,            # current window frequency
                "sources": int,            # source count
                "positions": list[str],    # positions mentioning this skill
            }

        Returns:
            EmergenceReport with all signals classified.
        """
        emerging: list[EmergenceSignal] = []
        rising: list[EmergenceSignal] = []
        stable: list[EmergenceSignal] = []
        declining: list[EmergenceSignal] = []

        for skill_name, data in skill_data.items():
            signal = self.detect(
                skill_name=skill_name,
                frequencies=data.get("frequencies", []),
                current_frequency=data.get("current", 0),
                source_count=data.get("sources", 1),
                positions=data.get("positions", []),
            )

            if signal.level == EmergenceLevel.EMERGING:
                emerging.append(signal)
            elif signal.level == EmergenceLevel.RISING:
                rising.append(signal)
            elif signal.level == EmergenceLevel.DECLINING:
                declining.append(signal)
            else:
                stable.append(signal)

        # Sort by z-score descending
        emerging.sort(key=lambda s: s.z_score, reverse=True)
        rising.sort(key=lambda s: s.z_score, reverse=True)
        declining.sort(key=lambda s: s.z_score)

        logger.info(
            "Emergence scan: {} emerging, {} rising, {} stable, {} declining (total: {})",
            len(emerging), len(rising), len(stable), len(declining),
            len(skill_data),
        )

        return EmergenceReport(
            emerging=emerging,
            rising=rising,
            stable=stable,
            declining=declining,
            total_skills_analyzed=len(skill_data),
        )

    # ─── Sprint 2.3: Cross-domain skill analysis ───

    def find_cross_domain_skills(
        self,
        skill_data: dict[str, dict[str, Any]],
    ) -> list[CrossDomainSkill]:
        """Identify skills that appear across multiple domains.

        Uses domain classification on skill names and associated positions
        to find skills that bridge domains (e.g., Python in IT/AI/BigData).

        Args:
            skill_data: Dict of skill_name → {
                "frequencies": list[int],
                "current": int,
                "sources": int,
                "positions": list[str],
            }

        Returns:
            List of CrossDomainSkill, sorted by domain_count descending.
        """
        # Aggregate skills by domain
        domain_skill_positions: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for skill_name, data in skill_data.items():
            positions = data.get("positions", [])
            domains = _classify_skill_domains(skill_name, positions)
            for domain in domains:
                domain_skill_positions[domain][skill_name].extend(positions)

        # Find skills appearing in multiple domains
        skill_domain_map: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for domain, skills_positions in domain_skill_positions.items():
            for skill_name, positions in skills_positions.items():
                skill_domain_map[skill_name][domain].extend(positions)

        results: list[CrossDomainSkill] = []
        for skill_name, domains_positions in skill_domain_map.items():
            if len(domains_positions) < 2:
                continue  # Skip single-domain skills

            domains = sorted(domains_positions.keys())
            # Deduplicate positions per domain
            positions_by_domain: dict[str, list[str]] = {}
            total_positions = 0
            for domain in domains:
                unique_positions = list(dict.fromkeys(domains_positions[domain]))
                positions_by_domain[domain] = unique_positions
                total_positions += len(unique_positions)

            # Compute portability
            portability = self.portability_score(skill_name, domains_positions)

            results.append(CrossDomainSkill(
                skill_name=skill_name,
                domains=domains,
                domain_count=len(domains),
                portability_score=portability,
                positions_by_domain=positions_by_domain,
                total_positions=total_positions,
                category=skill_data.get(skill_name, {}).get("category", ""),
            ))

        # Sort by portability score then domain count
        results.sort(key=lambda s: (s.portability_score, s.domain_count), reverse=True)

        logger.info(
            "Cross-domain analysis: {} skills found across multiple domains (total: {})",
            len(results), len(skill_data),
        )
        return results

    def portability_score(
        self,
        skill_name: str,
        domains_positions: dict[str, list[str]] | None = None,
    ) -> float:
        """Compute how transferable a skill is across domains (0.0 – 1.0).

        Scoring factors:
            - Domain coverage: more domains → higher score
            - Position diversity: more unique positions across domains → higher score
            - Domain balance: even distribution → higher than skewed

        Args:
            skill_name: Name of the skill.
            domains_positions: Optional pre-computed domain → positions mapping.
                If None, domains are inferred from skill_name alone.

        Returns:
            Float between 0.0 (single-domain only) and 1.0 (universal).
        """
        if domains_positions is None:
            domains = _classify_skill_domains(skill_name)
            domain_count = len(domains)
        else:
            domain_count = len(domains_positions)

        # Factor 1: Domain coverage (0.0 – 0.5)
        # 1 domain → 0.0, 2 domains → 0.25, 3 domains → 0.4, 4+ domains → 0.5
        total_known_domains = len(DOMAIN_KEYWORDS)
        coverage = min(1.0, domain_count / total_known_domains)
        domain_factor = coverage * 0.5

        # Factor 2: Position diversity (0.0 – 0.3)
        if domains_positions:
            unique_positions: set[str] = set()
            for positions in domains_positions.values():
                unique_positions.update(positions)
            # Scale: 1 position → ~0.05, 5+ positions → 0.3
            position_factor = min(0.3, len(unique_positions) * 0.06)
        else:
            position_factor = 0.0

        # Factor 3: Domain balance (0.0 – 0.2)
        # Penalize if skill is only marginally present in most domains
        if domains_positions and domain_count > 1:
            total_positions = sum(len(v) for v in domains_positions.values())
            if total_positions > 0:
                # Shannon entropy normalized
                entropy = 0.0
                for positions in domains_positions.values():
                    p = len(positions) / total_positions
                    if p > 0:
                        entropy -= p * math.log2(p)
                max_entropy = math.log2(domain_count)
                balance = entropy / max_entropy if max_entropy > 0 else 0.0
                balance_factor = balance * 0.2
            else:
                balance_factor = 0.0
        else:
            balance_factor = 0.0

        score = round(min(1.0, domain_factor + position_factor + balance_factor), 3)
        return score

    def get_portability_analysis(
        self,
        skill_name: str,
        skill_data: dict[str, dict[str, Any]],
    ) -> PortabilityAnalysis | None:
        """Get detailed portability analysis for a specific skill.

        Args:
            skill_name: Name of the skill to analyze.
            skill_data: Full skill data dict (same format as scan()).

        Returns:
            PortabilityAnalysis or None if skill not found in data.
        """
        # Find the skill in data (case-insensitive match)
        actual_name = skill_name
        data = skill_data.get(skill_name)
        if data is None:
            for name in skill_data:
                if name.lower() == skill_name.lower():
                    actual_name = name
                    data = skill_data[name]
                    break
        if data is None:
            return None

        positions = data.get("positions", [])
        domains = _classify_skill_domains(actual_name, positions)

        # Build positions by domain
        domains_positions: dict[str, list[str]] = {}
        for domain in domains:
            domains_positions[domain] = list(positions)

        portability = self.portability_score(actual_name, domains_positions)

        # Determine tier
        if portability >= 0.7:
            tier = "universal"
            recommendation = f"{actual_name} is a universal skill applicable across all tracked domains. High career flexibility value."
        elif portability >= 0.45:
            tier = "high"
            recommendation = (
                f"{actual_name} has high portability across {len(domains)} domains ({', '.join(domains)}). "
                "Strong foundation for cross-domain transitions."
            )
        elif portability >= 0.25:
            tier = "medium"
            recommendation = (
                f"{actual_name} is moderately portable across {len(domains)} domain(s). "
                "Consider deepening expertise to increase transferability."
            )
        else:
            tier = "low"
            recommendation = (
                f"{actual_name} is primarily domain-specific ({', '.join(domains)}). "
                "Consider pairing with cross-domain skills for career flexibility."
            )

        # Find related cross-domain skills
        cross_domain = self.find_cross_domain_skills(skill_data)
        related: list[str] = []
        for cds in cross_domain:
            if cds.skill_name != actual_name and set(domains) & set(cds.domains):
                related.append(cds.skill_name)
                if len(related) >= 5:
                    break

        return PortabilityAnalysis(
            skill_name=actual_name,
            portability_score=portability,
            domains=sorted(domains),
            domain_count=len(domains),
            positions_by_domain=domains_positions,
            total_positions=len(positions),
            transferability_tier=tier,
            related_skills=related,
            recommendation=recommendation,
        )
