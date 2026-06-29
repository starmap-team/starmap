"""W3 纯函数单元测试（不依赖 PostgreSQL / Docker）。

覆盖：compute_f1、skill_set、load_golden、call_extract_api（mock httpx）。
CI 可全量运行。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# 强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crawler.scripts.w3_run_golden import (  # noqa: E402
    compute_f1,
    load_golden,
    skill_set,
)
from crawler.scripts.w3_integration import call_extract_api  # noqa: E402


# ---------------- compute_f1 测试 ----------------
class TestComputeF1:
    """F1 算法边界值测试。"""

    def test_perfect_match(self):
        f = compute_f1({"a", "b", "c"}, {"a", "b", "c"})
        assert f["tp"] == 3
        assert f["fp"] == 0
        assert f["fn"] == 0
        assert f["precision"] == 1.0
        assert f["recall"] == 1.0
        assert f["f1"] == 1.0

    def test_no_overlap(self):
        f = compute_f1({"a"}, {"b"})
        assert f["tp"] == 0
        assert f["f1"] == 0.0

    def test_partial_overlap(self):
        f = compute_f1({"a", "b"}, {"b", "c"})
        assert f["tp"] == 1
        assert f["fp"] == 1
        assert f["fn"] == 1
        assert abs(f["precision"] - 0.5) < 0.01
        assert abs(f["recall"] - 0.5) < 0.01
        assert abs(f["f1"] - 0.5) < 0.01

    def test_both_empty(self):
        f = compute_f1(set(), set())
        assert f["f1"] == 1.0

    def test_predicted_empty(self):
        f = compute_f1(set(), {"a", "b"})
        assert f["f1"] == 0.0

    def test_golden_empty(self):
        f = compute_f1({"a"}, set())
        assert f["f1"] == 0.0


# ---------------- skill_set 测试 ----------------
class TestSkillSet:
    """技能名提取逻辑测试。"""

    def test_basic(self):
        skills = [
            {"name": "Python", "level": "expert"},
            {"name": "FastAPI", "category": "hard_skill"},
            {"name": "", "level": "x"},  # 空 name
            {"level": "x"},  # 无 name
        ]
        assert skill_set(skills) == {"Python", "FastAPI"}


# ---------------- load_golden 测试 ----------------
class TestLoadGolden:
    """Golden Set 文件加载测试。"""

    def test_loads_50_items(self):
        items = load_golden()
        assert len(items) >= 50, f"期望 50 条，实际 {len(items)}"

    def test_schema(self):
        items = load_golden()
        assert "id" in items[0]
        assert "raw_jd" in items[0]
        assert "required_skills" in items[0]

    def test_first_item(self):
        items = load_golden()
        first = items[0]
        assert first["id"] == "jd-001"
        assert "Python" in first["required_skills"]


# ---------------- call_extract_api 测试（mock httpx）----------------
class TestCallExtractApi:
    """API 调用逻辑测试（不依赖真实后端）。"""

    def test_success(self):
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

    def test_422_error(self):
        fake_resp = MagicMock()
        fake_resp.raise_for_status.side_effect = Exception("HTTP 422")
        fake_resp.status_code = 422
        fake_resp.text = "Validation failed"

        with patch("httpx.post", return_value=fake_resp):
            result = call_extract_api("bad", "http://fake:8000")

        assert "error" in result
        assert "422" in result["error"]

    def test_connection_error(self):
        with patch("httpx.post", side_effect=Exception("Connection refused")):
            result = call_extract_api("test", "http://fake:8000")

        assert "error" in result
        assert "Connection refused" in result["error"]
