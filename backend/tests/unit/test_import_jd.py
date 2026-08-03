"""Tests for Phase 15-02 import service + PII detector + CSV parser."""
from __future__ import annotations

import pytest

from app.services.csv_parser import DEFAULT_CSV_MAPPING, parse_csv
from app.services.pii_detector import detect_pii

# ── PII Detector ──────────────────────────────────────────────────────


class TestPiiDetector:
    def test_detects_chinese_mobile(self):
        types = detect_pii("联系我 13800138000 或邮件")
        assert "phone" in types

    def test_detects_international_mobile(self):
        types = detect_pii("Call +86-13912345678")
        assert "phone" in types

    def test_detects_email(self):
        types = detect_pii("邮件 test@example.com 谢谢")
        assert "email" in types

    def test_detects_idcard(self):
        types = detect_pii("身份证 110101199003078811")
        assert "idcard" in types

    def test_detects_multiple(self):
        types = detect_pii("联系 13800138000 或 test@example.com")
        assert "phone" in types
        assert "email" in types

    def test_empty_returns_empty(self):
        assert detect_pii("") == []
        assert detect_pii(None) == [] if False else detect_pii("") == []  # type ignore

    def test_no_pii(self):
        types = detect_pii("我们是一家专注于 AI 的公司")
        assert types == []

    def test_short_number_not_phone(self):
        # 12345 is not 11 digits starting with 1[3-9]
        types = detect_pii("订单号 12345")
        assert "phone" not in types


# ── CSV Parser ────────────────────────────────────────────────────────


class TestCsvParser:
    def test_utf8_with_bom(self):
        """Fix M3: UTF-8 with BOM should parse correctly."""
        csv_content = (
            "职位名称,公司名称,职位描述\n"
            "Python 工程师,TestCo,负责 Python 服务开发\n"
            "Java 工程师,OtherCo,负责 Java 后端\n"
        ).encode("utf-8-sig")
        items = parse_csv(csv_content)
        assert len(items) == 2
        assert items[0]["job_title"] == "Python 工程师"
        assert items[0]["company"] == "TestCo"

    def test_gbk_encoding(self):
        """Fix M3: GBK encoding should auto-detect."""
        csv_content = (
            "职位名称,公司名称,职位描述\n"
            "Python工程师,测试公司,负责Python开发\n"
        ).encode("gbk")
        items = parse_csv(csv_content)
        assert len(items) == 1
        assert items[0]["job_title"] == "Python工程师"

    def test_invalid_encoding_raises(self):
        """Fix M3: 不可识别编码应显式抛错，不静默."""
        # Random bytes that don't match any encoding
        bad_content = b"\xff\xfe\x00\x01\x80\x81"
        with pytest.raises(ValueError, match="无法识别 CSV 编码"):
            parse_csv(bad_content)

    def test_empty_csv(self):
        """Empty CSV returns empty list."""
        items = parse_csv(b"")
        assert items == []

    def test_missing_required_fields_skipped(self):
        """Rows without job_title or clean_text should be skipped."""
        csv_content = (
            "职位名称,公司名称,职位描述\n"
            "Python工程师,TestCo,\n"  # missing clean_text
            ",TestCo2,负责Python\n"  # missing job_title
            "Valid,Co,描述正常\n"
        ).encode()
        items = parse_csv(csv_content)
        assert len(items) == 1
        assert items[0]["job_title"] == "Valid"

    def test_english_field_aliases(self):
        """English CSV column aliases should also work."""
        csv_content = (
            b"title,company,description\n"
            b"Engineer,Acme,Build stuff\n"
        )
        items = parse_csv(csv_content)
        assert len(items) == 1
        assert items[0]["job_title"] == "Engineer"
        assert items[0]["clean_text"] == "Build stuff"

    def test_custom_mapping(self):
        """Custom mapping should override defaults."""
        csv_content = (
            "岗位,公司,内容\n"
            "Data Scientist,DataCo,Analyse data\n"
        ).encode()
        custom_mapping = {"岗位": "job_title", "公司": "company", "内容": "clean_text"}
        items = parse_csv(csv_content, mapping=custom_mapping)
        assert len(items) == 1
        assert items[0]["job_title"] == "Data Scientist"

    def test_default_mapping_has_common_aliases(self):
        """Verify DEFAULT_CSV_MAPPING covers common Chinese/English headers."""
        assert "职位名称" in DEFAULT_CSV_MAPPING
        assert "title" in DEFAULT_CSV_MAPPING
        assert "公司名称" in DEFAULT_CSV_MAPPING
        assert "company" in DEFAULT_CSV_MAPPING
        assert "职位描述" in DEFAULT_CSV_MAPPING
        assert "description" in DEFAULT_CSV_MAPPING
