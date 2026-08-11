"""Phase 03 Plan 03 Task 11: Cron 校验完整测试 (D-16)。

锁定 5 字段值域 + 范围 + 错误格式契约。
"""
from __future__ import annotations

import pytest

from app.core.pipeline.cron_scheduler import validate_cron_expression


class TestValidateCronValid:
    """合法 cron 表达式。"""

    @pytest.mark.parametrize(
        "cron",
        [
            "0 2 * * *",
            "*/15 * * * *",
            "0 9-18 * * 1-5",
            "0 0 1 * *",
            "30 4 1,15 * *",
            "* * * * *",
            "0 0 * * 0",
            "0 0 * * 7",
            "59 23 31 12 6",
        ],
    )
    def test_valid_cron_returns_no_errors(self, cron: str):
        result = validate_cron_expression(cron)
        assert result["valid"] is True, f"expected valid for {cron!r}, got {result}"
        assert result["errors"] == []


class TestValidateCronFieldCount:
    """字段数量校验。"""

    def test_too_few_fields(self):
        result = validate_cron_expression("0 2 * *")
        assert result["valid"] is False
        assert any("5 个字段" in e["message"] for e in result["errors"])

    def test_too_many_fields(self):
        result = validate_cron_expression("0 2 * * * *")
        assert result["valid"] is False
        assert any("5 个字段" in e["message"] for e in result["errors"])

    def test_empty_string(self):
        result = validate_cron_expression("")
        assert result["valid"] is False


class TestValidateCronMinuteBounds:
    """分字段 0-59 校验。"""

    def test_minute_out_of_range_high(self):
        result = validate_cron_expression("60 * * * *")
        assert result["valid"] is False
        assert any(e["field"] == "minute" for e in result["errors"])

    def test_minute_negative(self):
        result = validate_cron_expression("-1 * * * *")
        assert result["valid"] is False


class TestValidateCronHourBounds:
    """时字段 0-23 校验。"""

    def test_hour_out_of_range_high(self):
        result = validate_cron_expression("0 24 * * *")
        assert result["valid"] is False
        assert any(e["field"] == "hour" for e in result["errors"])


class TestValidateCronDayBounds:
    """日字段 1-31 校验。"""

    def test_day_zero(self):
        result = validate_cron_expression("0 0 0 * *")
        assert result["valid"] is False
        assert any(e["field"] == "day" for e in result["errors"])

    def test_day_out_of_range_high(self):
        result = validate_cron_expression("0 0 32 * *")
        assert result["valid"] is False
        assert any(e["field"] == "day" for e in result["errors"])


class TestValidateCronMonthBounds:
    """月字段 1-12 校验。"""

    def test_month_thirteen(self):
        result = validate_cron_expression("0 0 1 13 *")
        assert result["valid"] is False
        assert any(e["field"] == "month" for e in result["errors"])


class TestValidateCronWeekBounds:
    """周字段 0-7 校验。"""

    def test_week_eight(self):
        result = validate_cron_expression("0 0 * * 8")
        assert result["valid"] is False
        assert any(e["field"] == "week" for e in result["errors"])


class TestValidateCronErrorFormat:
    """错误返回格式契约（D-16 错误格式 CRON_INVALID）。"""

    def test_error_structure_has_field_value_message(self):
        result = validate_cron_expression("60 * * * *")
        assert result["valid"] is False
        assert len(result["errors"]) >= 1
        for err in result["errors"]:
            assert "field" in err
            assert "value" in err
            assert "message" in err
            assert err["field"] in {"minute", "hour", "day", "month", "week"}
