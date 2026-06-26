"""Stage 4 API contract tests."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from docx import Document

from app.dependencies import get_db_session, get_neo4j_driver
from app.main import app


class FakeResult:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value


class FakeAsyncSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _stmt):
        return FakeResult(self.results.pop(0))


@pytest.fixture(autouse=True)
def no_neo4j_driver():
    app.dependency_overrides[get_neo4j_driver] = lambda: None
    yield
    app.dependency_overrides.pop(get_neo4j_driver, None)


def test_match_position_returns_enriched_contract(client):
    payload = {
        "target_position": "数据分析师",
        "person_skills": [
            {"name": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"name": "Excel", "category": "tool", "proficiency": "精通"},
            {"name": "SQL", "category": "hard_skill", "proficiency": "了解"},
        ],
    }

    resp = client.post("/api/v1/match/position", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "match_id",
        "target_position",
        "match_score",
        "matched_skills",
        "gap_skills",
        "recommendations",
        "missing_required",
        "missing_bonus",
        "skill_gap_detail",
        "overall_assessment",
        "estimated_learning_time",
    }
    assert body["target_position"] == "数据分析师"
    assert isinstance(body["match_score"], float)
    assert body["skill_gap_detail"]

    result_id = body["match_id"]
    detail_resp = client.get(f"/api/v1/match/result/{result_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["match_id"] == result_id


def test_match_diagnose_alias_matches_position(client):
    payload = {
        "target_position": "后端开发工程师",
        "person_skills": [{"name": "Python", "proficiency": "精通"}],
    }

    resp = client.post("/api/v1/match/diagnose", json=payload)

    assert resp.status_code == 200
    assert resp.json()["target_position"] == "后端开发工程师"


def test_match_result_not_found(client):
    resp = client.get("/api/v1/match/result/not-exists")
    assert resp.status_code == 404


def test_resume_upload_endpoint_accepts_docx(client):
    pipeline_result = {
        "success": True,
        "data": {
            "position_name": "后端开发工程师",
            "required_skills": [{"name": "Python", "level": "advanced"}],
            "preferred_skills": [],
            "experience_required": 3,
            "education_required": "本科",
            "responsibilities": [],
        },
        "validation": {"is_valid": True, "confidence": 0.9},
        "normalization": [],
    }
    document = Document()
    document.add_paragraph("姓名：张三")
    document.add_paragraph("技能：Python、FastAPI、PostgreSQL")
    document.add_paragraph("经历：3年后端开发经验")

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)

    with pytest.MonkeyPatch.context() as monkeypatch:
        mock_extract = AsyncMock(return_value=pipeline_result)
        monkeypatch.setattr("app.api.v1.resume.run_resume_extraction", mock_extract)
        resp = client.post(
            "/api/v1/resume/upload",
            files={
                "file": (
                    "resume.docx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "required_skills" in body
    assert all("skill" in item for item in body["required_skills"])
    mock_extract.assert_awaited_once()


def test_admin_review_queue_and_reset(client):
    resp = client.get("/api/v1/admin/review-queue")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1

    approve_resp = client.post(f"/api/v1/admin/audit/{items[0]['id']}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    reset_resp = client.post("/api/v1/admin/seed/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["ok"] is True


def test_admin_stats_contract(client):
    async def override_session():
        yield FakeAsyncSession([(0.8, 0.75, 0.77), (10, 2, 1), (3, 8, 12, 0.81)])

    app.dependency_overrides[get_db_session] = override_session
    try:
        resp = client.get("/api/v1/admin/stats")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "total_nodes",
        "total_edges",
        "total_positions",
        "total_skills",
        "avg_confidence",
        "hallucination_rate",
        "pending_review",
    }
    assert body["total_nodes"] == 11
