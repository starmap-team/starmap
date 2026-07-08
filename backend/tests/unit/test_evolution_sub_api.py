"""Unit tests for evolution sub-module API endpoints.

Covers:
- evolution_career_path.py — GET /evolution/career-path/{position}
- evolution_emerging_alerts.py — GET /evolution/emerging-alerts
- evolution_industry_report.py — GET /evolution/industry-report

Uses FastAPI TestClient + dependency_overrides, same pattern as test_admin_endpoints.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.evolution.emergence_finder import EmergenceLevel, EmergenceReport, EmergenceSignal
from app.dependencies import get_db_session
from app.main import app

# ── Fake DB primitives (same pattern as admin tests) ──


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        v = self.value
        if isinstance(v, (list, tuple)) and len(v) == 1:
            return v[0]
        return v

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def fetchall(self):
        return self.value if isinstance(self.value, list) else [self.value]


class FakeEvolutionPath:
    """Mimics an EvolutionPath ORM instance."""

    def __init__(
        self,
        source_position="后端工程师",
        target_position="全栈工程师",
        similarity=0.75,
        evidence_count=5,
        skill_overlap=None,
        key_gaps=None,
    ):
        self.source_position = source_position
        self.target_position = target_position
        self.similarity = similarity
        self.evidence_count = evidence_count
        self.skill_overlap = skill_overlap or ["Python", "SQL"]
        self.key_gaps = key_gaps or ["React"]


class FakeAsyncSession:
    """Minimal async session that returns pre-configured results per execute call."""

    def __init__(self, results=None):
        self._results = list(results or [])
        self._idx = 0

    async def execute(self, _stmt):
        if self._idx < len(self._results):
            r = self._results[self._idx]
            self._idx += 1
            return r
        return FakeResult([])


def _make_db_override(session: FakeAsyncSession):
    async def _override():
        yield session
    return _override


# ── Fixtures ──


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db_override():
    """Override get_db_session. Returns a setter function."""
    def _set(session: FakeAsyncSession | None):
        if session is None:
            app.dependency_overrides.pop(get_db_session, None)
        else:
            app.dependency_overrides[get_db_session] = _make_db_override(session)

    yield _set
    app.dependency_overrides.pop(get_db_session, None)


# ── Helpers ──

BASE = "/api/v1/evolution"


def _make_emergence_report(
    emerging=None, rising=None, declining=None, stable=None,
) -> EmergenceReport:
    """Build an EmergenceReport with fake signals."""
    return EmergenceReport(
        emerging=emerging or [],
        rising=rising or [],
        declining=declining or [],
        stable=stable or [],
        total_skills_analyzed=10,
    )


def _make_signal(
    skill_name="LangChain",
    level=EmergenceLevel.EMERGING,
    z_score=2.5,
    current_frequency=10,
    mean_frequency=3.0,
    source_count=5,
    positions=None,
    metadata=None,
) -> EmergenceSignal:
    return EmergenceSignal(
        skill_name=skill_name,
        level=level,
        z_score=z_score,
        current_frequency=current_frequency,
        mean_frequency=mean_frequency,
        std_frequency=1.0,
        source_count=source_count,
        positions=positions or ["AI工程师"],
        metadata=metadata or {"domains": ["AI"]},
    )


# ══════════════════════════════════════════════════════════════
# GET /evolution/career-path/{position}
# ══════════════════════════════════════════════════════════════


class TestCareerPath:
    """GET /api/v1/evolution/career-path/{position}"""

    def test_career_path_returns_200_with_data(self, client, db_override):
        path1 = FakeEvolutionPath(
            source_position="后端工程师",
            target_position="全栈工程师",
            similarity=0.8,
            evidence_count=5,
            skill_overlap=["Python", "SQL"],
            key_gaps=["React"],
        )
        # depth=1: one query; depth>=2: one more per top-5 first-hop
        # Use depth=1 to keep it simple
        session = FakeAsyncSession([FakeResult([path1])])
        db_override(session)
        resp = client.get(f"{BASE}/career-path/后端工程师", params={"depth": 1})
        assert resp.status_code == 200
        body = resp.json()
        assert body["origin"] == "后端工程师"
        assert body["total_paths"] >= 1
        assert body["nodes"][0]["position"] == "全栈工程师"
        assert body["nodes"][0]["similarity"] == 0.8
        assert body["nodes"][0]["direction"] == "forward"

    def test_career_path_senior_direction(self, client, db_override):
        path1 = FakeEvolutionPath(
            source_position="后端工程师",
            target_position="高级后端工程师",
            similarity=0.9,
        )
        session = FakeAsyncSession([FakeResult([path1])])
        db_override(session)
        resp = client.get(f"{BASE}/career-path/后端工程师", params={"depth": 1})
        assert resp.status_code == 200
        body = resp.json()
        # "高级" is in SENIOR_KEYWORDS → direction should be "up"
        assert body["nodes"][0]["direction"] == "up"

    def test_career_path_lateral_direction(self, client, db_override):
        # source_position != position → lateral
        path1 = FakeEvolutionPath(
            source_position="前端工程师",
            target_position="后端工程师",
            similarity=0.5,
        )
        session = FakeAsyncSession([FakeResult([path1])])
        db_override(session)
        resp = client.get(f"{BASE}/career-path/后端工程师", params={"depth": 1})
        assert resp.status_code == 200
        body = resp.json()
        # position is target, so we go from target back to source → lateral
        assert body["nodes"][0]["position"] == "前端工程师"
        assert body["nodes"][0]["direction"] == "lateral"

    def test_career_path_empty_result(self, client, db_override):
        session = FakeAsyncSession([FakeResult([])])
        db_override(session)
        resp = client.get(f"{BASE}/career-path/未知岗位", params={"depth": 1})
        assert resp.status_code == 200
        body = resp.json()
        assert body["origin"] == "未知岗位"
        assert body["total_paths"] == 0
        assert body["nodes"] == []

    def test_career_path_depth_2_multi_hop(self, client, db_override):
        # First hop: 后端工程师 → 全栈工程师
        path1 = FakeEvolutionPath(
            source_position="后端工程师",
            target_position="全栈工程师",
            similarity=0.8,
        )
        # Second hop: 全栈工程师 → 架构师
        path2 = FakeEvolutionPath(
            source_position="全栈工程师",
            target_position="架构师",
            similarity=0.6,
        )
        session = FakeAsyncSession([FakeResult([path1]), FakeResult([path2])])
        db_override(session)
        resp = client.get(f"{BASE}/career-path/后端工程师", params={"depth": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_paths"] >= 1
        # First hop node should be present
        positions = [n["position"] for n in body["nodes"]]
        assert "全栈工程师" in positions

    def test_career_path_db_error(self, client, db_override):
        session = FakeAsyncSession()
        session.execute = AsyncMock(side_effect=Exception("db down"))
        db_override(session)
        resp = client.get(f"{BASE}/career-path/后端工程师", params={"depth": 1})
        # Unhandled DB error → 500
        assert resp.status_code == 500

    def test_career_path_dedup_positions(self, client, db_override):
        # Two paths pointing to same target → deduped
        path1 = FakeEvolutionPath(
            source_position="后端工程师",
            target_position="全栈工程师",
            similarity=0.8,
        )
        path2 = FakeEvolutionPath(
            source_position="后端工程师",
            target_position="全栈工程师",
            similarity=0.6,
        )
        session = FakeAsyncSession([FakeResult([path1, path2])])
        db_override(session)
        resp = client.get(f"{BASE}/career-path/后端工程师", params={"depth": 1})
        assert resp.status_code == 200
        body = resp.json()
        # Same target deduped
        positions = [n["position"] for n in body["nodes"]]
        assert positions.count("全栈工程师") == 1


# ══════════════════════════════════════════════════════════════
# GET /evolution/emerging-alerts
# ══════════════════════════════════════════════════════════════


class TestEmergingAlerts:
    """GET /api/v1/evolution/emerging-alerts"""

    def test_emerging_alerts_returns_200_with_data(self, client, db_override):
        skill_data = {
            "LangChain": {
                "frequencies": [2, 3, 5],
                "current": 10,
                "sources": 5,
                "positions": ["AI工程师"],
                "category": "AI",
            },
        }
        report = _make_emergence_report(
            emerging=[_make_signal(skill_name="LangChain", level=EmergenceLevel.EMERGING, z_score=2.5)],
        )
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_finder.portability_score.return_value = 0.8
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/emerging-alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["alerts"][0]["skill_name"] == "LangChain"
        assert body["alerts"][0]["level"] == "emerging"
        assert body["alerts"][0]["portability_score"] == 0.8

    def test_emerging_alerts_empty_timeseries(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch("app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data", new_callable=AsyncMock, return_value={}):
            resp = client.get(f"{BASE}/emerging-alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["alerts"] == []
        assert "暂无时序数据" in body["summary"]

    def test_emerging_alerts_level_filter(self, client, db_override):
        skill_data = {"A": {"frequencies": [1], "current": 5, "sources": 3, "positions": [], "category": ""}}
        report = _make_emergence_report(
            emerging=[_make_signal(skill_name="A", level=EmergenceLevel.EMERGING, z_score=2.5)],
            rising=[_make_signal(skill_name="B", level=EmergenceLevel.RISING, z_score=1.8)],
        )
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_finder.portability_score.return_value = 0.5
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/emerging-alerts", params={"level": "emerging"})
        assert resp.status_code == 200
        body = resp.json()
        # Only emerging should pass the filter
        assert body["total"] == 1
        assert body["alerts"][0]["skill_name"] == "A"

    def test_emerging_alerts_min_z_score_filter(self, client, db_override):
        skill_data = {"A": {"frequencies": [1], "current": 5, "sources": 3, "positions": [], "category": ""}}
        report = _make_emergence_report(
            emerging=[
                _make_signal(skill_name="A", level=EmergenceLevel.EMERGING, z_score=2.5),
                _make_signal(skill_name="B", level=EmergenceLevel.EMERGING, z_score=1.0),
            ],
        )
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_finder.portability_score.return_value = 0.5
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/emerging-alerts", params={"min_z_score": 2.0})
        assert resp.status_code == 200
        body = resp.json()
        # Only z_score >= 2.0 should pass
        assert body["total"] == 1
        assert body["alerts"][0]["skill_name"] == "A"

    def test_emerging_alerts_domain_filter(self, client, db_override):
        skill_data = {
            "A": {"frequencies": [1], "current": 5, "sources": 3, "positions": [], "category": ""},
        }
        report = _make_emergence_report(
            emerging=[
                _make_signal(skill_name="A", metadata={"domains": ["AI"]}),
                _make_signal(skill_name="B", metadata={"domains": ["IoT"]}),
            ],
        )
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_finder.portability_score.return_value = 0.5
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/emerging-alerts", params={"domain": "AI"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["alerts"][0]["skill_name"] == "A"

    def test_emerging_alerts_db_error(self, client, db_override):
        session = FakeAsyncSession()
        session.execute = AsyncMock(side_effect=Exception("db down"))
        db_override(session)
        # load_skill_timeseries_data calls session.execute, so patch it to raise
        with patch(
            "app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data",
            new_callable=AsyncMock,
            side_effect=Exception("db down"),
        ):
            resp = client.get(f"{BASE}/emerging-alerts")
        assert resp.status_code == 500

    def test_emerging_alerts_summary_counts(self, client, db_override):
        skill_data = {"A": {"frequencies": [1], "current": 5, "sources": 3, "positions": [], "category": ""}}
        report = _make_emergence_report(
            emerging=[_make_signal(skill_name="A", level=EmergenceLevel.EMERGING, z_score=2.5)],
            rising=[_make_signal(skill_name="B", level=EmergenceLevel.RISING, z_score=1.8)],
            declining=[_make_signal(skill_name="C", level=EmergenceLevel.DECLINING, z_score=-2.0)],
        )
        session = FakeAsyncSession()
        db_override(session)
        with (
            patch("app.api.v1.evolution_emerging_alerts.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_finder.portability_score.return_value = 0.5
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/emerging-alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert "1 新兴" in body["summary"]
        assert "1 上升" in body["summary"]
        assert "1 下降" in body["summary"]


# ══════════════════════════════════════════════════════════════
# GET /evolution/industry-report
# ══════════════════════════════════════════════════════════════


class TestIndustryReport:
    """GET /api/v1/evolution/industry-report"""

    def test_industry_report_with_timeseries_data(self, client, db_override):
        skill_data = {
            "Rust": {
                "frequencies": [2, 5, 8],
                "current": 12,
                "sources": 6,
                "positions": ["系统工程师"],
            },
        }
        report = _make_emergence_report(
            rising=[_make_signal(skill_name="Rust", level=EmergenceLevel.RISING, z_score=1.8)],
            declining=[_make_signal(skill_name="jQuery", level=EmergenceLevel.DECLINING, z_score=-2.0)],
            stable=[_make_signal(skill_name="Python", level=EmergenceLevel.STABLE, z_score=0.3)],
        )
        # top_positions query
        top_pos_result = FakeResult([("后端工程师", 15)])
        session = FakeAsyncSession([top_pos_result])
        db_override(session)
        with (
            patch("app.api.v1.evolution_industry_report.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/industry-report")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_skills"] == 3
        assert len(body["rising_skills"]) >= 1
        assert body["rising_skills"][0]["skill_name"] == "Rust"
        assert len(body["declining_skills"]) >= 1
        assert body["declining_skills"][0]["skill_name"] == "jQuery"

    def test_industry_report_empty_timeseries_fallback(self, client, db_override):
        # No timeseries → fallback to SkillRecord query
        # First query: SkillRecord fallback
        fallback_rows = [("Python", 8, "hard_skill")]
        # Second query per skill: positions
        pos_rows = [("后端工程师",)]
        # Third query: top_positions
        top_pos_rows = [("后端工程师", 10)]
        session = FakeAsyncSession([
            FakeResult(fallback_rows),  # SkillRecord query
            FakeResult(pos_rows),       # positions for Python
            FakeResult(top_pos_rows),   # top_positions
        ])
        db_override(session)
        with patch("app.api.v1.evolution_industry_report.load_skill_timeseries_data", new_callable=AsyncMock, return_value={}):
            resp = client.get(f"{BASE}/industry-report")
        assert resp.status_code == 200
        body = resp.json()
        # source_count=8 > 5 → "rising"
        assert body["total_skills"] >= 1
        assert any(s["skill_name"] == "Python" for s in body["rising_skills"])

    def test_industry_report_empty_all(self, client, db_override):
        # No timeseries, no fallback records, no top positions
        session = FakeAsyncSession([
            FakeResult([]),   # SkillRecord fallback
            FakeResult([]),   # top_positions
        ])
        db_override(session)
        with patch("app.api.v1.evolution_industry_report.load_skill_timeseries_data", new_callable=AsyncMock, return_value={}):
            resp = client.get(f"{BASE}/industry-report")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_skills"] == 0
        assert body["rising_skills"] == []
        assert body["declining_skills"] == []
        assert body["stable_skills"] == []

    def test_industry_report_category_filter(self, client, db_override):
        skill_data = {
            "Rust": {"frequencies": [2], "current": 5, "sources": 3, "positions": []},
        }
        report = _make_emergence_report(
            rising=[_make_signal(skill_name="Rust", level=EmergenceLevel.RISING, z_score=1.8)],
        )
        session = FakeAsyncSession([FakeResult([])])  # top_positions
        db_override(session)
        with (
            patch("app.api.v1.evolution_industry_report.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data) as mock_load,
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/industry-report", params={"category": "AI"})
        assert resp.status_code == 200
        # Verify category was passed to load_skill_timeseries_data
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args
        assert call_kwargs.kwargs.get("category") == "AI" or (len(call_kwargs.args) > 1 and "AI" in str(call_kwargs))

    def test_industry_report_db_error(self, client, db_override):
        session = FakeAsyncSession()
        db_override(session)
        with patch(
            "app.api.v1.evolution_industry_report.load_skill_timeseries_data",
            new_callable=AsyncMock,
            side_effect=Exception("db down"),
        ):
            resp = client.get(f"{BASE}/industry-report")
        assert resp.status_code == 500

    def test_industry_report_summary(self, client, db_override):
        skill_data = {"A": {"frequencies": [1], "current": 5, "sources": 3, "positions": []}}
        report = _make_emergence_report(
            rising=[_make_signal(skill_name="A", level=EmergenceLevel.RISING, z_score=1.8)],
        )
        session = FakeAsyncSession([FakeResult([])])  # top_positions
        db_override(session)
        with (
            patch("app.api.v1.evolution_industry_report.load_skill_timeseries_data", new_callable=AsyncMock, return_value=skill_data),
            patch("app.core.evolution.emergence_finder.EmergenceFinder") as mock_cls,
        ):
            mock_finder = MagicMock()
            mock_finder.scan.return_value = report
            mock_cls.return_value = mock_finder
            resp = client.get(f"{BASE}/industry-report")
        assert resp.status_code == 200
        body = resp.json()
        assert "1 个技能呈上升趋势" in body["summary"]
        assert "共跟踪 1 个技能" in body["summary"]
