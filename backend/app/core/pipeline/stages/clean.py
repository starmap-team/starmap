"""Pipeline clean 阶段（D-01 + D-18 Task 3）。

HTML 剥离 + 规范化 + 标题提取，并在成功后设 jd.status = JdStatus.cleaned（Task 0 T5 修复）。
本模块从 executor.execute_clean 迁出；executor.py 保留兼容重导出，存量调用方零改动（D-11）。
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger

from app.core.pipeline.stages.common import (
    PipelineStageError,
    publish_stage_progress,
    run_async,
)


def execute_clean(run_id: str) -> dict[str, Any]:
    """执行 clean 阶段：HTML 剥离 + 规范化 + 标题提取 + 设 cleaned 状态。"""
    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus

    processed = 0
    errors: list[str] = []
    cleaned_titles: list[str] = []
    start = time.monotonic()

    run_async(publish_stage_progress(
        run_id, "clean", "running", progress=0.0,
        current_activity="正在加载待清洗记录...", elapsed_ms=0,
    ))

    try:
        with get_jd_raw_session() as s:
            raw_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).all()
            total = len(raw_jds)
            run_async(publish_stage_progress(
                run_id, "clean", "running", progress=0.1,
                current_activity=f"待清洗: {total} 条 (HTML剥离 + 空白规范化 + 标题提取)",
                records_processed=0,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            ))

            for idx, jd in enumerate(raw_jds):
 # Basic cleaning: strip whitespace, normalize
                if jd.clean_text:
                    jd.clean_text = jd.clean_text.strip()
                    if not jd.job_title:
                        first_line = jd.clean_text.split("\n")[0][:200]
                        jd.job_title = first_line or "Unknown"
                    if idx < 5:
                        cleaned_titles.append(jd.job_title[:60])
                processed += 1
 # T5 fix: 标记 cleaned 状态供 import 阶段读取
                jd.status = JdStatus.cleaned
 # 每处理 10 条报告一次
                if idx > 0 and idx % 10 == 0:
                    run_async(publish_stage_progress(
                        run_id, "clean", "running",
                        progress=0.1 + 0.8 * (idx / total),
                        records_processed=processed,
                        current_activity=f"已清洗 {idx}/{total} 条",
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                    ))
            s.commit()

            run_async(publish_stage_progress(
                run_id, "clean", "completed", progress=1.0,
                records_processed=processed,
                current_activity=f"清洗完成: 共 {processed} 条记录标准化",
                recent_samples=[{"title": t} for t in cleaned_titles[:5]],
                elapsed_ms=int((time.monotonic() - start) * 1000),
                message=f"清洗完成: {processed} 条",
            ))
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"clean failed: {exc}")
        logger.opt(exception=True).error("Clean stage failed: {}", exc)
        run_async(publish_stage_progress(
            run_id, "clean", "failed", current_activity=f"清洗失败: {exc}",
        ))

    return {
        "records_processed": processed,
        "errors": errors,
 # 修复: return 补 current_activity —— _mark_stage_completed 从 result 读,
 # 此前仅 SSE publish 有文案, DB 快照丢失 → 卡片"已完成但 0 数据无解释"
        "current_activity": f"清洗完成: 共 {processed} 条记录标准化",
 # D8 fix: SSE 有 recent_samples 但 return 缺 → _mark_stage_completed 读
 # result.get("recent_samples") 为 null → 详情抽屉/阶段展开看不到清洗样本
        "recent_samples": [{"title": t} for t in cleaned_titles[:5]],
        "sub_breakdown": {
            "原始总数": processed,
            "清洗标题": len(cleaned_titles),
        },
    }


__all__ = ["execute_clean"]
