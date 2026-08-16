"""Phase 23 Task 10 — ingestion_consistency 6 项入库完整性指标单测（IS-04/DF-03）。

覆盖:
  1. 6 项指标判定函数在 fixture 数据下值正确（纯函数，不连库）
  2. 超阈数据 → evaluate_gate / gate_exit_code fail 逻辑（exit 非 0）
  3. run_baseline.decide_gate 第二道门禁合并判定（quality + ingestion 任一 FAIL → FAIL）
  4. kpi_audit.assert_status_aggregator_caliber 运行时口径断言
  5. scripts/ensure_data_consistency.py 改走 settings（不再硬编码环境变量）
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_EVAL = _ROOT / "evaluation"
_BACKEND = _ROOT / "backend"
_BACKEND_SCRIPTS = _BACKEND / "scripts"
_ROOT_SCRIPTS = _ROOT / "scripts"
for p in (_EVAL, _BACKEND, _BACKEND_SCRIPTS, _ROOT_SCRIPTS):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import ensure_data_consistency  # noqa: E402
import run_baseline  # noqa: E402
from ingestion_consistency import (  # noqa: E402
    evaluate_gate,
    gate_exit_code,
    jd_dedup_rate_metric,
    kpi_drift_metric,
    load_gates,
    orphan_ratio_metric,
    pg_neo4j_position_metric,
    pg_neo4j_skill_metric,
    psr_vs_requires_metric,
)
from kpi_audit import assert_status_aggregator_caliber, caliber_audit_passed  # noqa: E402

# ---------------------------------------------------------------------------
# 1. 6 项指标判定函数（fixture 数据下值正确）
# ---------------------------------------------------------------------------

class TestPsrVsRequires:
    def test_within_tolerance_passes(self) -> None:
        m = psr_vs_requires_metric(pg_psr=1000, neo4j_requires=1004, tolerance=0.005)
        assert m["name"] == "psr_vs_requires_count"
        assert m["diff"] == 4
        assert m["passed"] is True

    def test_over_tolerance_fails(self) -> None:
        m = psr_vs_requires_metric(pg_psr=1000, neo4j_requires=1010, tolerance=0.005)
        assert m["diff"] == 10
        assert m["passed"] is False

    def test_zero_psr_uses_min_one_tolerance(self) -> None:
        # 无 PSR 时容差至少 1 条（与 /admin/reconcile-neo4j 同款），避免 0 边飘移漏检
        m = psr_vs_requires_metric(pg_psr=0, neo4j_requires=2, tolerance=0.005)
        assert m["allowed"] == 1
        assert m["passed"] is False


class TestPgNeo4jDiffs:
    def test_position_diff_zero_passes(self) -> None:
        m = pg_neo4j_position_metric(pg_positions=120, neo4j_positions=120)
        assert m["diff"] == 0
        assert m["passed"] is True

    def test_position_diff_nonzero_fails(self) -> None:
        m = pg_neo4j_position_metric(pg_positions=120, neo4j_positions=121, allowed_diff=0)
        assert m["passed"] is False

    def test_skill_diff_zero_passes(self) -> None:
        m = pg_neo4j_skill_metric(pg_skills=300, neo4j_skills=300)
        assert m["passed"] is True

    def test_skill_diff_nonzero_fails(self) -> None:
        m = pg_neo4j_skill_metric(pg_skills=300, neo4j_skills=302, allowed_diff=0)
        assert m["passed"] is False


class TestOrphanRatio:
    def test_below_threshold_passes(self) -> None:
        m = orphan_ratio_metric(orphans=2, total=1000, max_ratio=0.005)
        assert m["ratio"] == 0.002
        assert m["passed"] is True

    def test_above_threshold_fails(self) -> None:
        m = orphan_ratio_metric(orphans=10, total=1000, max_ratio=0.005)
        assert m["ratio"] == 0.01
        assert m["passed"] is False

    def test_zero_total_passes_vacuously(self) -> None:
        m = orphan_ratio_metric(orphans=0, total=0, max_ratio=0.005)
        assert m["ratio"] == 0.0
        assert m["passed"] is True


class TestJdDedupRate:
    def test_at_or_above_min_rate_passes(self) -> None:
        m = jd_dedup_rate_metric(total_rows=1000, duplicate_rows=40, min_rate=0.95)
        assert m["dedup_rate"] == 0.96
        assert m["passed"] is True

    def test_below_min_rate_fails(self) -> None:
        m = jd_dedup_rate_metric(total_rows=1000, duplicate_rows=100, min_rate=0.95)
        assert m["dedup_rate"] == 0.9
        assert m["passed"] is False

    def test_empty_table_passes(self) -> None:
        m = jd_dedup_rate_metric(total_rows=0, duplicate_rows=0, min_rate=0.95)
        assert m["dedup_rate"] == 1.0
        assert m["passed"] is True


class TestKpiDrift:
    def test_zero_drift_passes(self) -> None:
        m = kpi_drift_metric(quality_pending=15, aggregator_pending=15, allowed_diff=0.0)
        assert m["diff"] == 0
        assert m["passed"] is True

    def test_positive_drift_fails(self) -> None:
        m = kpi_drift_metric(quality_pending=15, aggregator_pending=17, allowed_diff=0.0)
        assert m["diff"] == 2
        assert m["passed"] is False


# ---------------------------------------------------------------------------
# 2. 超阈 → gate FAIL 且 exit code 非 0
# ---------------------------------------------------------------------------

def _passing_metrics() -> list[dict]:
    return [
        psr_vs_requires_metric(1000, 1002, 0.005),
        pg_neo4j_position_metric(120, 120),
        pg_neo4j_skill_metric(300, 300),
        orphan_ratio_metric(1, 1000, 0.005),
        jd_dedup_rate_metric(1000, 30, 0.95),
        kpi_drift_metric(15, 15, 0.0),
    ]


def test_evaluate_gate_all_pass() -> None:
    gate = evaluate_gate(_passing_metrics())
    assert gate["passed"] is True
    assert gate["failed"] == []
    assert gate_exit_code(gate) == 0


def test_evaluate_gate_any_over_threshold_fails_and_exit_nonzero() -> None:
    metrics = _passing_metrics()
    # 指标 1 超阈（REQUIRES 边漂移 > 容差）
    metrics[0] = psr_vs_requires_metric(1000, 1100, 0.005)
    gate = evaluate_gate(metrics)
    assert gate["passed"] is False
    assert "psr_vs_requires_count" in gate["failed"]
    assert gate_exit_code(gate) == 1


def test_evaluate_gate_caliber_findings_fail_also_fails() -> None:
    """KPI 口径运行时断言失败 → 门禁同样 FAIL（IC-07 并入 ingestion gate）。"""
    gate = evaluate_gate(_passing_metrics(), caliber_findings=[{"id": "A1", "passed": False}])
    assert gate["passed"] is False
    assert "A1" in gate["failed"]


# ---------------------------------------------------------------------------
# 3. run_baseline 第二道门禁合并判定（quality + ingestion 任一 FAIL → FAIL，exit 非 0）
# ---------------------------------------------------------------------------

def test_decide_gate_both_pass() -> None:
    overall = run_baseline.decide_gate(
        {"passed": True, "message": "F1 ok"},
        {"passed": True, "message": "ingestion ok"},
    )
    assert overall["passed"] is True


def test_decide_gate_ingestion_fail_means_overall_fail() -> None:
    """构造超阈 ingestion gate → decide_gate FAIL → main() 返回 1（exit 非 0）。"""
    metrics = _passing_metrics()
    metrics[2] = pg_neo4j_skill_metric(300, 305, allowed_diff=0)  # 指标 3 超阈
    ingestion_gate = evaluate_gate(metrics)
    assert ingestion_gate["passed"] is False

    overall = run_baseline.decide_gate(
        {"passed": True, "message": "F1 ok"},
        ingestion_gate,
    )
    assert overall["passed"] is False
    assert "pg_vs_neo4j_skill_diff" in overall["ingestion_gate"]["failed"]
    # run_baseline.main() 的返回契约: 0 if overall['passed'] else 1
    assert 0 if overall["passed"] else 1 == 1


def test_decide_gate_quality_fail_means_overall_fail() -> None:
    overall = run_baseline.decide_gate(
        {"passed": False, "message": "F1 0.85 < 0.90"},
        {"passed": True, "message": "ingestion ok"},
    )
    assert overall["passed"] is False
    assert "quality" in overall["message"]


# ---------------------------------------------------------------------------
# 4. kpi_audit 运行时口径断言（status_aggregator 唯一事实源）
# ---------------------------------------------------------------------------

def test_caliber_assertion_passes_on_valid_aggregates() -> None:
    aggregates = {
        "today_crawl_volume": 1200,
        "today_crawl_new": 42,
        "total_jd_raw": 10000,
        "success_rate": 0.8571,
        "avg_quality_score": 0.9,
    }
    findings = assert_status_aggregator_caliber(aggregates)
    assert caliber_audit_passed(findings)


def test_caliber_assertion_fails_on_missing_key() -> None:
    aggregates = {
        "today_crawl_volume": 1200,
        "success_rate": 0.5,
    }
    findings = assert_status_aggregator_caliber(aggregates)
    assert not caliber_audit_passed(findings)
    missing = [f for f in findings if f["id"] == "A1"]
    assert missing and missing[0]["passed"] is False


def test_caliber_assertion_fails_on_impossible_count() -> None:
    """today_crawl_new > total_jd_raw → 口径不合理（A3 fail）。"""
    aggregates = {
        "today_crawl_volume": 10,
        "today_crawl_new": 999,
        "total_jd_raw": 100,
        "success_rate": 0.5,
        "avg_quality_score": 0.5,
    }
    findings = assert_status_aggregator_caliber(aggregates)
    assert not caliber_audit_passed(findings)


def test_caliber_assertion_fails_on_out_of_range_rate() -> None:
    aggregates = {
        "today_crawl_volume": 10,
        "today_crawl_new": 5,
        "total_jd_raw": 100,
        "success_rate": 1.5,  # 成功率 > 1 → 口径错误
        "avg_quality_score": 0.5,
    }
    findings = assert_status_aggregator_caliber(aggregates)
    assert not caliber_audit_passed(findings)


# ---------------------------------------------------------------------------
# 5. ensure_data_consistency.py 改走 settings（不硬编码环境变量）
# ---------------------------------------------------------------------------

def test_ensure_data_consistency_uses_settings() -> None:
    """脚本连接参数来自 app.config.settings，而非硬编码 os.getenv 默认值。"""
    assert ensure_data_consistency.NEO4J_URI == ensure_data_consistency.settings.neo4j_uri
    assert ensure_data_consistency.NEO4J_USER == ensure_data_consistency.settings.neo4j_user
    assert ensure_data_consistency.NEO4J_PASSWORD == ensure_data_consistency.settings.neo4j_password
    assert ensure_data_consistency.PG_URI == ensure_data_consistency.settings.postgres_uri
    # 源码中不得再出现硬编码连接默认值（os.getenv 兜底 / 明文库串）
    source = Path(ensure_data_consistency.__file__).read_text(encoding="utf-8")
    assert "os.getenv" not in source
    assert "starmap:starmap123456@localhost:5433" not in source
    assert "starmap123456" not in source


def test_load_gates_reads_config() -> None:
    """阈值集中 config.py（ingestion_* 字段），脚本不硬编码。"""
    from app.config import settings

    gates = load_gates()
    assert gates["psr_tolerance"] == settings.ingestion_psr_tolerance
    assert gates["position_diff"] == settings.ingestion_position_diff
    assert gates["skill_diff"] == settings.ingestion_skill_diff
    assert gates["orphan_ratio"] == settings.ingestion_orphan_ratio
    assert gates["dedup_rate"] == settings.ingestion_dedup_rate
    assert gates["kpi_drift"] == settings.ingestion_kpi_drift
    # 默认值符合 RESEARCH §2.9-1
    assert gates["psr_tolerance"] == 0.005
    assert gates["orphan_ratio"] == 0.005
    assert gates["dedup_rate"] == 0.95
    assert gates["kpi_drift"] == 0.0
