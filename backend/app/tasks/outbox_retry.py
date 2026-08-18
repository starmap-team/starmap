"""Outbox retry worker — 自动重放失败的 graph_write_outbox 行（）。 /: 采集写入不可退——`run_batch_extract_jd` / `execute_graph_sync` 写 Neo4j
失败后留下 `status='failed'` 行；本 worker 由 Celery beat 每 30 分钟派发，重放这些
行 + sweep 进程崩溃残留的超龄 `pending` 行，终结失败行无限堆积（旧行为只增
retry_count 无消费者）。

重放幂等性：
- graph_writer 的 MERGE 键（canonical_id / name）保证同一条 extraction 重放不产生
  重复节点/边；
- `merge_skill` 的 source_count 已改为 **max 语义**（Task 1 波序前置）——同技能重复
  merge 保持 `max(coalesce(source_count,0), $source_count)`，重放不再每次 +1 放大漂移
  （ 不膨胀）。

设计约定（PATTERNS ）:
- `_create/_complete/_fail_outbox_record` 的名字面不动（`executor.py` 兼容重导出 +
  `stage3_services.py:256-296` lazy import 依赖）；本文件直接 import
  `app.core.pipeline.stages.graph_sync`，不改 executor 的 `__all__`。
- 重放前从 PG SSOT 重新解析 canonical_id（不信任 outbox 行内旧值，T1 威胁面）。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from app.exceptions import StarMapError
from app.tasks.celery_app import celery_app
from app.utils.async_helpers import run_async

#: 每行最大重试次数（达上限 → 告警日志 + audit_events， 暴露）
MAX_RETRY_COUNT = 3

#: 每轮处理行数上限
BATCH_SIZE = 50

#: 超龄 pending 行（进程崩溃残留）判定阈值
PENDING_STALE_HOURS = 6

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def retry_failed_outbox_writes(self) -> dict[str, Any]:
    """Celery beat 任务：重放 failed outbox 行 + sweep 超龄 pending 行。

    每 30 分钟（`celery_app.py` beat_schedule `retry-failed-outbox-writes`）执行；
    幂等（MERGE），重放失败行 `_fail_outbox_record` 自动 +1 retry_count。
    """
    try:
        logger.info("retry_failed_outbox_writes started")
        return run_async(_run)
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("retry_failed_outbox_writes error: {}", exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries)) from exc

async def _list_retryable_outbox(
    session: Any, batch_size: int = BATCH_SIZE) -> list[Any]:
    """扫 `status='failed' AND retry_count < MAX_RETRY_COUNT` 行（updated_at 升序）。

    Returns:
        List[GraphWriteOutbox] — 仅含可重试 failed 行（跳过 completed/drift_warning）。
    """
    from sqlalchemy import select

    from app.models.pipeline_models import GraphWriteOutbox

    result = await session.execute(
        select(GraphWriteOutbox)
        .where(GraphWriteOutbox.status == "failed")
        .where(GraphWriteOutbox.retry_count < MAX_RETRY_COUNT)
        .order_by(GraphWriteOutbox.updated_at.asc)
        .limit(batch_size)
    )
    rows = list(result.scalars.all)
 # 防御性二次过滤（SQL 已过滤；Python 侧兜底防误捡 drift_warning/completed 等）
    return [r for r in rows if r.status == "failed" and (r.retry_count or 0) < MAX_RETRY_COUNT]

async def _sweep_stale_pending(
    session: Any,
    max_age_hours: int = PENDING_STALE_HOURS,
    batch_size: int = BATCH_SIZE) -> list[Any]:
    """Sweep `status='pending' AND created_at < now - 6h` 超龄行（进程崩溃残留）。

    这些行 create 后从未 complete/fail（崩溃于 Neo4j 写中间）——与 failed 行走同一
    重放流程（成功 complete，失败转 failed + retry_count 计入）。
    """
    from sqlalchemy import select

    from app.models.pipeline_models import GraphWriteOutbox

    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    result = await session.execute(
        select(GraphWriteOutbox)
        .where(GraphWriteOutbox.status == "pending")
        .where(GraphWriteOutbox.created_at < cutoff)
        .order_by(GraphWriteOutbox.updated_at.asc)
        .limit(batch_size)
    )
    rows = list(result.scalars.all)
 # 防御性二次过滤（SQL 已过滤；Python 侧兜底防误捡 drift_warning/completed 等）
    return [
        r for r in rows
        if r.status == "pending"
        and r.created_at is not None
        and r.created_at < cutoff
    ]

async def _replay_outbox_row(session_factory: Any, row: Any, driver: Any) -> bool:
    """重放单条 outbox 行：从 PG SSOT 重载抽取记录 + canonical_id → batch_write。

    成功 → `_complete_outbox_record`（返回 True）；失败 → `_fail_outbox_record`
    （自动 retry_count+1，返回 False）；retry_count 达上限 → 告警 + audit_events
    （ 暴露）。单行失败不阻断 batch（ fail-soft）。
    """
    from sqlalchemy import select

    from app.core.extraction.graph_writer import batch_write_extractions, skill_entry_name
    from app.core.pipeline.stages.graph_sync import _complete_outbox_record, _fail_outbox_record
    from app.models.extraction_models import JDExtractionRecord, PositionRecord, SkillRecord

    extraction_ids = [uuid.UUID(str(eid)) for eid in (row.extraction_ids or [])]
    try:
        async with session_factory as session:
            records: list[Any] = []
            if extraction_ids:
                records = list(
                    (
                        await session.execute(
                            select(JDExtractionRecord).where(
                                JDExtractionRecord.id.in_(extraction_ids)
                            )
                        )
                    ).scalars.all
                )
            extractions = [rec.to_extraction_payload for rec in records]

 # 从 PG SSOT 重新解析 canonical_id（不信任 outbox 行内旧值，T1 威胁面）
            position_names = {
                str(p.get("position_name") or p.get("job_title") or "").strip
                for p in extractions
                if p
            } - {""}
            skill_names: set[str] = set
            for p in extractions:
                for entry in (p.get("required_skills") or []) + (p.get("preferred_skills") or []):
                    name = skill_entry_name(entry)
                    if name:
                        skill_names.add(name)

            position_map: dict[str, str] = {}
            if position_names:
                position_map = {
                    name: str(pid)
                    for name, pid in (
                        await session.execute(
                            select(PositionRecord.name, PositionRecord.id).where(
                                PositionRecord.name.in_(position_names)
                            )
                        )
                    ).all
                }
            skill_map: dict[str, str] = {}
            if skill_names:
                skill_map = {
                    name: str(sid)
                    for name, sid in (
                        await session.execute(
                            select(SkillRecord.name, SkillRecord.id).where(
                                SkillRecord.name.in_(skill_names)
                            )
                        )
                    ).all
                }

        if not extractions:
 # 抽取记录已不存在 → 直接 complete（避免空行无限重试）
            await _complete_outbox_record(session_factory, row.id, 0)
            return True

        canonical_ids_list: list[dict[str, Any] | None] = []
        for p in extractions:
            pname = str(p.get("position_name") or p.get("job_title") or "").strip
            cids: dict[str, Any] = {"position_id": position_map.get(pname), "skills": {}}
            for entry in (p.get("required_skills") or []) + (p.get("preferred_skills") or []):
                name = skill_entry_name(entry)
                if name and name in skill_map:
                    cids["skills"][name] = skill_map[name]
            canonical_ids_list.append(cids)

        summaries = await batch_write_extractions(
            extractions, driver, canonical_ids_list=canonical_ids_list)
        total_triples = sum(int(s.get("triples_merged", 0)) for s in summaries)
        await _complete_outbox_record(session_factory, row.id, total_triples)
        return True
    except Exception as exc:  # noqa: BLE001 — 单行重放失败不阻断 batch
        logger.warning("outbox retry replay failed (row={}): {}", row.id, exc)
        try:
            await _fail_outbox_record(session_factory, row.id, str(exc))
        except Exception as fail_exc:  # noqa: BLE001
            logger.warning("outbox retry fail-update error: {}", fail_exc)
        if (row.retry_count or 0) + 1 >= MAX_RETRY_COUNT:
            await _alert_max_retry(session_factory, row, str(exc))
        return False

async def _alert_max_retry(session_factory: Any, row: Any, error: str) -> None:
    """retry_count 达上限 → 告警日志 + audit_events 原始 SQL INSERT（ 暴露）。

    沿 admin.py:119-138 审计范式（entity_type='graph'）——让"outbox 反复失败"成为
    可检索的 P0/P1 缺陷信号，而非静默堆积。
    """
    logger.error(
        "outbox retry exhausted: id={} run_id={} extraction_ids={} error={}",
        row.id, getattr(row, "run_id", None), getattr(row, "extraction_ids", []), error)
    try:
        from sqlalchemy import text as _text

        async with session_factory as session:
            await session.execute(
                _text("""
                    INSERT INTO audit_events
                        (id, event, actor, action, detail, ip, entity_type, entity_id, created_at)
                    VALUES (:id, 'outbox_retry', 'retry_worker', 'max_retry_alert',
                            :detail, '', 'graph', :entity_id, :now)
                """),
                {
                    "id": str(uuid.uuid4),
                    "detail": (
                        f"outbox_id={row.id},retry_count={getattr(row, 'retry_count', 0)},"
                        f"error={error[:300]}"
                    ),
                    "entity_id": str(row.id),
                    "now": datetime.now(UTC),
                })
            await session.commit
    except Exception as exc:  # noqa: BLE001 — 审计写入失败不阻断重放
        logger.warning("outbox retry audit write failed (non-fatal): {}", exc)

async def _run() -> dict[str, Any]:
    """扫 failed/超龄 pending 行并逐行重放（每 30 分钟一次）。"""
    from app.core.extraction.graph_writer import GraphConfig
    from app.db.session import get_session_factory

    sm = get_session_factory
    async with sm as session:
        failed_rows = await _list_retryable_outbox(session)
        stale_rows = await _sweep_stale_pending(session)
    rows = failed_rows + stale_rows

    stats: dict[str, Any] = {
        "status": "completed",
        "failed_retryable": len(failed_rows),
        "pending_swept": len(stale_rows),
        "replayed": 0,
        "completed": 0,
        "failed_again": 0,
    }
    if not rows:
        return stats
    async with GraphConfig.get_driver as driver:
        for row in rows:
            stats["replayed"] += 1
            ok = await _replay_outbox_row(sm, row, driver)
            if ok:
                stats["completed"] += 1
            else:
                stats["failed_again"] += 1
    logger.info(
        "outbox retry round: replayed={} completed={} failed_again={}",
        stats["replayed"], stats["completed"], stats["failed_again"])
    return stats
