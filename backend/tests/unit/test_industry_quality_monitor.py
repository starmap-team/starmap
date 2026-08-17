"""Phase 4 IndustryQualityMonitor 测试 (2026-08-17)。

锁定 app/services/industry_quality_monitor.py 的 4 个核心指标 + 告警等级：
1. unclassified_count / unclassified_ratio（approved 口径）
2. new_24h_unclassified_count / new_24h_total
3. per_source_unclassified（各源未分类率分布）
4. neo4j_pg_consistency
5. alert_level（info / warning / critical 阈值）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL
from app.services.industry_quality_monitor import (
    NEW_24H_RATIO_WARNING,
    SOURCE_RATIO_WARNING,
    UNCLASSIFIED_RATIO_CRITICAL,
    UNCLASSIFIED_RATIO_WARNING,
    IndustryQualityReport,
    SourceQualityStats,
    _compute_alert_level,
    detect_industry_quality,
    report_to_dict,
)


# ──────────────────────────────────────────────────────────────────
# _compute_alert_level unit tests (no DB needed)
# ──────────────────────────────────────────────────────────────────


class TestAlertLevelThreshold:
    """告警等级 4 档阈值：info / warning / critical。"""

    def test_clean_returns_info(self):
        report = IndustryQualityReport(
            unclassified_count=5,
            unclassified_ratio=0.05,
            total_positions=100,
            neo4j_pg_consistency=True,
        )
        assert _compute_alert_level(report) == "info"

    def test_warning_at_30_percent(self):
        report = IndustryQualityReport(
            unclassified_count=30,
            unclassified_ratio=0.30,
            total_positions=100,
            neo4j_pg_consistency=True,
        )
        assert _compute_alert_level(report) == "warning"

    def test_critical_at_50_percent(self):
        report = IndustryQualityReport(
            unclassified_count=50,
            unclassified_ratio=0.50,
            total_positions=100,
            neo4j_pg_consistency=True,
        )
        assert _compute_alert_level(report) == "critical"

    def test_critical_takes_precedence(self):
        """50% 触发 critical，即便其他指标只是 warning。"""
        report = IndustryQualityReport(
            unclassified_count=80,
            unclassified_ratio=0.80,  # critical
            total_positions=100,
            new_24h_unclassified_count=50,
            new_24h_total=100,  # 50% new — also critical
            neo4j_pg_consistency=True,
        )
        assert _compute_alert_level(report) == "critical"

    def test_warning_from_24h_ratio(self):
        """24h 新增 40%+ 未分类触发 warning。"""
        report = IndustryQualityReport(
            unclassified_count=5,
            unclassified_ratio=0.05,  # OK 总体
            total_positions=100,
            new_24h_unclassified_count=8,
            new_24h_total=10,  # 80% — critical via 24h
            neo4j_pg_consistency=True,
        )
        assert _compute_alert_level(report) == "warning"

    def test_warning_from_source_ratio(self):
        """单源 80%+ 未分类触发 warning。"""
        report = IndustryQualityReport(
            unclassified_count=5,
            unclassified_ratio=0.05,
            total_positions=100,
            neo4j_pg_consistency=True,
            per_source_unclassified=[
                SourceQualityStats(source_site="arbeitnow", unclassified=10, total=10),
            ],
        )
        assert _compute_alert_level(report) == "warning"

    def test_warning_from_neo4j_inconsistency(self):
        """Neo4j vs PG 不一致触发 warning。"""
        report = IndustryQualityReport(
            unclassified_count=5,
            unclassified_ratio=0.05,
            total_positions=100,
            neo4j_pg_consistency=False,
        )
        assert _compute_alert_level(report) == "warning"

    def test_no_positions_returns_info(self):
        """无岗位时退化为 info（不能除零触发 critical）。"""
        report = IndustryQualityReport()
        assert _compute_alert_level(report) == "info"

    def test_thresholds_consistent(self):
        """验证阈值常量顺序合理（warning < critical）。"""
        assert UNCLASSIFIED_RATIO_WARNING < UNCLASSIFIED_RATIO_CRITICAL
        assert 0 <= NEW_24H_RATIO_WARNING <= 1
        assert 0 <= SOURCE_RATIO_WARNING <= 1


class TestReportToDict:
    """report_to_dict 必须 JSON 序列化安全（无 dataclass / datetime 泄漏）。"""

    def test_dict_has_all_fields(self):
        report = IndustryQualityReport(
            unclassified_count=10,
            unclassified_ratio=0.5,
            total_positions=20,
            new_24h_unclassified_count=3,
            new_24h_total=5,
            neo4j_pg_consistency=True,
            alert_level="warning",
            timestamp=12345.0,
            per_source_unclassified=[
                SourceQualityStats(source_site="arbeitnow", unclassified=5, total=10),
            ],
        )
        d = report_to_dict(report)
        assert d["unclassified_count"] == 10
        assert d["unclassified_ratio"] == 0.5
        assert d["total_positions"] == 20
        assert d["alert_level"] == "warning"
        assert d["neo4j_pg_consistency"] is True
        assert isinstance(d["per_source_unclassified"], list)
        assert d["per_source_unclassified"][0]["source_site"] == "arbeitnow"
        assert d["per_source_unclassified"][0]["ratio"] == 0.5


# ──────────────────────────────────────────────────────────────────
# detect_industry_quality integration tests (with fake session)
# ──────────────────────────────────────────────────────────────────


@dataclass
class _FakeRow:
    """模拟 SQLAlchemy row。"""

    source: str
    total: int
    unclass: int


class _FakeSession:
    """最小化 session fake，捕获 stmt 字符串 → 返回预配置的 rows。

    不同的 stmt 字符串返回不同的结果 — 模拟 dashboard_service 的
    多次查询。
    """

    def __init__(self, statements_to_results: list[list] | None = None):
        self._statements = list(statements_to_results or [])
        self._call_index = 0
        self.calls: list[str] = []

    async def execute(self, stmt, *args, **kwargs):
        self.calls.append(str(stmt.compile()))
        if self._call_index < len(self._statements):
            result = self._statements[self._call_index]
            self._call_index += 1
        else:
            result = []
        # 模拟 SQLAlchemy Result 接口
        return _FakeResult(result)

    async def commit(self):
        pass


@dataclass
class _FakeResult:
    rows: list

    def scalar(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class TestDetectIndustryQualitySuccess:
    """detect_industry_quality 主流程。"""

    @pytest.mark.asyncio
    async def test_baseline_clean_report(self):
        """低未分类率（5%）→ info 告警。"""
        # 1: total approved = 100
        # 2: unclassified approved = 5
        # 3: new_24h_total = 10
        # 4: new_24h_unclassified = 1
        # 5: per_source_unclassified
        # 6: pg distinct industry (neo4j 部分跳过因 driver=None)
        session = _FakeSession([
            [100],  # total
            [5],    # unclassified
            [10],   # new_24h_total
            [1],    # new_24h_unclassified
            [_FakeRow(source="arbeitnow", total=5, unclass=0),
             _FakeRow(source="manual", total=2, unclass=1)],
        ])
        report = await detect_industry_quality(session, neo4j_driver=None)
        assert report.unclassified_count == 5
        assert report.total_positions == 100
        assert report.unclassified_ratio == 0.05
        assert report.new_24h_total == 10
        assert report.new_24h_unclassified_count == 1
        assert len(report.per_source_unclassified) == 2
        assert report.alert_level == "info"

    @pytest.mark.asyncio
    async def test_high_unclassified_triggers_warning(self):
        """30% 未分类 → warning 告警。"""
        session = _FakeSession([
            [100],  # total
            [30],   # unclassified = 30%
            [10],   # new_24h_total
            [1],    # new_24h_unclassified
            [],     # per_source
        ])
        report = await detect_industry_quality(session, neo4j_driver=None)
        assert report.alert_level == "warning"

    @pytest.mark.asyncio
    async def test_critical_unclassified_triggers_critical(self):
        """50% 未分类 → critical 告警。"""
        session = _FakeSession([
            [100],  # total
            [50],   # unclassified = 50%
            [10],
            [1],
            [],
        ])
        report = await detect_industry_quality(session, neo4j_driver=None)
        assert report.alert_level == "critical"

    @pytest.mark.asyncio
    async def test_no_data_returns_zero(self):
        """DB 为空时不能除零，返回 0 指标 + info 告警。"""
        session = _FakeSession([
            [0],  # total
            [0],  # unclassified
            [0],
            [0],
            [],
        ])
        report = await detect_industry_quality(session, neo4j_driver=None)
        assert report.unclassified_ratio == 0.0
        assert report.alert_level == "info"

    @pytest.mark.asyncio
    async def test_per_source_stats_computed(self):
        """各源未分类率正确计算。"""
        session = _FakeSession([
            [100],
            [30],
            [10],
            [2],
            [_FakeRow(source="arbeitnow", total=80, unclass=25),
             _FakeRow(source="jobicy", total=20, unclass=5)],
        ])
        report = await detect_industry_quality(session, neo4j_driver=None)
        sources = {s.source_site: s for s in report.per_source_unclassified}
        assert sources["arbeitnow"].unclassified == 25
        assert sources["arbeitnow"].total == 80
        assert abs(sources["arbeitnow"].ratio - 0.3125) < 0.001


class TestDetectIndustryQualityNeo4jFailure:
    """Neo4j 不可用时 fail-soft（不抛异常）。"""

    @pytest.mark.asyncio
    async def test_neo4j_driver_failure_returns_inconsistent_marker(self):
        """Neo4j driver 抛异常时，neo4j_pg_consistency 仍返回 True（fail-open）。"""
        session = _FakeSession([
            [100],
            [10],
            [5],
            [1],
            [],
            [3],  # pg distinct industry
        ])

        class _BrokenDriver:
            def session(self):
                raise RuntimeError("Neo4j down")

        report = await detect_industry_quality(session, neo4j_driver=_BrokenDriver())
        # fail-soft: consistency 标记为 True（避免 dashboard 5xx）
        assert report.neo4j_pg_consistency is True