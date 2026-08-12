"""D5 爬虫入库层修复单测（纯函数 + 不依赖 live DB）。"""
from __future__ import annotations

import uuid

from crawler.persistence import dao
from crawler.persistence.models import JdStatus


def _base_record(**overrides):
    rec = {
        "source_site": "TEST",
        "source_url": f"https://test/{uuid.uuid4().hex}",
        "raw_html": "",
        "clean_text": "d",
        "job_title": "t",
        "company": "c",
        "salary_min": 0,
        "salary_max": 0,
        "location": "",
        "publish_date": "2026-08-12",
        "content_hash": uuid.uuid4().hex.replace("-", ""),
        "status": JdStatus.raw,
    }
    rec.update(overrides)
    return rec


# ── _sanitize: 守 publish_date / salary_* 类型边界 ──────────────────


def test_sanitize_strips_empty_publish_date():
    out = dao._sanitize(_base_record(publish_date=""))
    assert "publish_date" not in out


def test_sanitize_strips_none_publish_date():
    out = dao._sanitize(_base_record(publish_date=None))
    assert "publish_date" not in out


def test_sanitize_strips_literal_none_publish_date():
    out = dao._sanitize(_base_record(publish_date="None"))
    assert "publish_date" not in out


def test_sanitize_keeps_valid_publish_date():
    out = dao._sanitize(_base_record(publish_date="2026-08-12"))
    assert out["publish_date"] == "2026-08-12"


def test_sanitize_strips_invalid_date_string():
    """D5: 非法日期字符串（如 'invalid'）必须被剔除，否则 PG 抛 InvalidDatetimeFormat。"""
    out = dao._sanitize(_base_record(publish_date="invalid-date"))
    assert "publish_date" not in out


def test_sanitize_strips_empty_salary_min():
    out = dao._sanitize(_base_record(salary_min=""))
    assert "salary_min" not in out


def test_sanitize_coerces_numeric_strings():
    out = dao._sanitize(_base_record(salary_min="15000", salary_max="30000"))
    assert out["salary_min"] == 15000
    assert out["salary_max"] == 30000


def test_sanitize_drops_invalid_salary_strings():
    out = dao._sanitize(_base_record(salary_min="not-a-number"))
    assert "salary_min" not in out


# ── 错误穿透：get_last_error 暴露最近一次异常给上层 ───────────────


def test_get_last_error_starts_empty():
    dao.clear_last_error()
    assert dao.get_last_error() == {}


def test_get_last_error_returns_deepcopy_snapshot():
    """调用方修改返回值不应影响内部 _last_error（防止脏读）。"""
    dao.clear_last_error()
    snap = dao.get_last_error()
    snap["x"] = "y"
    assert dao.get_last_error() == {}
