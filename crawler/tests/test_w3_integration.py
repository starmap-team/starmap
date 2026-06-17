"""W3 联调脚本的单元测试。

不依赖 Docker / 真实 LLM，使用 mock httpx 客户端。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 设置环境变量
os.environ.setdefault("POSTGRES_PORT", "5433")

from crawler.persistence import extraction_dao  # noqa: E402
from crawler.scripts.w3_integration import call_extract_api  # noqa: E402
from crawler.scripts.w3_run_golden import (  # noqa: E402
    compute_f1,
    load_golden,
    skill_set,
)


# ---------------- compute_f1 测试 ----------------
def test_compute_f1_perfect():
    f = compute_f1({"a", "b", "c"}, {"a", "b", "c"})
    assert f["tp"] == 3
    assert f["fp"] == 0
    assert f["fn"] == 0
    assert f["precision"] == 1.0
    assert f["recall"] == 1.0
    assert f["f1"] == 1.0


def test_compute_f1_no_overlap():
    f = compute_f1({"a"}, {"b"})
    assert f["tp"] == 0
    assert f["f1"] == 0.0


def test_compute_f1_partial():
    f = compute_f1({"a", "b"}, {"b", "c"})
    assert f["tp"] == 1
    assert f["fp"] == 1
    assert f["fn"] == 1
    assert abs(f["precision"] - 0.5) < 0.01
    assert abs(f["recall"] - 0.5) < 0.01
    assert abs(f["f1"] - 0.5) < 0.01


def test_compute_f1_both_empty():
    f = compute_f1(set(), set())
    assert f["f1"] == 1.0


def test_compute_f1_pred_empty():
    f = compute_f1(set(), {"a", "b"})
    assert f["f1"] == 0.0


def test_compute_f1_golden_empty():
    f = compute_f1({"a"}, set())
    assert f["f1"] == 0.0


# ---------------- skill_set 测试 ----------------
def test_skill_set_basic():
    skills = [
        {"name": "Python", "level": "expert"},
        {"name": "FastAPI", "category": "hard_skill"},
        {"name": "", "level": "x"},  # 空 name
        {"level": "x"},  # 无 name
    ]
    assert skill_set(skills) == {"Python", "FastAPI"}


# ---------------- load_golden 测试 ----------------
def test_load_golden_real_file():
    items = load_golden()
    assert len(items) == 50, f"期望 50 条，实际 {len(items)}"
    assert "id" in items[0]
    assert "raw_jd" in items[0]
    assert "required_skills" in items[0]


def test_load_golden_first_item():
    items = load_golden()
    first = items[0]
    assert first["id"] == "jd-001"
    assert "Python" in first["required_skills"]


# ---------------- call_extract_api 测试（mock httpx）----------------
def test_call_extract_api_success():
    """Mock httpx 返回成功响应。"""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {
        "position_name": "测试岗位",
        "required_skills": [{"name": "Python", "level": "expert"}],
        "preferred_skills": [],
        "experience_required": 3,
        "education_required": "本科",
        "responsibilities": [],
        "confidence": 0.9,
        "hallucination_score": None,
        "normalized_skills": [],
    }

    with patch("httpx.post", return_value=fake_resp) as mock_post:
        result = call_extract_api("测试 JD 内容", "http://fake:8000")

    assert "error" not in result
    assert result["position_name"] == "测试岗位"
    assert len(result["required_skills"]) == 1
    mock_post.assert_called_once()


def test_call_extract_api_422_error():
    """Mock httpx 返回 422 错误。"""
    fake_resp = MagicMock()
    fake_resp.raise_for_status.side_effect = Exception("HTTP 422")
    fake_resp.status_code = 422
    fake_resp.text = "Validation failed"

    with patch("httpx.post", return_value=fake_resp):
        result = call_extract_api("bad", "http://fake:8000")

    assert "error" in result
    assert "422" in result["error"]


def test_call_extract_api_connection_error():
    """Mock httpx 抛连接异常。"""
    with patch("httpx.post", side_effect=Exception("Connection refused")):
        result = call_extract_api("test", "http://fake:8000")

    assert "error" in result
    assert "Connection refused" in result["error"]


# ---------------- extraction_dao 端到端测试 ----------------
def test_extraction_dao_roundtrip():
    """完整测试：写一条 → 读计数。"""
    from crawler.persistence.database import engine
    from sqlalchemy import text

    # 清理
    with engine.connect() as c:
        c.execute(text("DELETE FROM jd_extraction_records WHERE job_title LIKE 'pytest_%'"))
        c.commit()

    # 写
    r = extraction_dao.upsert_extraction(
        jd_content="测试 JD 内容，要求 Python 经验 3 年",
        job_title="pytest_test_engineer",
        extracted_skills={
            "required_skills": [{"name": "Python", "level": "expert"}],
            "preferred_skills": [],
        },
        experience_years=3,
        education="本科",
        confidence=0.9,
        status="completed",
    )
    assert r == "inserted"

    # 读
    cnt = extraction_dao.count_extractions()
    assert cnt >= 1

    by_status = extraction_dao.count_by_status()
    assert "completed" in by_status
