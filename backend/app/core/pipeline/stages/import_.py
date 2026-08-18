"""Pipeline import 阶段（D-01 + D-15 + D-18 Task 5）。

LLM 技能抽取 + PG 持久化。按 D-15 发 3 子步骤事件：extract / normalize / persist。
本模块从 executor.execute_import 迁出；executor.py 保留兼容重导出（D-11）。
Phase 03 Plan 03 拆分：`_update_source_after_import` 辅助随阶段迁入本模块。
"""
from __future__ import annotations

import time
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from app.core.pipeline.stages.common import (
    PipelineStageError,
    get_session_factory,
    publish_stage_progress,
    run_async,
)


def _update_source_after_import(run_id: str, valid_count: int) -> None:
    """execute_import 完成后刷新 DataSourceRecord 质量统计。

    D4 fix (2026-08-12): 原实现查遗留死表 raw_jd_records + `source_platform = ds.name`
    精确匹配 + 朴素公式 `min(extracted/100, 1.0)` —— 三处叠加导致把 sync_source_quality
    （D3 真实来源，从 jd_raw 聚合）已正确回写的 valid_records/avg_quality_score **清零**
    （匹配失败 → extracted=0 → 全源质量归 0）。此处改为直接委托 sync_source_quality：
    jd_raw 是唯一真实采集数据源，valid/quality/dup/total/last_crawl_at 全部由它聚合回写。
    """
    async def _update():
        from app.core.pipeline.source_quality_sync import sync_source_quality

        session_factory = get_session_factory()
        async with session_factory() as session:
            await sync_source_quality(session)
            logger.info("_update_source_after_import: stats refreshed via sync_source_quality (run_id={})", run_id)
    run_async(_update())


def execute_import(run_id: str) -> dict[str, Any]:
    """执行 import 阶段：LLM 抽取技能 + 持久化。"""
    from loguru import logger

    from app.tasks.stage3_services import run_batch_extract_jd

    processed = 0
 # 2026-08-14 门禁修复: total 原仅在 DB 查询成功后赋值（len(jd_texts)），
 # 而 except/finally 返回路径无条件引用它 → DB 不可达时 UnboundLocalError。
 # 提前初始化为 0，失败路径返回 {current_activity: 无可提取记录} 优雅降级。
    total = 0
    errors: list[str] = []
    extracted_skills_sample: list[dict[str, Any]] = []
    start = time.monotonic()
 # 2026-08-16: stage budget (independent of Celery soft_time_limit).
    from app.config import settings as _settings
    stage_budget_seconds = max(_settings.pipeline_stage_timeout - 300, 60)

    run_async(publish_stage_progress(
        run_id, "import", "running", progress=0.0,
        current_activity="正在加载已清洗的JD...", elapsed_ms=0,
        sub_step="extract",
    ))

    try:
        from crawler.persistence.database import get_jd_raw_session
        from crawler.persistence.models import JdRaw, JdStatus

 # 2026-08-16 fix: 不在查询时提前标记 extracted —— 原实现 (L85) 在 LLM 抽取
 # 之前就把 jd.status 改为 extracted 并 commit, 一旦抽取失败/超时, 这些 JD
 # 既没成功入库也不会被下次 run 重试 (cleaned=0 数据丢失)。
 # 现改为: 只收集 (id, text, title), 循环内抽取成功后收集 success_ids,
 # 循环结束后统一把成功的标记为 extracted; 失败的保持 cleaned 可重试。
        with get_jd_raw_session() as s:
            from app.config import settings

            clean_jds = (
                s.query(JdRaw)
                .filter(JdRaw.status == JdStatus.cleaned)
                .limit(settings.pipeline_import_batch_size)
                .all()
            )
            jd_items = [
                (jd.id, jd.clean_text, jd.job_title)
                for jd in clean_jds
                if jd.clean_text
            ]

            total = len(jd_items)
            run_async(publish_stage_progress(
                run_id, "import", "running", progress=0.1,
                current_activity=f"待提取: {total} 条 (LLM: 技能识别 + 标准化 + 验证)",
                records_processed=0,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                sub_step="extract",
            ))

 # : normalize 子步骤事件
        run_async(publish_stage_progress(
            run_id, "import", "running", progress=0.15,
            current_activity=f"技能归一化中: {total} 条记录",
            records_processed=0,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            sub_step="normalize",
        ))

        success_ids: list[Any] = []
        for idx, (jd_id, text, title) in enumerate(jd_items):
 # 2026-08-16: stage budget check — break early when single LLM endpoint hangs
            elapsed_sec = time.monotonic() - start
            if elapsed_sec > stage_budget_seconds:
                msg = f"Stage budget exceeded ({elapsed_sec:.0f}s > {stage_budget_seconds}s); processed {processed}/{total}"
                logger.warning("import stage {}: {}", run_id, msg)
                errors.append(msg)
                run_async(publish_stage_progress(
                    run_id, "import", "running",
                    progress=0.15 + 0.8 * (idx / max(total, 1)),
                    records_processed=processed,
                    current_activity=f"Stage budget exceeded ({elapsed_sec:.0f}s)",
                    elapsed_ms=int(elapsed_sec * 1000),
                    sub_step="persist",
                ))
                break
            try:
 # : persist 子步骤事件 (LLM 抽取完成 = 持久化就绪)
 # D5 fix: 传 JD 标题作为 position_name 回退（LLM 未返回岗位名时不再落 Unknown Position）
                result = run_async(run_batch_extract_jd(text, job_title=title))
                if result.get("status") == "completed":
                    processed += 1
                    success_ids.append(jd_id)
                    if result.get("data", {}).get("required_skills"):
                        for sk in result["data"]["required_skills"][:3]:
                            extracted_skills_sample.append({
                                "title": title[:40] if title else "未命名",
                                "skill": sk.get("name", ""),
                                "category": sk.get("category", ""),
                            })
                else:
                    errors.append(f"extraction failed: {result.get('error', 'unknown')}")

 # 2026-08-16: progress every record, not every 3rd (so UI sees activity)
                run_async(publish_stage_progress(
                    run_id, "import", "running",
                    progress=0.15 + 0.8 * ((idx + 1) / max(total, 1)),
                    records_processed=processed,
                    current_activity=f"LLM 提取 {idx + 1}/{total} 条 - 当前: {title[:30] if title else '...'}",
                    recent_samples=extracted_skills_sample[-5:],
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                    sub_step="persist",  # D-15: persist 期间
                ))
            except PipelineStageError:
                raise
            except SoftTimeLimitExceeded:
                logger.warning("import stage {}: SoftTimeLimitExceeded, breaking", run_id)
                errors.append("Celery soft_time_limit reached")
                break
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.opt(exception=True).warning("JD extraction failed in import stage: {}", exc)

 # 2026-08-16 fix: 循环结束后才把抽取成功的 JD 标记为 extracted。
 # 失败的保持 cleaned, 下次 run 可重试 (原实现提前标记导致失败 JD 数据丢失)。
        if success_ids:
            with get_jd_raw_session() as s:
                from sqlalchemy import update

                s.execute(
                    update(JdRaw)
                    .where(JdRaw.id.in_(success_ids))
                    .values(status=JdStatus.extracted)
                )
                s.commit()
            logger.info(
                "import stage {}: marked {} JDs as extracted ({} failed/skipped kept cleaned)",
                run_id, len(success_ids), total - len(success_ids),
            )

        run_async(publish_stage_progress(
            run_id, "import", "completed", progress=1.0,
            records_processed=processed,
            current_activity=f"提取完成: {processed}/{total} 条 JD 成功提取技能",
            recent_samples=extracted_skills_sample[-5:],
            elapsed_ms=int((time.monotonic() - start) * 1000),
            message=f"LLM 提取完成: {processed}/{total} 成功",
        ))
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"import failed: {exc}")
        logger.opt(exception=True).error("Import stage failed: {}", exc)
        run_async(publish_stage_progress(
            run_id, "import", "failed", current_activity=f"提取失败: {exc}",
        ))
    finally:
 # SOURCE-03: execute_import 后更新 valid_records (UAT 修复)
        try:
            _update_source_after_import(run_id, processed)
        except PipelineStageError:
            raise
        except Exception as exc:
            logger.warning("_update_source_after_import failed (non-fatal): {}", exc)

 # : 阶段末 PG↔Neo4j 一致性告警（仅日志，不阻断不改数据）
        try:
            from app.services.pipeline_consistency import check_pg_neo4j_consistency

            run_async(check_pg_neo4j_consistency(run_id))
        except Exception as exc:
            logger.warning("pipeline_consistency check failed (non-fatal): {}", exc)

    return {
        "records_processed": processed,
        "errors": errors,
        "extracted_samples": extracted_skills_sample[-5:],
 # 修复: return 补 current_activity（DB 快照持久化）
        "current_activity": (
            f"提取完成: {processed}/{total} 条 JD 成功提取技能"
            if total
            else "无可提取记录"
        ),
 # D8 fix: 键名与 _mark_stage_completed 对齐（原 extracted_samples 不被消费 →
 # 详情抽屉/阶段展开看不到抽取的岗位/技能样本）；sub_breakdown 补成功/失败分解
        "recent_samples": extracted_skills_sample[-5:],
        "sub_breakdown": {
            "成功抽取": processed,
            "失败": len(errors),
        },
    }


__all__ = ["_update_source_after_import", "execute_import"]
