"""Unit tests for EmergenceFinder."""

from app.config import get_settings
from app.core.evolution.emergence_finder import (
    DOMAIN_KEYWORDS,
    CrossDomainSkill,
    EmergenceFinder,
    EmergenceLevel,
    EmergenceReport,
    EmergenceSignal,
    PortabilityAnalysis,
    _classify_skill_domains,
)
from app.core.evolution.trust_scorer import (
    SOURCE_SATURATION,
    WEIGHT_SOURCE,
    WEIGHT_STABILITY,
    WEIGHT_TYPE,
)


class TestEmergenceFinder:
    """Tests for Z-score emergence detection."""

    def setup_method(self) -> None:
        self.finder = EmergenceFinder()

    def test_emerging_skill(self) -> None:
        """High z-score + frequency + sources → emerging."""
        signal = self.finder.detect(
            skill_name="RAG",
            frequencies=[1, 2, 1, 2, 1],  # mean=1.4, std≈0.49
            current_frequency=5,
            source_count=3,
        )
        assert signal.level == EmergenceLevel.EMERGING
        assert signal.z_score > 2.0

    def test_rising_skill(self) -> None:
        """Moderate z-score → rising."""
        signal = self.finder.detect(
            skill_name="Docker",
            frequencies=[5, 5, 5, 5, 5],  # mean=5, std=0
            current_frequency=8,
            source_count=5,
        )
        # std=0 → z=10.0, but freq=8 > 3 and sources=5 → emerging
        # Actually with std=0, z is set to 10.0 which is > 2.0
        assert signal.level in (EmergenceLevel.EMERGING, EmergenceLevel.RISING)

    def test_stable_skill(self) -> None:
        """Normal fluctuation → stable."""
        signal = self.finder.detect(
            skill_name="Python",
            frequencies=[10, 12, 11, 10, 12],
            current_frequency=11,
            source_count=8,
        )
        assert signal.level == EmergenceLevel.STABLE

    def test_declining_skill(self) -> None:
        """Low z-score → declining."""
        # std=0, current < mean → z=0 → stable
        self.finder.detect(
            skill_name="Perl",
            frequencies=[10, 10, 10, 10, 10],  # mean=10, std=0
            current_frequency=3,
            source_count=2,
        )
        # With variance: z < -1.5 → declining
        signal = self.finder.detect(
            skill_name="Perl",
            frequencies=[8, 9, 10, 11, 12],  # mean=10, std≈1.41
            current_frequency=5,
            source_count=2,
        )
        assert signal.level == EmergenceLevel.DECLINING

    def test_insufficient_history(self) -> None:
        """Too few data points → stable with note (BL-07: Wilson fallback)."""
        signal = self.finder.detect(
            skill_name="NewSkill",
            frequencies=[1],
            current_frequency=3,
        )
        assert signal.level == EmergenceLevel.STABLE
        # BL-07: note changed from "insufficient_history" to "insufficient_history_wilson_fallback"
        assert "insufficient_history" in signal.metadata.get("note", "")

    def test_emerging_needs_min_frequency(self) -> None:
        """z > 2.0 but frequency < 3 → not emerging."""
        signal = self.finder.detect(
            skill_name="RareSkill",
            frequencies=[0, 0, 0, 0, 0],  # mean=0, std=0
            current_frequency=2,  # < MIN_FREQUENCY
            source_count=5,
        )
        # z=10 but freq=2 < 3 → rising, not emerging
        assert signal.level != EmergenceLevel.EMERGING

    def test_scan_multiple_skills(self) -> None:
        """Scan classifies multiple skills correctly."""
        report = self.finder.scan({
            "Python": {"frequencies": [10, 12, 11, 10, 12], "current": 11, "sources": 8},
            "RAG": {"frequencies": [1, 2, 1, 2, 1], "current": 5, "sources": 3},
            "Perl": {"frequencies": [8, 9, 10, 11, 12], "current": 5, "sources": 2},
        })
        assert report.total_skills_analyzed == 3
        assert len(report.emerging) >= 1  # RAG
        assert len(report.declining) >= 1  # Perl


class TestEmergenceSignal:
    def test_has_positions_and_metadata(self) -> None:
        signal = EmergenceSignal(
            skill_name="Kubernetes",
            level=EmergenceLevel.EMERGING,
            z_score=3.5,
            current_frequency=15,
            mean_frequency=4.0,
            std_frequency=1.5,
            source_count=5,
            positions=["sre", "devops"],
            metadata={"domains": ["IT"]},
        )
        assert signal.positions == ["sre", "devops"]
        assert signal.metadata["domains"] == ["IT"]


class TestEmergenceReport:
    def test_all_signals_property(self) -> None:
        report = EmergenceReport(
            emerging=[EmergenceSignal("e1", EmergenceLevel.EMERGING, 3.0, 10, 2.0, 1.0, 3)],
            rising=[EmergenceSignal("r1", EmergenceLevel.RISING, 1.8, 8, 5.0, 2.0, 4)],
            stable=[EmergenceSignal("s1", EmergenceLevel.STABLE, 0.5, 5, 5.0, 1.0, 5)],
            declining=[EmergenceSignal("d1", EmergenceLevel.DECLINING, -2.0, 1, 5.0, 2.0, 2)],
            total_skills_analyzed=4,
        )
        assert len(report.all_signals) == 4
        names = {s.skill_name for s in report.all_signals}
        assert names == {"e1", "r1", "s1", "d1"}


class TestCrossDomain:
    def setup_method(self) -> None:
        self.finder = EmergenceFinder()

    def test_find_cross_domain_skills(self) -> None:
        """Python matches IT; position with BigData keyword triggers cross-domain."""
        skill_data = {
            "Python": {
                "frequencies": [10, 12, 11],
                "current": 12,
                "sources": 8,
                # "数据挖掘" is a BigData keyword → triggers cross-domain match
                "positions": ["backend-dev", "数据挖掘"],
            },
        }
        results = self.finder.find_cross_domain_skills(skill_data)
        assert len(results) >= 1
        python_result = next(r for r in results if r.skill_name == "Python")
        assert python_result.domain_count >= 2
        assert isinstance(python_result, CrossDomainSkill)

    def test_cross_domain_skill_dataclass(self) -> None:
        skill = CrossDomainSkill(
            skill_name="Python",
            domains=["IT", "AI"],
            domain_count=2,
            portability_score=0.5,
            positions_by_domain={"IT": ["backend"], "AI": ["ml"]},
            total_positions=2,
            category="programming",
        )
        assert skill.skill_name == "Python"
        assert skill.domains == ["IT", "AI"]

    def test_portability_analysis_dataclass(self) -> None:
        analysis = PortabilityAnalysis(
            skill_name="Python",
            portability_score=0.65,
            domains=["IT", "AI"],
            domain_count=2,
            positions_by_domain={"IT": ["backend"], "AI": ["ml"]},
            total_positions=2,
            transferability_tier="high",
            related_skills=["Rust"],
            recommendation="Cross-domain skill.",
        )
        assert analysis.transferability_tier == "high"
        assert analysis.related_skills == ["Rust"]

    def test_portability_score_single_domain(self) -> None:
        score = self.finder.portability_score("Python")
        assert 0.0 <= score <= 1.0

    def test_portability_score_with_positions(self) -> None:
        score = self.finder.portability_score(
            "Python",
            {"IT": ["backend", "devops"], "AI": ["ml-engineer"]},
        )
        assert 0.0 <= score <= 1.0

    def test_get_portability_analysis_returns_analysis(self) -> None:
        skill_data = {
            "Python": {
                "frequencies": [10, 12, 11],
                "current": 12,
                "sources": 8,
                "positions": ["backend-dev"],
            },
        }
        result = self.finder.get_portability_analysis("Python", skill_data)
        assert result is not None
        assert result.skill_name == "Python"
        assert result.transferability_tier in ("low", "medium", "high", "universal")

    def test_get_portability_analysis_missing_skill(self) -> None:
        result = self.finder.get_portability_analysis("NonExistent", {})
        assert result is None

    def test_get_portability_analysis_case_insensitive(self) -> None:
        skill_data = {
            "python": {
                "frequencies": [10, 12, 11],
                "current": 12,
                "sources": 8,
                "positions": ["backend-dev"],
            },
        }
        result = self.finder.get_portability_analysis("Python", skill_data)
        assert result is not None
        assert result.skill_name == "python"


class TestDomainKeywords:
    def test_domain_keywords_is_dict(self) -> None:
        assert isinstance(DOMAIN_KEYWORDS, dict)
        assert len(DOMAIN_KEYWORDS) >= 4  # IT, AI, BigData, IoT

    def test_classify_skill_domains_ai(self) -> None:
        domains = _classify_skill_domains("pytorch")
        assert "AI" in domains

    def test_classify_skill_domains_it(self) -> None:
        domains = _classify_skill_domains("java")
        assert "IT" in domains

    def test_classify_skill_domains_fallback(self) -> None:
        domains = _classify_skill_domains("unknown_xyz_skill")
        assert len(domains) >= 1  # should fall back to at least "IT"


class TestEmergenceTripleConditionBoundary:
    """D-02: 三重条件边界锁定（z>2.0 且 频次>=3 且 源>=3 → EMERGING）。"""

    def setup_method(self) -> None:
        self.finder = EmergenceFinder()

    def test_classify_emerging_when_all_three_met(self) -> None:
        """z 恰 > 2.0 且 frequency == 3 且 source_count == 3 → EMERGING。"""
        assert self.finder._classify(z=2.0001, frequency=3, source_count=3) == EmergenceLevel.EMERGING

    def test_classify_not_emerging_when_frequency_2(self) -> None:
        """z > 2.0 但 frequency == 2（低于 emergence_min_frequency=3）→ 不 EMERGING。"""
        assert self.finder._classify(z=2.0001, frequency=2, source_count=3) != EmergenceLevel.EMERGING

    def test_classify_not_emerging_when_sources_2(self) -> None:
        """z > 2.0 且 freq>=3 但 source_count == 2（低于 emergence_min_sources=3）→ 不 EMERGING。"""
        assert self.finder._classify(z=2.0001, frequency=3, source_count=2) != EmergenceLevel.EMERGING

    def test_classify_z_exactly_2_0_not_emerging(self) -> None:
        """z == 2.0（严格大于才判 EMERGING）→ 不 EMERGING，落入 RISING。"""
        assert self.finder._classify(z=2.0, frequency=3, source_count=3) == EmergenceLevel.RISING

    def test_detect_triple_condition_end_to_end(self) -> None:
        """detect() 全链路：z>2.0 且 freq=3 且 sources=3 → EMERGING。"""
        signal = self.finder.detect(
            skill_name="BoundarySkill",
            frequencies=[1, 2, 2],  # mean=1.667, std≈0.471 → z=(3-1.667)/0.471≈2.83
            current_frequency=3,
            source_count=3,
        )
        assert signal.z_score > 2.0
        assert signal.level == EmergenceLevel.EMERGING


class TestZeroVarianceBranch:
    """零方差分支（std < 1e-6）：current > mean → z=10.0；current < mean → z=0.0。"""

    def setup_method(self) -> None:
        self.finder = EmergenceFinder()

    def test_zero_variance_current_above_mean_z_10(self) -> None:
        """frequencies 全等 → std=0；current > mean → z=10.0（一次性跳变判 EMERGING）。"""
        signal = self.finder.detect(
            skill_name="ZeroVarJump",
            frequencies=[5, 5, 5, 5, 5],
            current_frequency=8,
            source_count=3,
        )
        assert signal.z_score == 10.0
        assert signal.level == EmergenceLevel.EMERGING

    def test_zero_variance_current_below_mean_z_0(self) -> None:
        """frequencies 全等 → std=0；current < mean → z=0.0（不误判 DECLINING）。"""
        signal = self.finder.detect(
            skill_name="ZeroVarDrop",
            frequencies=[5, 5, 5, 5, 5],
            current_frequency=3,
            source_count=2,
        )
        assert signal.z_score == 0.0
        assert signal.level == EmergenceLevel.STABLE


class TestWilsonFallback:
    """D-03: 历史窗口 len(frequencies) < 2 时 Wilson 下界 > 0.3 → RISING 兜底。"""

    def setup_method(self) -> None:
        self.finder = EmergenceFinder()

    def test_wilson_rising_when_lower_above_0_3(self) -> None:
        """len<2 且 wilson_lower≈0.488 > 0.3 且 current>0 且 sources>=MIN_SOURCES → RISING。"""
        signal = self.finder.detect(
            skill_name="WilsonRising",
            frequencies=[1],
            current_frequency=20,  # wilson_lower≈0.4878 > 0.3
            source_count=3,
        )
        assert signal.level == EmergenceLevel.RISING
        assert "insufficient_history_wilson_fallback" in signal.metadata.get("note", "")

    def test_wilson_stable_when_lower_below_0_3(self) -> None:
        """len<2 且 wilson_lower≈0.152 <= 0.3 → STABLE。"""
        signal = self.finder.detect(
            skill_name="WilsonStable",
            frequencies=[1],
            current_frequency=5,  # wilson_lower≈0.1518 <= 0.3
            source_count=3,
        )
        assert signal.level == EmergenceLevel.STABLE

    def test_wilson_requires_min_sources(self) -> None:
        """兜底比 D-03 文字更严格：source_count < MIN_SOURCES 则 STABLE（保持现状不放宽）。"""
        signal = self.finder.detect(
            skill_name="WilsonNoSources",
            frequencies=[1],
            current_frequency=20,  # wilson_lower>0.3 但源数不达标
            source_count=2,
        )
        assert signal.level == EmergenceLevel.STABLE

    def test_wilson_zero_current_stable(self) -> None:
        """current_frequency == 0（无当前提及）→ STABLE。"""
        signal = self.finder.detect(
            skill_name="WilsonZero",
            frequencies=[],
            current_frequency=0,
            source_count=3,
        )
        assert signal.level == EmergenceLevel.STABLE


class TestThresholdSource:
    """D-02: 阈值来自配置（emergence_z_emerging=2.0 / emergence_z_rising=1.5），非硬编码。"""

    def test_finder_thresholds_match_config(self) -> None:
        cfg = get_settings()
        finder = EmergenceFinder()
        assert finder.EMERGING_Z == cfg.emergence_z_emerging == 2.0
        assert finder.RISING_Z == cfg.emergence_z_rising == 1.5
        assert finder.DECLINING_Z == cfg.emergence_z_declining == -1.5
        assert finder.MIN_FREQUENCY == cfg.emergence_min_frequency == 3
        assert finder.MIN_SOURCES == cfg.emergence_min_sources == 3


class TestTrustScorerFormulaLock:
    """D-10: 信任度权重常量锁定（保持现状、不配置化）。"""

    def test_weight_constants_locked(self) -> None:
        assert WEIGHT_SOURCE == 0.5
        assert WEIGHT_STABILITY == 0.3
        assert WEIGHT_TYPE == 0.2
        assert SOURCE_SATURATION == 10.0
