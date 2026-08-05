"""Coverage boost: services/import_service.py — JD 导入计数/PII/审计回归 (PLAN-013)。

import_items 的 dao/detect_pii/audit_log 全部 patch，验证:
- H3 回归: content_hash 为全量 sha256（非 [:500] 截断）
- inserted/duplicate/errors/pii_warnings 计数口径
- PII 命中时写入 PII_DETECTED 审计且不阻断入库
- 单行异常进入 errors 列表，不中断整体导入
"""

from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from app.services.import_service import import_items


class _FakeSession:
    pass


@pytest.fixture
def fake_session() -> _FakeSession:
    return _FakeSession()


async def _run(items: list[dict], *, source="test.csv", platform="test", actor="tester") -> dict:
    return await import_items(_FakeSession(), items, source, platform, actor)


class TestImportItems:
    @pytest.mark.asyncio
    async def test_inserted_and_duplicate_counts(self, fake_session: _FakeSession) -> None:
        with (
            patch("crawler.persistence.dao.upsert_jd", side_effect=["inserted", "duplicate"]),
            patch("app.services.import_service.detect_pii", return_value=[]),
            patch("app.services.import_service.audit_log") as audit,
        ):
            out = await _run([{"clean_text": "a"}, {"clean_text": "b"}])
        assert out == {"total": 2, "inserted": 1, "duplicate": 1, "errors": [], "pii_warnings": 0}
        # MANUAL_IMPORT 审计始终写入
        from app.utils.audit import AuditEvent

        events = [call.args[0].event for call in audit.call_args_list]
        assert AuditEvent.MANUAL_IMPORT in events

    @pytest.mark.asyncio
    async def test_content_hash_is_full_sha256_not_truncated(self) -> None:
        """H3 回归：hash 输入为 clean_text|job_title|company 全量拼接。"""
        item = {"clean_text": "x" * 2000, "job_title": "Backend", "company": "ACME"}
        captured: dict = {}

        def fake_upsert(rec: dict) -> str:
            captured.update(rec)
            return "inserted"

        with (
            patch("crawler.persistence.dao.upsert_jd", side_effect=fake_upsert),
            patch("app.services.import_service.detect_pii", return_value=[]),
            patch("app.services.import_service.audit_log"),
        ):
            await _run([item])
        expected = hashlib.sha256((item["clean_text"] + "|" + item["job_title"] + "|" + item["company"]).encode()).hexdigest()
        assert captured["content_hash"] == expected
        assert len(captured["content_hash"]) == 64  # sha256 全量，非截断

    @pytest.mark.asyncio
    async def test_pii_detection_writes_audit_but_does_not_block(self) -> None:
        with (
            patch("crawler.persistence.dao.upsert_jd", return_value="inserted"),
            patch("app.services.import_service.detect_pii", return_value=["phone"]),
            patch("app.services.import_service.audit_log") as audit,
        ):
            out = await _run([{"clean_text": "tel 13800138000"}])
        assert out["inserted"] == 1
        assert out["pii_warnings"] == 1
        from app.utils.audit import AuditEvent

        events = [call.args[0].event for call in audit.call_args_list]
        assert AuditEvent.PII_DETECTED in events

    @pytest.mark.asyncio
    async def test_duplicate_does_not_count_pii_warning(self) -> None:
        with (
            patch("crawler.persistence.dao.upsert_jd", return_value="duplicate"),
            patch("app.services.import_service.detect_pii", return_value=["phone"]),
            patch("app.services.import_service.audit_log"),
        ):
            out = await _run([{"clean_text": "tel 13800138000"}])
        assert out["duplicate"] == 1
        assert out["pii_warnings"] == 0  # 重复行不算 PII 警告

    @pytest.mark.asyncio
    async def test_row_exception_goes_to_errors_and_continues(self) -> None:
        with (
            patch("crawler.persistence.dao.upsert_jd", side_effect=[RuntimeError("boom"), "inserted"]),
            patch("app.services.import_service.detect_pii", return_value=[]),
            patch("app.services.import_service.audit_log"),
        ):
            out = await _run([{"clean_text": "bad"}, {"clean_text": "good"}])
        assert out["total"] == 2
        assert out["inserted"] == 1
        assert len(out["errors"]) == 1
        assert out["errors"][0]["row"] == 0
        assert "boom" in out["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_salary_ints_and_raw_html_truncation(self) -> None:
        captured: dict = {}

        def fake_upsert(rec: dict) -> str:
            captured.update(rec)
            return "inserted"

        with (
            patch("crawler.persistence.dao.upsert_jd", side_effect=fake_upsert),
            patch("app.services.import_service.detect_pii", return_value=[]),
            patch("app.services.import_service.audit_log"),
        ):
            await _run([{"clean_text": "z" * 20000, "salary_min": "8000", "salary_max": "12000"}])
        assert captured["salary_min"] == 8000  # 字符串转 int
        assert len(captured["raw_html"]) == 10000  # 截断
        assert captured["status"] == "raw"
