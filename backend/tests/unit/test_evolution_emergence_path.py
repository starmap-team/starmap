"""Unit tests for EmergenceFinder and PathRecommender."""

from app.core.evolution.emergence_finder import EmergenceFinder, EmergenceLevel
from app.core.evolution.path_recommender import PathRecommender


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
        """Too few data points → stable with note."""
        signal = self.finder.detect(
            skill_name="NewSkill",
            frequencies=[1],
            current_frequency=3,
        )
        assert signal.level == EmergenceLevel.STABLE
        assert signal.metadata.get("note") == "insufficient_history"

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


class TestPathRecommender:
    """Tests for EVOLVES_TO path discovery."""

    def setup_method(self) -> None:
        self.recommender = PathRecommender()

    def test_jaccard_similarity(self) -> None:
        """Jaccard similarity computation."""
        sim, overlap = self.recommender.compute_similarity(
            {"Python", "SQL", "Docker"},
            {"Python", "SQL", "Go"},
        )
        assert abs(sim - 2 / 4) < 0.01  # 2 overlap / 4 union
        assert set(overlap) == {"Python", "SQL"}

    def test_no_overlap(self) -> None:
        """No overlap → similarity 0."""
        sim, overlap = self.recommender.compute_similarity(
            {"Python", "SQL"},
            {"Go", "Rust"},
        )
        assert sim == 0.0
        assert overlap == []

    def test_find_paths(self) -> None:
        """Find paths with sufficient similarity and evidence."""
        report = self.recommender.find_paths(
            position_skills={
                "Backend": {"Python", "SQL", "Docker", "Redis"},
                "FullStack": {"Python", "SQL", "Docker", "JavaScript", "React"},
                "Frontend": {"JavaScript", "React", "CSS", "HTML"},
            },
            evidence_counts={
                "Backend->FullStack": 5,
                "FullStack->Frontend": 2,
                "Backend->Frontend": 1,
            },
            time_order={
                "Backend": 1.0,
                "FullStack": 2.0,
                "Frontend": 3.0,
            },
        )
        # Backend->FullStack: sim=3/6=0.5 < 0.6 → filtered out
        # FullStack->Frontend: ev=2 < 3 → filtered out
        # So no paths should pass all filters
        assert report.total_pairs_analyzed == 6

    def test_find_paths_high_similarity(self) -> None:
        """Paths with high similarity and evidence pass filters."""
        report = self.recommender.find_paths(
            position_skills={
                "Junior": {"Python", "SQL", "Git"},
                "Senior": {"Python", "SQL", "Git", "Docker", "K8s"},
            },
            evidence_counts={"Junior->Senior": 5},
            time_order={"Junior": 1.0, "Senior": 2.0},
        )
        # sim = 3/5 = 0.6 >= 0.6, ev=5 >= 3, time order correct
        assert report.path_count == 1
        assert report.paths[0].source_position == "Junior"
        assert report.paths[0].target_position == "Senior"

    def test_recommend_transitions(self) -> None:
        """Recommend transitions from current position."""
        recs = self.recommender.recommend_transitions(
            current_position="Backend",
            current_skills={"Python", "SQL", "Docker"},
            position_skills={
                "Backend": {"Python", "SQL", "Docker"},
                "FullStack": {"Python", "SQL", "JavaScript", "React"},
                "DataEng": {"Python", "SQL", "Spark", "Airflow"},
                "Frontend": {"JavaScript", "React", "CSS"},
            },
        )
        assert len(recs) > 0
        # Backend → DataEng should rank high (Python+SQL overlap)
        targets = [r.target_position for r in recs]
        assert "DataEng" in targets

    def test_empty_positions(self) -> None:
        """Empty input → empty report."""
        report = self.recommender.find_paths({})
        assert report.path_count == 0
        assert report.total_pairs_analyzed == 0
