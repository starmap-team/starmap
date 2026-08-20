"""Pipeline import 阶段（D-01 + D-15 + D-18 Task 5）。

LLM 技能抽取 + PG 持久化。按 D-15 发 3 子步骤事件：extract / normalize / persist。
本模块从 executor.execute_import 迁出；executor.py 保留兼容重导出（D-11）。
Phase 03 Plan 03 拆分：`_update_source_after_import` 辅助随阶段迁入本模块。
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from loguru import logger

from app.core.pipeline.stages.common import (
    PipelineStageError,
    get_session_factory,
    publish_stage_progress,
    run_async,
)


def _persist_progress(
    run_id: str,
    *,
    status: str,
    progress: float,
    records_processed: int = 0,
    current_activity: str = "",
    recent_samples: list[dict] | None = None,
    sub_breakdown: dict[str, int] | None = None,
    elapsed_ms: int = 0,
) -> None:
    """进度事件除 Redis pub/sub 外，同步写入 pipeline_runs.stages DB 快照。

    2026-08-21 (P0-1): publish_stage_progress 只发 Redis，前端轮询/刷新/详情
    抽屉读的是 DB 快照 → import 进行中 progress 恒 0、activity 恒空，用户
    误判"卡住"。本函数把同一进度事件落 DB（update_stage_status 已支持这些
    字段），SSE 断开/轮询模式下也能看到实时进度。

    注意: 不用 run_async()（每次新建 loop + dispose engine 太重，循环内每条
    调用会产生 ~60 次 engine 重建）；直接用同步 SQLAlchemy 写，开销极小。
    """
    from crawler.persistence.database import get_jd_raw_session

    from app.core.pipeline.orchestrator import _stage_index
    from app.models.pipeline_models import PipelineRun

    try:
        with get_jd_raw_session() as s:  # 复用 crawler 的同步 engine（同库）
            # jd_raw session 绑定的是 crawler engine，pipeline_runs 在同一 PG。
            # 直接用该 session 执行 UPDATE pipeline_runs SET stages=...
            run = s.get(PipelineRun, run_id)
            if run is None or not run.stages:
                return
            stages: list[dict] = list(run.stages)
            idx = _stage_index(stages, "import")
            stage = stages[idx]
            stage["status"] = status
            stage["progress"] = progress
            stage["records_processed"] = records_processed
            if current_activity:
                stage["current_activity"] = current_activity
            if recent_samples is not None:
                stage["recent_samples"] = list(recent_samples)[-10:]
            if sub_breakdown is not None:
                stage["sub_breakdown"] = sub_breakdown
            if elapsed_ms:
                stage["elapsed_ms"] = elapsed_ms
            if status in ("completed", "failed"):
                from datetime import UTC, datetime

                stage["completed_at"] = datetime.now(UTC).isoformat()
            run.stages = stages
            # JSON 列 in-place 修改不会被 SQLAlchemy 自动检测为 dirty
            # （crawler session autoflush=False）→ 必须 flag_modified 强制 UPDATE
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(run, "stages")
            s.commit()
    except Exception as exc:
        # 进度持久化失败不阻断抽取主流程（graceful degradation）
        logger.warning("_persist_progress failed (non-fatal): {}", exc)


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

    # P0-1: 进度事件同时写 Redis(SSE) + DB 快照 —— 轮询/刷新也能看到实时进度
    _persist_progress(
        run_id, status="running", progress=0.0,
        current_activity="正在加载已清洗的JD...", elapsed_ms=0,
    )
    run_async(publish_stage_progress(
        run_id, "import", "running", progress=0.0,
        current_activity="正在加载已清洗的JD...", elapsed_ms=0,
        sub_step="extract",
    ))

    try:
        from crawler.persistence.database import get_jd_raw_session
        from crawler.persistence.models import JdRaw, JdStatus

        # 2026-08-20 (修复 B2): 抽取前不标记 extracted —— 此前在 LLM 抽取前就把
        # status 置为 extracted，LLM 失败（不可用/超时）时记录永远停在 extracted 且
        # 无抽取结果，永不重试（103 条 extracted 但 jd_extraction_records 仅 6 条根因）。
        # 改为：先收集 cleaned 记录，抽取成功后按 id 后置标记 extracted。
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
            pending_ids: list[int] = []
            for jd in clean_jds:
                if jd.clean_text:
                    jd_texts.append(jd.clean_text)
                    jd_titles.append(jd.job_title)
                    pending_ids.append(jd.id)
            # 2026-08-20 (debug 修复): 全局待处理总数 —— 进度口径改为
            # "已抽取/全局待处理"，而非每轮 batch 的局部进度（每轮 200 条从 0 开始，
            # run 跑 8 小时仍显示 0% 的根因）。
            global_pending = s.query(JdRaw).filter(JdRaw.status == JdStatus.cleaned).count()
            s.commit()

            total = len(jd_texts)
            total_global = max(global_pending, total)
            _persist_progress(
                run_id, status="running", progress=0.1,
                current_activity=(
                    f"待提取: 本轮 {total} 条 / 全局待处理 {total_global} 条 "
                    f"(LLM: 技能识别 + 标准化 + 验证)"
                ),
                records_processed=0,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
            run_async(publish_stage_progress(
                run_id, "import", "running", progress=0.1,
                current_activity=(
                    f"待提取: 本轮 {total} 条 / 全局待处理 {total_global} 条 "
                    f"(LLM: 技能识别 + 标准化 + 验证)"
                ),
                records_processed=0,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                sub_step="extract",
            ))

        # D-15: normalize 子步骤事件
        _persist_progress(
            run_id, status="running", progress=0.15,
            current_activity=f"技能归一化中: {total} 条记录",
            records_processed=0,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )
        run_async(publish_stage_progress(
            run_id, "import", "running", progress=0.15,
            current_activity=f"技能归一化中: {total} 条记录",
            records_processed=0,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            sub_step="normalize",
        ))

        # 2026-08-21 (阶段预算修复): celery hard_time_limit=1800s，而单条 JD 抽取
        # 最坏可达 ~180s+（fallback 链）+ anti-hallucination 二次 LLM。盲目循环
        # 200 条必然撞 hard limit 被 SIGKILL → 阶段永远卡 running、本批 0 成功。
        # 按"阶段剩余时间预算"提前截断：处理到接近 soft limit 就停止本轮，
        # 剩余 cleaned 记录留给下一次 run（幂等，不丢不重）。
        # 预算 = soft_time_limit - 启动损耗 - 收尾余量；至少允许处理 1 条。
        from app.config import settings

        soft_limit = getattr(settings, "pipeline_stage_timeout", 1800) - 30
        budget_seconds = max(soft_limit - 20, 30)
        batch_start_wall = time.monotonic()
        planned = total
        if total > 1:
            per_item_budget = max(
                (budget_seconds - 30) / total,  # 均摊预算
                25.0,  # 单条最低 25s（qwen-plus 实测 ~25s/条，避免 0 条可跑）
            )
            planned = max(1, min(total, int(budget_seconds / per_item_budget)))
        if planned < total:
            logger.warning(
                "Import stage budget: {}s stage budget → 本轮只处理 {}/{} 条，"
                "其余留待后续 run（避免撞 hard limit 被 SIGKILL）",
                budget_seconds, planned, total,
            )

        success_ids: list[int] = []
        # Phase 27 (qwen-plus 资源包优化): 同批内 content_hash 重复的 JD 复用首次抽取结果,
        # 避免同一 source 抓回完全相同内容时重复调 LLM。
        # 注意:仅去重本批 (in-memory dict),不跨批/不跨 run,保留跨批独立去重走 PG content_hash 唯一索引。
        def _extract_one(idx: int, text: str, title: str) -> dict[str, Any]:
            content_hash = hashlib.sha256(
                (text or "").encode("utf-8", errors="ignore"),
            ).hexdigest()
            if content_hash in _cached_results:
                # 同批内重复 → 复用首次抽取结果
                reused = dict(_cached_results[content_hash])
                reused.setdefault("warnings", []).append(
                    "in-batch dedup: same content as a prior JD in this batch",
                )
                return reused
            # D-15: persist 子步骤事件 (LLM 抽取完成 = 持久化就绪)
            # D5 fix: 传 JD 标题作为 position_name 回退（LLM 未返回岗位名时不再落 Unknown Position）
            result = run_async(run_batch_extract_jd(text, job_title=title))
            # 缓存"成功完成"的抽取结果,避免批内再次重复调 LLM。
            # 失败/错误结果不缓存(让下一条同 hash 仍能尝试 LLM)。
            if result.get("status") == "completed":
                _cached_results[content_hash] = result
            return result

        _cached_results: dict[str, dict] = {}
        for idx, (text, title) in enumerate(zip(jd_texts, jd_titles, strict=False)):
            if idx >= planned:
                break
            # 单条前检查剩余预算：若所剩时间不足以完成一条抽取（含 fallback），
            # 提前结束本轮，避免在循环中途被 hard limit 杀（阶段状态永远 running）。
            elapsed_here = time.monotonic() - batch_start_wall
            remaining = budget_seconds - elapsed_here
            if remaining < 30 and idx > 0:
                logger.warning(
                    "Import stage budget exhausted at {}/{} (remaining={:.0f}s) — "
                    "stop this round, {} JD(s) kept as cleaned for next run",
                    idx, total, remaining, total - idx,
                )
                break
            try:
                result = _extract_one(idx, text, title)
                if result.get("status") == "completed":
                    processed += 1
                    if idx < len(pending_ids):
                        success_ids.append(pending_ids[idx])
                    if result.get("data", {}).get("required_skills"):
                        for sk in result["data"]["required_skills"][:3]:
                            extracted_skills_sample.append({
                                "title": title[:40] if title else "未命名",
                                "skill": sk.get("name", ""),
                                "category": sk.get("category", ""),
                            })
                else:
                    errors.append(f"extraction failed: {result.get('error', 'unknown')}")

                # 2026-08-20 (debug 修复): 每条都推送进度 —— 此前每 3 条才发一次
                # （45-90s 间隔），LLM 逐条抽取 15-30s/条时前端感知为卡死。
                # 进度用全局口径：已抽取(processed) / 全局待处理(total_global)。
                # P0-1: 同事件写 DB 快照，轮询/刷新也可见实时进度。
                _persist_progress(
                    run_id, status="running",
                    progress=0.15 + 0.8 * ((processed + 1) / max(total_global, 1)),
                    records_processed=processed,
                    current_activity=(
                        f"LLM 提取 {idx + 1}/{total} 条(本轮) - 当前: {title[:30] if title else '...'}"
                        f"（全局已成功 {processed}/{total_global} 条）"
                    ),
                    recent_samples=extracted_skills_sample[-5:],
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
                run_async(publish_stage_progress(
                    run_id, "import", "running",
                    progress=0.15 + 0.8 * ((processed + 1) / max(total_global, 1)),
                    records_processed=processed,
                    current_activity=(
                        f"LLM 提取 {idx + 1}/{total} 条(本轮) - 当前: {title[:30] if title else '...'}"
                        f"（全局已成功 {processed}/{total_global} 条）"
                    ),
                    recent_samples=extracted_skills_sample[-5:],
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                    sub_step="persist",  # D-15: persist 期间
                ))
            except PipelineStageError:
                raise
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.opt(exception=True).warning("JD extraction failed in import stage: {}", exc)

        # 后置标记：仅抽取成功的记录置 extracted（失败保留 cleaned 可重试）
        if success_ids:
            with get_jd_raw_session() as s:
                s.query(JdRaw).filter(JdRaw.id.in_(success_ids)).update(
                    {JdRaw.status: JdStatus.extracted},
                    synchronize_session=False,
                )
                s.commit()
            logger.info(
                "Import stage: marked {} JD(s) as extracted ({} failed kept as cleaned)",
                len(success_ids), total - len(success_ids),
            )

        # P0-1 + P1-4: 完成事件写 DB 快照 + 报告"本次 X / 剩余 Z 待续"
        remaining = max(total_global - processed, 0)
        completion_activity = (
            f"本轮完成: 成功 {processed}/{total} 条"
            + (f"，剩余 {remaining} 条待续跑（继续处理即可）" if remaining > 0 else "，全部处理完成")
        )
        _persist_progress(
            run_id, status="completed", progress=1.0,
            records_processed=processed,
            current_activity=completion_activity,
            recent_samples=extracted_skills_sample[-5:],
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )
        run_async(publish_stage_progress(
            run_id, "import", "completed", progress=1.0,
            records_processed=processed,
            current_activity=completion_activity,
            recent_samples=extracted_skills_sample[-5:],
            elapsed_ms=int((time.monotonic() - start) * 1000),
            message=f"LLM 提取完成: 本轮 {processed}/{total} 成功",
        ))
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"import failed: {exc}")
        logger.opt(exception=True).error("Import stage failed: {}", exc)
        _persist_progress(run_id, status="failed", progress=0.0, current_activity=f"提取失败: {exc}")
        run_async(publish_stage_progress(
            run_id, "import", "failed", current_activity=f"提取失败: {exc}",
        ))
    finally:
        # Phase 2 SOURCE-03: execute_import 后更新 valid_records (UAT 修复)
        try:
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

    return {
        "records_processed": processed,
        "errors": errors,
        "extracted_samples": extracted_skills_sample[-5:],
        # Phase 19 修复: return 补 current_activity（DB 快照持久化）
        # P1-4: 报告剩余待续数，让"完成但没做完"一目了然
        "current_activity": (
            f"本轮完成: 成功 {processed}/{total} 条"
            + (f"，剩余 {max(total_global - processed, 0)} 条待续跑" if total else "")
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
