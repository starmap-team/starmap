"""Pipeline import 阶段（D-01 + D-15 + D-18 Task 5）。

LLM 技能抽取 + PG 持久化。按 D-15 发 3 子步骤事件：extract / normalize / persist。
本模块从 executor.execute_import 迁出；executor.py 保留兼容重导出（D-11）。
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


def execute_import(run_id: str) -> dict[str, Any]:
    """执行 import 阶段：LLM 抽取技能 + 持久化。"""
    from app.tasks.stage3_services import run_batch_extract_jd

    processed = 0
    errors: list[str] = []
    extracted_skills_sample: list[dict[str, Any]] = []
    start = time.monotonic()

    run_async(publish_stage_progress(
        run_id, "import", "running", progress=0.0,
        current_activity="正在加载已清洗的JD...", elapsed_ms=0,
        sub_step="extract",
    ))

    try:
        from crawler.persistence.database import get_jd_raw_session
        from crawler.persistence.models import JdRaw, JdStatus

        with get_jd_raw_session() as s:
            from app.config import settings

            clean_jds = (
                s.query(JdRaw)
                .filter(JdRaw.status == JdStatus.cleaned)
                .limit(settings.pipeline_import_batch_size)
                .all()
            )
            jd_texts = []
            jd_titles = []
            for jd in clean_jds:
                if jd.clean_text:
                    jd_texts.append(jd.clean_text)
                    jd_titles.append(jd.job_title)
                    jd.status = JdStatus.extracted
            s.commit()

            total = len(jd_texts)
            run_async(publish_stage_progress(
                run_id, "import", "running", progress=0.1,
                current_activity=f"待提取: {total} 条 (LLM: 技能识别 + 标准化 + 验证)",
                records_processed=0,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                sub_step="extract",
            ))

        # D-15: normalize 子步骤事件
        run_async(publish_stage_progress(
            run_id, "import", "running", progress=0.15,
            current_activity=f"技能归一化中: {total} 条记录",
            records_processed=0,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            sub_step="normalize",
        ))

        for idx, (text, title) in enumerate(zip(jd_texts, jd_titles, strict=False)):
            try:
                # D-15: persist 子步骤事件 (LLM 抽取完成 = 持久化就绪)
                result = run_async(run_batch_extract_jd(text))
                if result.get("status") == "completed":
                    processed += 1
                    if result.get("data", {}).get("required_skills"):
                        for sk in result["data"]["required_skills"][:3]:
                            extracted_skills_sample.append({
                                "title": title[:40] if title else "未命名",
                                "skill": sk.get("name", ""),
                                "category": sk.get("category", ""),
                            })
                else:
                    errors.append(f"extraction failed: {result.get('error', 'unknown')}")

                if idx > 0 and idx % 3 == 0:
                    run_async(publish_stage_progress(
                        run_id, "import", "running",
                        progress=0.15 + 0.8 * (idx / max(total, 1)),
                        records_processed=processed,
                        current_activity=f"LLM 提取 {idx}/{total} 条 - 当前: {title[:30] if title else '...'}",
                        recent_samples=extracted_skills_sample[-5:],
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                        sub_step="persist",  # D-15: persist 期间
                    ))
            except PipelineStageError:
                raise
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.opt(exception=True).warning("JD extraction failed in import stage: {}", exc)

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
        # Phase 2 SOURCE-03: execute_import 后更新 valid_records (UAT 修复)
        try:
            from app.core.pipeline.executor import _update_source_after_import

            _update_source_after_import(run_id, processed)
        except PipelineStageError:
            raise
        except Exception as exc:
            logger.warning("_update_source_after_import failed (non-fatal): {}", exc)

        # D-06: 阶段末 PG↔Neo4j 一致性告警（仅日志，不阻断不改数据）
        try:
            from app.services.pipeline_consistency import check_pg_neo4j_consistency

            run_async(check_pg_neo4j_consistency(run_id))
        except Exception as exc:
            logger.warning("pipeline_consistency check failed (non-fatal): {}", exc)

    return {"records_processed": processed, "errors": errors, "extracted_samples": extracted_skills_sample[-5:]}


__all__ = ["execute_import"]
