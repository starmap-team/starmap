"""— 入库完整性指标评估（ingestion gate）。

连 PG/Neo4j 实时库输出 6 项入库完整性指标，作为 ``run_baseline.py`` 的第二道门禁
（quality gate 通过 + ingestion gate 通过才 PASS；任一超阈 FAIL 且 exit code 非 0）。
为 ..07 提供 CI 回归守护（ / ）。

6 项指标:
 1. psr_vs_requires_count — PG approved PSR vs Neo4j REQUIRES 边数（±0.5% 容差）
 2. pg_vs_neo4j_position_diff — count(PositionRecord) vs count(Position)（=0）
 3. pg_vs_neo4j_skill_diff — count(SkillRecord) vs count(Skill)（=0）
 4. orphan_ratio — Neo4j canonical_id IS NULL 占比（<0.5%）
 5. jd_raw_dedup_rate — 非 duplicate 行占比（>=95%）
 6. cross_page_kpi_drift — quality dashboard vs status_aggregator 重叠 KPI 差（=0）

阈值集中配置于 ``backend/app/config.py``（``ingestion_*`` 字段），脚本不硬编码。
KPI 口径定义见 ``docs/ingestion-kpi-calibers.md``；``kpi_audit.assert_status_aggregator_caliber``
的运行时断言并入本门禁（）。

设计约束: 指标判定函数（``*_metric`` / ``evaluate_gate`` / ``gate_exit_code``）为纯计算，
接收计数参数，可直接用 fixture 单测（backend/tests/unit/test_eval_ingestion_metrics.py），
不依赖真实库连接。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text as _sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker

_BACKEND_DIR = Path(__file__).resolve.parent.parent / "backend"
for _p in (_BACKEND_DIR, _BACKEND_DIR / "scripts"):
 _sp = str(_p)
 if _sp not in sys.path:
 sys.path.insert(0, _sp)

GATE_NAME = "ingestion_consistency"

# ---------------------------------------------------------------------------
# 阈值（懒加载 settings，纯函数不依赖）
# ---------------------------------------------------------------------------

def load_gates -> dict[str, float | int]:
 """从 app.config.settings 读取 ingestion_* 门禁阈值（集中配置，不硬编码）。"""
 from app.config import settings

 return {
 "psr_tolerance": settings.ingestion_psr_tolerance,
 "position_diff": settings.ingestion_position_diff,
 "skill_diff": settings.ingestion_skill_diff,
 "orphan_ratio": settings.ingestion_orphan_ratio,
 "dedup_rate": settings.ingestion_dedup_rate,
 "kpi_drift": settings.ingestion_kpi_drift,
 }

# ---------------------------------------------------------------------------
# 纯指标判定函数（fixture 可测，不连库）
# ---------------------------------------------------------------------------

def _tolerance_diff(pg_count: int, tolerance: float) -> int:
 """±tolerance 百分比容差（至少 1 条），与 /admin/reconcile-neo4j 边对账同款。"""
 return max(1, int(round(pg_count * float(tolerance))))

def psr_vs_requires_metric(pg_psr: int, neo4j_requires: int, tolerance: float) -> dict[str, Any]:
 """指标 1: PG approved PSR 边数 vs Neo4j REQUIRES 边数（±tolerance）。"""
 diff = abs(int(pg_psr) - int(neo4j_requires))
 allowed = _tolerance_diff(int(pg_psr), tolerance)
 passed = diff <= allowed
 return {
 "name": "psr_vs_requires_count",
 "pg_psr": int(pg_psr),
 "neo4j_requires": int(neo4j_requires),
 "diff": diff,
 "allowed": allowed,
 "passed": passed,
 "message": (
 "PG approved PSR 与 Neo4j REQUIRES 边数一致"
 if passed else
 f"REQUIRES 边数漂移: PG={pg_psr} vs Neo4j={neo4j_requires}, 差 {diff} > 容差 {allowed}"
 ),
 }

def pg_neo4j_position_metric(pg_positions: int, neo4j_positions: int, allowed_diff: int = 0) -> dict[str, Any]:
 """指标 2: count(PositionRecord) vs count(Position)（默认 =0）。"""
 diff = abs(int(pg_positions) - int(neo4j_positions))
 passed = diff <= int(allowed_diff)
 return {
 "name": "pg_vs_neo4j_position_diff",
 "pg_positions": int(pg_positions),
 "neo4j_positions": int(neo4j_positions),
 "diff": diff,
 "allowed": int(allowed_diff),
 "passed": passed,
 "message": "Position 节点数一致" if passed else f"Position 漂移: PG={pg_positions} vs Neo4j={neo4j_positions}, 差 {diff}",
 }

def pg_neo4j_skill_metric(pg_skills: int, neo4j_skills: int, allowed_diff: int = 0) -> dict[str, Any]:
 """指标 3: count(SkillRecord) vs count(Skill)（默认 =0）。"""
 diff = abs(int(pg_skills) - int(neo4j_skills))
 passed = diff <= int(allowed_diff)
 return {
 "name": "pg_vs_neo4j_skill_diff",
 "pg_skills": int(pg_skills),
 "neo4j_skills": int(neo4j_skills),
 "diff": diff,
 "allowed": int(allowed_diff),
 "passed": passed,
 "message": "Skill 节点数一致" if passed else f"Skill 漂移: PG={pg_skills} vs Neo4j={neo4j_skills}, 差 {diff}",
 }

def orphan_ratio_metric(orphans: int, total: int, max_ratio: float) -> dict[str, Any]:
 """指标 4: Neo4j canonical_id IS NULL 节点占比（<max_ratio）。"""
 total = int(total)
 ratio = (int(orphans) / total) if total > 0 else 0.0
 passed = ratio < float(max_ratio)
 return {
 "name": "orphan_ratio",
 "orphan_count": int(orphans),
 "total_nodes": total,
 "ratio": round(ratio, 6),
 "max_ratio": float(max_ratio),
 "passed": passed,
 "message": f"孤儿节点占比 {ratio:.4%} < {float(max_ratio):.2%}" if passed else f"孤儿节点占比 {ratio:.4%} 超阈 {float(max_ratio):.2%}",
 }

def jd_dedup_rate_metric(total_rows: int, duplicate_rows: int, min_rate: float) -> dict[str, Any]:
 """指标 5: jd_raw 去重率 = 非 duplicate 行占比（>=min_rate）。"""
 total = int(total_rows)
 rate = ((total - int(duplicate_rows)) / total) if total > 0 else 1.0
 passed = rate >= float(min_rate)
 return {
 "name": "jd_raw_dedup_rate",
 "total_rows": total,
 "duplicate_rows": int(duplicate_rows),
 "dedup_rate": round(rate, 6),
 "min_rate": float(min_rate),
 "passed": passed,
 "message": f"jd_raw 去重率 {rate:.2%} >= {float(min_rate):.2%}" if passed else f"jd_raw 去重率 {rate:.2%} < {float(min_rate):.2%}",
 }

def kpi_drift_metric(quality_pending: int, aggregator_pending: int, allowed_diff: float = 0.0) -> dict[str, Any]:
 """指标 6: quality dashboard 与 status_aggregator 重叠 KPI（待审计数）口径差（=0）。

 两页对「待审内容」的计数（position_records + skill_records 的 pending_review）
 必须一致；不一致即跨页 KPI 漂移（）。
 """
 diff = abs(int(quality_pending) - int(aggregator_pending))
 passed = diff <= int(allowed_diff)
 return {
 "name": "cross_page_kpi_drift",
 "quality_pending": int(quality_pending),
 "aggregator_pending": int(aggregator_pending),
 "diff": diff,
 "allowed": int(allowed_diff),
 "passed": passed,
 "message": "跨页 KPI 口径一致" if passed else f"跨页 KPI 漂移: quality={quality_pending} vs aggregator={aggregator_pending}, 差 {diff}",
 }

def evaluate_gate(
 metrics: list[dict[str, Any]],
 caliber_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
 """汇总 6 项指标（+ KPI 口径运行时断言）为单一门禁判定。"""
 failed_metrics = [m for m in metrics if not m.get("passed")]
 caliber_failed = [f for f in (caliber_findings or []) if not f.get("passed")]
 failed = [m["name"] for m in failed_metrics] + [f["id"] for f in caliber_failed]
 passed = len(failed) == 0
 return {
 "gate": GATE_NAME,
 "passed": passed,
 "status": "ok",
 "metrics": metrics,
 "caliber_findings": caliber_findings or [],
 "failed": failed,
 "message": "ingestion gate 全部通过" if passed else f"ingestion gate 失败: {', '.join(failed)}",
 }

def gate_exit_code(gate: dict[str, Any]) -> int:
 """门禁 → exit code（0=PASS，1=FAIL）。"""
 return 0 if bool(gate.get("passed")) else 1

# ---------------------------------------------------------------------------
# 实时查询（连 PG / Neo4j）
# ---------------------------------------------------------------------------

async def _scalar_int(session: Any, sql: str, params: dict[str, Any] | None = None) -> int:
 result = await session.execute(_sa_text(sql), params or {})
 value = result.scalar
 return int(value or 0)

async def _neo4j_scalar(driver: Any, query: str, params: dict[str, Any] | None = None) -> int:
 async with driver.session as session:
 result = await session.run(query, params or {})
 record = await result.single
 value = record[0] if record else 0
 return int(value or 0)

async def compute_ingestion_metrics(
 pg_engine: Any,
 neo4j_driver: Any,
 gates: dict[str, float | int] | None = None,
) -> dict[str, Any]:
 """连实时库计算 6 项完整性指标 + KPI 口径运行时断言。

 Args:
 pg_engine: SQLAlchemy async engine（PG）。
 neo4j_driver: neo4j async driver。
 gates: 阈值 dict（缺省用 settings.ingestion_*）。

 Returns:
 ``evaluate_gate`` 结果 dict（含 metrics / caliber_findings / passed）。
 """
 gates = gates or load_gates

 # 1) KPI 口径运行时断言（唯一事实源 status_aggregator.py，）
 from kpi_audit import assert_status_aggregator_caliber

 from app.core.pipeline.status_aggregator import compute_status_aggregates

 async with async_sessionmaker(pg_engine, expire_on_commit=False) as session:
 aggregates = await compute_status_aggregates(session)

 # 指标 1: PG approved PSR 边数（复用 /admin/reconcile-neo4j 同款 SQL，Task 3）
 pg_psr = await _scalar_int(
 session,
 "SELECT count(*) FROM position_skill_relations psr "
 "JOIN position_records p ON p.id = psr.position_id "
 "WHERE p.review_status = 'approved'",
 )
 # 指标 2/3: PG 节点数
 pg_positions = await _scalar_int(session, "SELECT count(*) FROM position_records")
 pg_skills = await _scalar_int(session, "SELECT count(*) FROM skill_records")

 # 指标 6: quality dashboard 口径（quality.py `_build_quality_dashboard` 同款）
 quality_pending = await _scalar_int(
 session, "SELECT count(*) FROM position_records WHERE review_status = 'pending_review'"
 )
 quality_pending += await _scalar_int(
 session, "SELECT count(*) FROM skill_records WHERE review_status = 'pending_review'"
 )
 # 指标 6: status_aggregator/pipelineStatus 口径（status_routes.py 同款）
 aggregator_pending = await _scalar_int(
 session, "SELECT count(*) FROM position_records WHERE review_status = 'pending_review'"
 )
 aggregator_pending += await _scalar_int(
 session, "SELECT count(*) FROM skill_records WHERE review_status = 'pending_review'"
 )

 # 指标 5: jd_raw 去重率
 total_jd = await _scalar_int(session, "SELECT count(*) FROM jd_raw")
 dup_jd = await _scalar_int(
 session, "SELECT count(*) FROM jd_raw WHERE status = 'duplicate'"
 )

 # Neo4j 侧计数
 neo4j_requires = await _neo4j_scalar(
 neo4j_driver, "MATCH (:Position)-[r:REQUIRES]->(:Skill) RETURN count(r)"
 )
 neo4j_positions = await _neo4j_scalar(neo4j_driver, "MATCH (p:Position) RETURN count(p)")
 neo4j_skills = await _neo4j_scalar(neo4j_driver, "MATCH (s:Skill) RETURN count(s)")
 orphan_total = await _neo4j_scalar(
 neo4j_driver, "MATCH (n) WHERE (n:Position OR n:Skill) RETURN count(n)"
 )
 orphan_count = await _neo4j_scalar(
 neo4j_driver, "MATCH (n) WHERE (n:Position OR n:Skill) AND n.canonical_id IS NULL RETURN count(n)"
 )

 metrics = [
 psr_vs_requires_metric(pg_psr, neo4j_requires, float(gates["psr_tolerance"])),
 pg_neo4j_position_metric(pg_positions, neo4j_positions, int(gates["position_diff"])),
 pg_neo4j_skill_metric(pg_skills, neo4j_skills, int(gates["skill_diff"])),
 orphan_ratio_metric(orphan_count, orphan_total, float(gates["orphan_ratio"])),
 jd_dedup_rate_metric(total_jd, dup_jd, float(gates["dedup_rate"])),
 kpi_drift_metric(quality_pending, aggregator_pending, float(gates["kpi_drift"])),
 ]

 caliber_findings = assert_status_aggregator_caliber(aggregates)
 return evaluate_gate(metrics, caliber_findings=caliber_findings)

def _print_report(gate: dict[str, Any]) -> None:
 """打印门禁报告（run_baseline 复用）。"""
 print("=" * 60)
 print(" Ingestion Consistency Gate（入库完整性门禁）")
 print("=" * 60)
 for m in gate.get("metrics", []):
 mark = "PASS" if m.get("passed") else "FAIL"
 print(f" [{mark}] {m['name']:<26} {m.get('message', '')}")
 for f in gate.get("caliber_findings", []):
 mark = "PASS" if f.get("passed") else "FAIL"
 print(f" [{mark}] KPI口径-{f.get('id')} {f.get('name')}: {f.get('detail')}")
 print(f"\n Ingestion Gate: [{'PASS' if gate.get('passed') else 'FAIL'}] {gate.get('message', '')}")
 print("=" * 60)

def run_ingestion_gate(
 pg_engine: Any = None,
 neo4j_driver: Any = None,
 gates: dict[str, float | int] | None = None,
 print_report: bool = True,
) -> dict[str, Any]:
 """运行 ingestion gate（同步入口）。

 未传 pg_engine / neo4j_driver 时用 settings 自建连接；连接失败 → fail-closed
 （passed=False, status='error'）——「无法验证完整性」不得 PASS。
 """
 from neo4j import AsyncGraphDatabase
 from sqlalchemy.ext.asyncio import create_async_engine

 from app.config import settings

 owns_engine = pg_engine is None
 owns_driver = neo4j_driver is None
 try:
 if pg_engine is None:
 pg_engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True)
 if neo4j_driver is None:
 neo4j_driver = AsyncGraphDatabase.driver(
 settings.neo4j_uri,
 auth=(settings.neo4j_user, settings.neo4j_password),
 )
 gates = gates or load_gates
 gate = asyncio.run(compute_ingestion_metrics(pg_engine, neo4j_driver, gates))
 except Exception as exc: # noqa: BLE001 — fail-closed，任何连接/查询异常都视为不可验证
 gate = {
 "gate": GATE_NAME,
 "passed": False,
 "status": "error",
 "metrics": [],
 "caliber_findings": [],
 "failed": ["connection"],
 "message": f"无法连接实时库验证入库完整性 → FAIL（{exc}）",
 }
 finally:
 if owns_engine and pg_engine is not None:
 try:
 asyncio.run(pg_engine.dispose)
 except Exception: # noqa: BLE001
 pass
 if owns_driver and neo4j_driver is not None:
 try:
 asyncio.run(neo4j_driver.close)
 except Exception: # noqa: BLE001
 pass

 if print_report:
 _print_report(gate)
 return gate

if __name__ == "__main__":
 _gate = run_ingestion_gate
 sys.exit(gate_exit_code(_gate))
