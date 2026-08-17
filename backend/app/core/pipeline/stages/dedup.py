"""Pipeline dedup 阶段（D-01 + D-18 Task 2）。

两遍去重（精确哈希 + SimHash 模糊），将重复 JD 标记为 duplicate。
本模块从 executor.execute_dedup 迁出；executor.py 保留兼容重导出，存量调用方零改动（D-11）。
Phase 03 Plan 03 拆分：`_update_source_after_dedup` 辅助随阶段迁入本模块。
"""
from __future__ import annotations

import time
from typing import Any

from app.core.pipeline.stages.common import (
    PipelineStageError,
    get_session_factory,
    publish_stage_progress,
    run_async,
    select,
)


def _update_source_after_dedup(run_id: str, duplicates: int, total: int) -> None:
    """execute_dedup 完成后更新 DataSourceRecord.duplicate_rate.

    Looks up all active crawler DataSourceRecords and updates the
    duplicate_rate for each.  When only one source exists the update is
    unambiguous; when multiple exist, the same rate is applied to all
    (dedup operates across the whole raw_jd table).
    """
    async def _update():
        from loguru import logger

        from app.models.pipeline_models import DataSourceRecord

        session_factory = get_session_factory()
        async with session_factory() as session:
            ds_result = await session.execute(
                select(DataSourceRecord).where(
                    DataSourceRecord.source_type == "crawler",
                    DataSourceRecord.status == "active",
                )
            )
            sources = ds_result.scalars().all()
            if not sources:
                logger.warning("_update_source_after_dedup: no active crawler sources found for run_id={}", run_id)
                return
            dup_rate = round(duplicates / total, 4) if total > 0 else 0.0
            for ds in sources:
                ds.duplicate_rate = dup_rate
            await session.commit()
            logger.info(
                "_update_source_after_dedup: duplicate_rate={} for {} source(s), run_id={}",
                dup_rate, len(sources), run_id,
            )
    run_async(_update())


def execute_dedup(run_id: str) -> dict[str, Any]:
    """执行 dedup 阶段：精确哈希 + SimHash 两遍去重。"""
    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus
    from loguru import logger

    processed = 0
    duplicates_found = 0
    errors: list[str] = []
    start = time.monotonic()
 # D8 fix: unique_jds/duplicates 在 except 路径（dedup_service 抛错）未定义 →
 # UnboundLocalError。初始化默认值，失败时返回 0 分解（诚实空态）。
    unique_jds: list[Any] = []
    duplicates = 0
    unique_titles: list[str] = []

    run_async(publish_stage_progress(
        run_id, "dedup", "running",
        progress=0.0,
        records_processed=0,
        current_activity="正在加载待去重记录...",
        message="去重阶段启动",
        elapsed_ms=0,
    ))

    try:
        with get_jd_raw_session() as s:
            raw_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).all()
            if not raw_jds:
                run_async(publish_stage_progress(
                    run_id, "dedup", "completed", progress=1.0,
                    records_processed=0, current_activity="无待去重记录",
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                ))
                return {
                    "records_processed": 0,
                    "errors": errors,
                    "duplicates_found": 0,
 # 空分支 return 也补 current_activity（DB 快照持久化）
                    "current_activity": "无待去重记录",
 # D8: 0 条时也返回分解，详情抽屉/阶段展开不显示空白
                    "sub_breakdown": {"原始总数": 0, "唯一数": 0, "重复数": 0},
                    "recent_samples": [],
                }

            processed = len(raw_jds)
            run_async(publish_stage_progress(
                run_id, "dedup", "running",
                progress=0.1,
                records_processed=processed,
                current_activity=f"待去重: {processed} 条 (精确哈希比对 + SimHash 模糊匹配)",
                message=f"已加载 {processed} 条记录",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            ))

            from app.services.dedup_service import dedup_jd_records
            from app.services.resources import resources as app_resources

            redis_client = app_resources.redis_client

            def _get_clean_text(jd: Any) -> str:
                return jd.clean_text or ""

            unique_jds, dup_jds = run_async(
                dedup_jd_records(
                    raw_jds,
                    text_getter=_get_clean_text,
                    redis_client=redis_client,
                    threshold=3,
                ),
            )

            dup_ids = {id(jd) for jd in dup_jds}
            for jd in raw_jds:
                if id(jd) in dup_ids:
                    jd.status = JdStatus.duplicate

            duplicates = len(dup_jds)
            duplicates_found = duplicates
 # D8c: 在 session 内收集唯一记录标题（dedup_jd_records 返回的实例可能
 # 已脱离 session，commit 后访问 .job_title 触发 DetachedInstanceError）
            unique_titles = [
                (jd.job_title or "未命名")[:60]
                for jd in unique_jds
                if getattr(jd, "job_title", None)
            ]
            s.commit()

            run_async(publish_stage_progress(
                run_id, "dedup", "completed",
                progress=1.0,
                records_processed=processed - duplicates,
                current_activity=f"去重完成: 总 {processed} → 唯一 {len(unique_jds)} 条 (剔除 {duplicates} 条重复)",
                sub_breakdown={"原始总数": processed, "唯一数": len(unique_jds), "重复数": duplicates},
                elapsed_ms=int((time.monotonic() - start) * 1000),
                message=f"去重完成: {len(unique_jds)} 唯一 / {duplicates} 重复",
            ))

            logger.info(
                "Dedup stage run_id={}: {} total, {} unique, {} duplicates",
                run_id, processed, len(unique_jds), duplicates,
            )
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"dedup failed: {exc}")
        logger.opt(exception=True).error("Dedup stage failed: {}", exc)
        run_async(publish_stage_progress(
            run_id, "dedup", "failed",
            current_activity=f"去重失败: {exc}",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        ))
    finally:
 # Phase 2 SOURCE-02: execute_dedup 后更新 duplicate_rate (UAT 修复)
        try:
            _update_source_after_dedup(run_id, duplicates_found, processed)
        except PipelineStageError:
            raise
        except Exception as exc:
            logger.warning("_update_source_after_dedup failed (non-fatal): {}", exc)

    return {
        "records_processed": processed,
        "errors": errors,
        "duplicates_found": duplicates_found,
 # Phase 19 修复: return 补 current_activity（DB 快照持久化，卡片解释"为何 0/去重结果"）
        "current_activity": (
            f"去重完成: 总 {processed} → 唯一 {len(unique_jds)} 条"
            f" (剔除 {duplicates} 条重复)"
            if processed
            else "无待去重记录"
        ),
 # 2026-08-12 (pipeline 联调): 持久化去重分解，详情抽屉可解释"为何入库 0"
        "sub_breakdown": {
            "原始总数": processed,
            "唯一数": len(unique_jds),
            "重复数": duplicates,
        },
 # D8 fix: 补去重后唯一记录标题样本（详情抽屉展示去重结果）——
 # 用 session 内收集的 unique_titles，避免访问脱绑实例
        "recent_samples": [{"title": t} for t in unique_titles[:5]],
    }


__all__ = ["_update_source_after_dedup", "execute_dedup"]
