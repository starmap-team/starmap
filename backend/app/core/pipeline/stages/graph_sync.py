"""Pipeline graph_sync 阶段（ + + + Task 6）。

将 PG 数据投影到 Neo4j 图谱（outbox 模式防漂移）。可选 reconcile 子步骤（）：
读取 `pipeline_graph_sync_reconcile_on_sync` 配置（默认 False），开启时执行 PG↔Neo4j 对账。
对账能力由原 `scripts/backfill_graph_to_pg.py` 与 `scripts/sync_pg_edges_to_graph.py`
折入；脚本打 DEPRECATED 标记保留可手动跑。

本模块从 executor.execute_graph_sync 迁出；executor.py 保留兼容重导出（）。
拆分：GraphWriteOutbox 辅助（_create/_complete/_fail）随阶段迁入本模块。
：阶段末追加 Position PG↔Neo4j 一致性校验（默认开启），差值 != 0 时写入
outbox `position_pg_neo4j_drift` 告警条目 —— 仅观察不阻断（沿 M3 ）。
"""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from app.core.pipeline.stages.common import (
 PipelineStageError,
 get_session_factory,
 publish_stage_progress,
 run_async,
)

# ── Graph Write Outbox helpers ( ; 原 executor.py, 随阶段迁入) ──

async def _create_outbox_record(
 session_factory: Any,
 outbox_id: uuid.UUID,
 run_id: uuid.UUID | None,
 extraction_ids: list[uuid.UUID] | None = None,
) -> None:
 """Create a pending outbox record before Neo4j write.

 run_id may be None for ad-hoc extractions outside a pipeline run;
 in that case extraction_ids must be populated for audit traceability.
 """
 from app.models.pipeline_models import GraphWriteOutbox

 async with session_factory as session:
 async with session.begin:
 record = GraphWriteOutbox(
 id=outbox_id,
 run_id=uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
 # D5 fix (2026-08-12): extraction_ids 是 JSON 列，UUID 对象无法被驱动
 # JSON 序列化 → "Object of type UUID is not JSON serializable"，
 # outbox 创建静默失败（non-fatal）→ 抽取产物审计/重试链路断裂。入库前转 str。
 extraction_ids=[str(eid) for eid in (extraction_ids or [])],
 status="pending",
 created_at=datetime.now(UTC),
 )
 session.add(record)

async def _complete_outbox_record(
 session_factory: Any, outbox_id: uuid.UUID, triples_written: int,
) -> None:
 """Mark outbox record as completed after successful Neo4j write."""
 from sqlalchemy import update

 from app.models.pipeline_models import GraphWriteOutbox

 async with session_factory as session:
 async with session.begin:
 await session.execute(
 update(GraphWriteOutbox)
 .where(GraphWriteOutbox.id == outbox_id)
 .values(status="completed", triples_written=triples_written, updated_at=datetime.now(UTC)),
 )

async def _fail_outbox_record(
 session_factory: Any, outbox_id: uuid.UUID, error_msg: str,
) -> None:
 """Mark outbox record as failed (will be retried on next pipeline run)."""
 from sqlalchemy import update

 from app.models.pipeline_models import GraphWriteOutbox

 async with session_factory as session:
 async with session.begin:
 await session.execute(
 update(GraphWriteOutbox)
 .where(GraphWriteOutbox.id == outbox_id)
 .values(
 status="failed",
 error=error_msg[:500],
 retry_count=GraphWriteOutbox.retry_count + 1,
 updated_at=datetime.now(UTC),
 ),
 )

def execute_graph_sync(run_id: str) -> dict[str, Any]:
 """执行 graph_sync 阶段：Neo4j 图谱投影 + 可选 reconcile。"""
 from app.tasks.stage3_services import run_build_graph_from_extractions

 processed = 0
 # 2026-08-14 门禁修复: 与 import_.execute_import 同源问题 — 三元组/节点/关系
 # 仅在 happy path 赋值，DB/Neo4j 失败路径的 return/sub_breakdown 引用它们 →
 # CI（无 DB）下 UnboundLocalError。提前初始化为 0，失败路径优雅返回。
 triples_merged = 0
 nodes = 0
 edges = 0
 errors: list[str] = []
 start = time.monotonic

 run_async(publish_stage_progress(
 run_id, "graph_sync", "running", progress=0.0,
 current_activity="正在连接 Neo4j 并准备图谱同步...", elapsed_ms=0,
 ))

 outbox_id = uuid.uuid4
 try:
 run_async(_create_outbox_record(get_session_factory, outbox_id, uuid.UUID(run_id)))
 except PipelineStageError:
 raise
 except Exception as o_exc:
 logger.warning("graph_sync outbox create failed (non-fatal): {}", o_exc)

 try:
 # : 增量 —— 只处理本次 run 开始后创建的已审核抽取记录。
 # 原实现全量重放最近 500 条历史记录（本次采集 0 新增也显示处理 226/2473），
 # 数值与本次流水线无关。改传 run 的 started_at 作为 since 过滤。
 from sqlalchemy import select

 from app.models.pipeline_models import PipelineRun

 _since: datetime | None = None
 try:
 async def _lookup_since -> datetime | None:
 session_factory = get_session_factory
 async with session_factory as session:
 return (
 await session.execute(
 select(PipelineRun.started_at).where(PipelineRun.id == uuid.UUID(run_id))
 )
 ).scalar_one_or_none
 _since = run_async(_lookup_since)
 except Exception as _e: # noqa: BLE001 — since 取不到则全量（回退旧行为）
 logger.warning("graph_sync since lookup failed (non-fatal): {}", _e)

 result = run_async(run_build_graph_from_extractions(limit=500, since=_since))
 processed = result.get("processed", 0)
 triples_merged = result.get("triples_merged", 0)
 # fix: 原读 nodes_written/edges_written —— 该键不存在（run_build_graph_
 # from_extractions 返回 nodes_touched/relationships_touched），导致死字段恒 0。
 nodes = result.get("nodes_touched", 0)
 edges = result.get("relationships_touched", 0)
 run_async(_complete_outbox_record(get_session_factory, outbox_id, triples_merged))
 run_async(publish_stage_progress(
 run_id, "graph_sync", "completed", progress=1.0,
 records_processed=processed,
 current_activity=(
 f"图谱构建完成: 扫描 {processed} 条已审核抽取记录，"
 f"三元组操作 {triples_merged}（含已存在），触及节点 {nodes} / 关系 {edges}"
 ),
 sub_breakdown={
 "扫描抽取记录": processed,
 "三元组操作": triples_merged,
 "触及节点": nodes,
 "触及关系": edges,
 },
 elapsed_ms=int((time.monotonic - start) * 1000),
 ))
 if result.get("status") != "completed":
 errors.append(f"graph sync incomplete: {result}")

 # : 可选 reconcile 子步骤（默认关闭）
 from app.config import settings

 if settings.pipeline_graph_sync_reconcile_on_sync:
 run_async(publish_stage_progress(
 run_id, "graph_sync", "running",
 progress=0.95,
 current_activity="对账中 (reconcile_on_sync=True): PG↔Neo4j",
 elapsed_ms=int((time.monotonic - start) * 1000),
 sub_step="reconcile", # 
 ))
 _run_reconcile_substep(run_id, errors, start)

 # : Position PG↔Neo4j 一致性校验（**默认开启**，仅观察不阻断）。
 # 与 reconcile 不同：这里只比对计数并告警，不改任何数据。
 _run_position_consistency_substep(run_id)
 except PipelineStageError:
 raise
 except Exception as exc:
 errors.append(f"graph_sync failed: {exc}")
 logger.opt(exception=True).error("Graph sync stage failed: {}", exc)
 try:
 run_async(_fail_outbox_record(get_session_factory, outbox_id, str(exc)))
 except PipelineStageError:
 raise
 except Exception as o_err:
 logger.warning("outbox fail update error: {}", o_err)
 run_async(publish_stage_progress(
 run_id, "graph_sync", "failed", current_activity=f"图谱同步失败: {exc}",
 ))

 return {
 "records_processed": processed,
 "errors": errors,
 "outbox_id": str(outbox_id),
 # 修复: return 补 current_activity（DB 快照持久化，解释"0 条扫描/构建结果"）
 "current_activity": (
 f"图谱构建完成: {triples_merged} 三元组 / {nodes} 节点 / {edges} 关系"
 if processed
 else "无新抽取记录待投影"
 ),
 # D8 fix: SSE publish 有 sub_breakdown 但 return 缺 → 持久化丢失 →
 # 图谱构建阶段展开无「节点/关系/triples」详情
 # : 键名与 publish 一致（扫描抽取记录/三元组操作/触及节点/触及关系）
 "sub_breakdown": {
 "扫描抽取记录": processed,
 "三元组操作": triples_merged,
 "触及节点": nodes,
 "触及关系": edges,
 },
 }

# ── Position PG↔Neo4j 一致性校验（ ；沿 仅观察不阻断）──

#: outbox 告警条目类型标识，写入 GraphWriteOutbox.error 前缀便于检索
POSITION_DRIFT_ALERT_TYPE = "position_pg_neo4j_drift"

#: 一致性告警使用的 outbox status，与写入重试生命周期
#: （'pending' / 'completed' / 'failed'）区分，避免被重试逻辑误捡
POSITION_DRIFT_OUTBOX_STATUS = "drift_warning"

async def _count_pg_positions(session_factory: Any) -> int:
 """PG position_records 行数。"""
 import sqlalchemy as sa

 from app.models.extraction_models import PositionRecord

 async with session_factory as session:
 result = await session.execute(sa.select(sa.func.count).select_from(PositionRecord))
 return int(result.scalar or 0)

async def _count_neo4j_positions(neo4j_driver: Any) -> tuple[int, int]:
 """Neo4j Position 节点数：返回 (总数, 带 canonical_id 的节点数)。

 带 canonical_id 的节点才是 SSOT 管理范围；差额即早期按 name MERGE 留下的遗留节点。
 """
 async with neo4j_driver.session as s:
 result = await s.run(
 "MATCH (n:Position) RETURN count(n) AS total, count(n.canonical_id) AS with_cid"
 )
 record = await result.single
 if record is None:
 return 0, 0
 return int(record["total"]), int(record["with_cid"])

async def _write_position_drift_outbox(
 session_factory: Any, run_id: str | None, detail: str,
) -> None:
 """把 Position 漂移告警写入 outbox（severity=warning，不阻断流水线）。"""
 from app.models.pipeline_models import GraphWriteOutbox

 async with session_factory as session:
 async with session.begin:
 session.add(GraphWriteOutbox(
 id=uuid.uuid4,
 run_id=uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
 extraction_ids=[],
 status=POSITION_DRIFT_OUTBOX_STATUS,
 triples_written=0,
 error=f"{POSITION_DRIFT_ALERT_TYPE}: {detail}"[:500],
 created_at=datetime.now(UTC),
 ))

async def _check_position_consistency(
 session_factory: Any, neo4j_driver: Any, run_id: str | None = None,
) -> int:
 """: Neo4j Position 节点数 vs PG PositionRecord 行数一致性校验。

 差值 != 0 时写入 outbox `position_pg_neo4j_drift` 告警条目（severity=warning）。
 **仅观察不阻断**：任何异常都被吞掉并记日志，不影响 graph_sync 阶段结果（沿 M3 ）。

 Returns:
 `neo4j_total - pg_count` 差值；无法取数时返回 0。
 """
 if neo4j_driver is None:
 logger.debug("position consistency check skipped: neo4j_driver unavailable")
 return 0

 try:
 pg_count = await _count_pg_positions(session_factory)
 neo4j_total, neo4j_with_cid = await _count_neo4j_positions(neo4j_driver)
 except Exception as exc: # noqa: BLE001 — 取数失败不阻断阶段
 logger.warning("position consistency check failed (non-fatal): {}", exc)
 return 0

 diff = neo4j_total - pg_count
 if diff == 0:
 logger.info("position consistency ok: pg={} neo4j={}", pg_count, neo4j_total)
 return 0

 detail = (
 f"pg={pg_count} neo4j_total={neo4j_total} neo4j_with_canonical_id={neo4j_with_cid} "
 f"diff={diff} legacy_without_canonical_id={neo4j_total - neo4j_with_cid}"
 )
 logger.warning("position PG↔Neo4j drift detected (warning only): {}", detail)
 try:
 await _write_position_drift_outbox(session_factory, run_id, detail)
 except Exception as exc: # noqa: BLE001 — 告警落库失败同样不阻断
 logger.warning("position drift outbox write failed (non-fatal): {}", exc)
 return diff

def _run_position_consistency_substep(run_id: str) -> int:
 """同步包装：在 graph_sync 阶段末调用一致性校验（默认开启，仅告警）。"""
 from app.services.resources import resources as app_resources

 try:
 return run_async(_check_position_consistency(
 get_session_factory, app_resources.neo4j_driver, run_id,
 ))
 except Exception as exc: # noqa: BLE001 — 校验永不阻断阶段
 logger.warning("position consistency sub-step failed (non-fatal): {}", exc)
 return 0

def _run_reconcile_substep(run_id: str, errors: list[str], start: float) -> None:
 """: 对账子步骤 — 执行 PG↔Neo4j 一致性补齐。

 对账逻辑折入此处；原 `scripts/backfill_graph_to_pg.py` 与 `scripts/sync_pg_edges_to_graph.py`
 已打 DEPRECATED 标记保留可手动跑。失败仅告警不阻断流水线。
 """
 try:
 # Step 1: PG ← Neo4j (补齐缺失 skill/position)
 # Step 2: PG → Neo4j (补齐缺失 REQUIRES edges)
 # 完整实现见 scripts/backfill_graph_to_pg.py + scripts/sync_pg_edges_to_graph.py。
 # 当前实现调用 services/pipeline_consistency.check_pg_neo4j_consistency 触发告警。
 from app.services.pipeline_consistency import check_pg_neo4j_consistency

 run_async(check_pg_neo4j_consistency(run_id))
 logger.info("graph_sync reconcile sub-step completed for run_id={}", run_id)
 except Exception as exc: # noqa: BLE001
 err_msg = f"reconcile sub-step failed (non-fatal): {exc}"
 errors.append(err_msg)
 logger.warning(err_msg)

__all__ = [
 "POSITION_DRIFT_ALERT_TYPE",
 "POSITION_DRIFT_OUTBOX_STATUS",
 "_check_position_consistency",
 "_complete_outbox_record",
 "_create_outbox_record",
 "_fail_outbox_record",
 "execute_graph_sync",
]
