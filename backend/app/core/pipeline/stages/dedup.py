"""Pipeline dedup 阶段（D-01 + D-18 Task 2）。

两遍去重（精确哈希 + SimHash 模糊），将重复 JD 标记为 duplicate。
本模块从 executor.execute_dedup 迁出；executor.py 保留兼容重导出，存量调用方零改动（D-11）。
"""
from __future__ import annotations

import time
from typing import Any

from app.core.pipeline.stages.common import (
    PipelineStageError,
    publish_stage_progress,
    run_async,
)


def execute_dedup(run_id: str) -> dict[str, Any]:
    """执行 dedup 阶段：精确哈希 + SimHash 两遍去重。"""
    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus
    from loguru import logger

    processed = 0
    duplicates_found = 0
    errors: list[str] = []
    start = time.monotonic()

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
                return {"records_processed": 0, "errors": errors, "duplicates_found": 0}

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
            from app.core.pipeline.executor import _update_source_after_dedup

            _update_source_after_dedup(run_id, duplicates_found, processed)
        except PipelineStageError:
            raise
        except Exception as exc:
            logger.warning("_update_source_after_dedup failed (non-fatal): {}", exc)

    return {"records_processed": processed, "errors": errors, "duplicates_found": duplicates_found}


__all__ = ["execute_dedup"]
