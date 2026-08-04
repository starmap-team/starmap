"""
Phase 13 契约回归测试：M2/M4/M5/M6 — 确保关键 API 字段不退化。

依赖：后端运行、admin 用户存在。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"


def _api_login():
    """return access_token string."""
    r = urllib.request.urlopen(urllib.request.Request(
        f"{API}/auth/login", method="POST",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode(),
        headers={"Content-Type": "application/json"}), timeout=10)
    return json.loads(r.read())["access_token"]


def _api_get(path: str, token: str):
    r = urllib.request.urlopen(urllib.request.Request(
        f"{API}{path}", headers={"Authorization": f"Bearer {token}"}), timeout=10)
    return r.status, json.loads(r.read())


def _api_post(path, body, token):
    r = urllib.request.urlopen(urllib.request.Request(
        f"{API}{path}", method="POST",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Bearer {token}"}), timeout=10)
    return r.status, json.loads(r.read())


def test_m2_note_field_contract():
    """M2: MatchResponse 必须包含 note 字段（可为 null）；存在无画像岗位时 note 非空。"""
    tok = _api_login()
    # Case A: skill-rich position → 200, note=null
    s, b = _api_post("/match/position",
                     {"person_skills": [{"name": "Python", "proficiency": "expert"}],
                      "target_position": "测试工程师"}, tok)
    assert s == 200, f"Expected 200, got {s}"
    assert "note" in b, "MatchResponse missing 'note' field"
    assert b["note"] is None, f"Expected note=null for skill-rich position, got {b['note']!r}"

    # Case B: exists-no-profile position → 200, note non-null
    s, b = _api_post("/match/position",
                     {"person_skills": [{"name": "Python", "proficiency": "expert"}],
                      "target_position": "Senior Python Engineer"}, tok)
    assert s == 200, f"Expected 200, got {s}"
    assert "note" in b, "MatchResponse missing 'note' field"
    assert b["note"] is not None, "Should have note for profile-less position"
    assert len(b["note"]) > 10, f"note seems too short: {b['note']!r}"

    # Case C: truly missing position → 404 (no note)
    try:
        _api_post("/match/position",
                  {"person_skills": [{"name": "Python", "proficiency": "expert"}],
                   "target_position": "ZZZ_NoSuchPosition_42"}, tok)
        raise AssertionError("Expected 404 for truly missing position")
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"


def test_m4_quality_baseline_contract():
    """M4: /quality/dashboard 必须包含 baseline_available/evaluation_explanation/evaluation_count。"""
    tok = _api_login()
    s, b = _api_get("/quality/dashboard", tok)
    assert s == 200
    assert "baseline_available" in b, "Missing baseline_available"
    assert "evaluation_count" in b, "Missing evaluation_count"
    assert "evaluation_explanation" in b, "Missing evaluation_explanation"
    # Given no eval data, these should be:
    assert b["baseline_available"] is False, "baseline_available should be False (no eval data)"
    r = b.get("report", {})
    assert r.get("warning_level") == "gray", f"warning_level should be gray, got {r.get('warning_level')}"


def test_m5_pipeline_quality_contract():
    """M5: /pipeline/data-quality 必须包含 baseline_available/quality_explanation。

    Phase 3 修正：原断言假设 DB 空（baseline_available=False），与真实有数据的
    DB 状态矛盾。改为校验契约：字段存在 + 布尔类型 + 与 explanation 一致。
    """
    tok = _api_login()
    s, b = _api_get("/pipeline/data-quality", tok)
    assert s == 200
    m = b.get("metrics", b)
    assert "baseline_available" in m, "Missing baseline_available"
    assert "quality_explanation" in m, "Missing quality_explanation"
    assert isinstance(m["baseline_available"], bool), f"baseline_available must be bool, got {type(m['baseline_available'])}"
    # M5 契约一致性：baseline_available=False 时 explanation 必须说明"未评估"且非空
    if not m["baseline_available"]:
        assert len(m["quality_explanation"]) > 10, f"quality_explanation too short {m['quality_explanation']!r}"
        assert "未评估" in m["quality_explanation"] or "暂无" in m["quality_explanation"], (
            f"baseline_available=False 但 explanation 未说明零数据: {m['quality_explanation']!r}"
        )


def test_m6_total_skills_equals_independent_skills():
    """M6: /graph/overview?group_by=domain 的 total_skills == independent_skills。"""
    tok = _api_login()
    s, b = _api_get("/graph/overview?group_by=domain", tok)
    assert s == 200
    assert b["total_skills"] == b["independent_skills"], (
        f"M6: total_skills({b['total_skills']}) != independent_skills({b['independent_skills']})"
    )
    assert b["total_positions"] == b["independent_positions"], (
        f"M6: total_positions({b['total_positions']}) != independent_positions({b['independent_positions']})"
    )
    assert len(b.get("domains", [])) > 0, "No domains; graph data may be missing"
    assert len(b.get("connections", [])) > 0, "No connections; expected at least some domain connections"
