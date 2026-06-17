"""W3 集成测试（需要 PostgreSQL）。

仅包含依赖数据库的测试用例。
纯函数测试见 test_w3_golden_f1.py。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 设置环境变量
os.environ.setdefault("POSTGRES_PORT", "5433")

from crawler.persistence import extraction_dao  # noqa: E402


# ---------------- extraction_dao 端到端测试 ----------------
class TestExtractionDao:
    """extraction_dao 写入 + 查询集成测试。"""

    def test_roundtrip(self):
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
