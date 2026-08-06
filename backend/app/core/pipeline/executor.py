"""Pipeline execution service — bridges DAG orchestrator to Celery tasks.

This module implements the DAG execution loop:
1. Create a PipelineRun via orchestrator
2. Dispatch ready stages to Celery tasks
3. Each Celery task calls back into advance_pipeline on completion
4. advance_pipeline updates stage status and dispatches next ready stages
5. When all stages are done, complete the run

Progress is broadcast via Redis pub/sub for SSE consumption.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select, update

from app.core.dashboard.sse_broadcaster import publish_event
from app.core.pipeline.orchestrator import (
    OPTIONAL_STAGES,
    STAGE_DEPS,
    RunStatus,
    StageName,
    StageStatus,
    all_stages_done,
    create_run,
    get_failed_stages,
    get_ready_stages,
    update_stage_status,
)
from app.db.session import get_session_factory
from app.exceptions import PipelineStageError

# 2026-08-07 (B2 修复): 共享 spider 注册表 — 提取为模块常量,
# executor 与单源调度端点共用; 补入 juejin/remoteok (PLAN-002/003 落地后遗漏注册)
SPIDER_REGISTRY: dict[str, Any] = {
    "v2ex": None,  # 延迟导入避免循环
}


def build_spider_registry() -> dict[str, Any]:
    """构建真实 spider 注册表 (B2: 含 juejin/remoteok, 2026-08-07 补)."""
    from crawler.spiders import arbeitnow, jobicy, juejin, remoteok, weworkremotely
    from crawler.spiders.v2ex_remote import run_sync as v2ex_sync

    return {
        "v2ex": v2ex_sync,
        "remotive": v2ex_sync,  # v2ex_remote spider 同时覆盖 V2EX + Remotive
        "arbeitnow": arbeitnow.run_sync,
        "jobicy": jobicy.run_sync,
        "weworkremotely": weworkremotely.run_sync,
        "juejin": juejin.run_sync,    # PLAN-002: D5 非结构化源
        "remoteok": remoteok.run_sync,  # PLAN-003: 英文 JD 源
    }
from app.models.pipeline_models import PipelineRun
from app.services.resources import resources as app_resources

# ---------------------------------------------------------------------------
# SSE progress helpers
# ---------------------------------------------------------------------------

async def _publish_stage_progress(
    run_id: str,
    stage_name: str,
    status: str,
    progress: float = 0.0,
    records_processed: int = 0,
    message: str = "",
    *,
    current_activity: str = "",
    recent_samples: list[dict[str, Any]] | None = None,
    sub_breakdown: dict[str, int] | None = None,
    elapsed_ms: int = 0,
) -> None:
    """Broadcast a pipeline stage progress event via Redis pub/sub.

    Phase 3.7: 丰富数据载荷 — 前端时间线能展示
    - current_activity: 当前正在做的具体事 (e.g. "正在爬取 BOSS直聘: python 工程师 - 第3页")
    - recent_samples: 最近处理的样本 (URL/技能名/图节点 等)
    - sub_breakdown: 子项分解 (e.g. {"bosszhipin": 12, "51job": 5})
    - elapsed_ms: 已运行毫秒数（用于 ETA 估算）
    """
    redis = app_resources.redis_client
    await publish_event(redis, "pipeline_update", {
        "run_id": run_id,
        "stage": stage_name,
        "status": status,
        "progress": progress,
        "records_processed": records_processed,
        "message": message,
        "current_activity": current_activity,
        "recent_samples": recent_samples or [],
        "sub_breakdown": sub_breakdown or {},
        "elapsed_ms": elapsed_ms,
    })


# ---------------------------------------------------------------------------
# Stage execution functions (sync, called from Celery workers)
# ---------------------------------------------------------------------------

from app.utils.async_helpers import run_async as _run_async  # noqa: E402

# ponytail: removed duplicate _run_async; reusing utils.async_helpers


def execute_crawl(run_id: str, run_type: str) -> dict[str, Any]:
    """Execute the crawl stage: run spiders and upsert JDs into jd_raw.

    Phase 2 AUTHORITY-03: Skip paused data sources.

    Multi-platform dispatch (Phase 3): reads per-source config from DataSourceRecord,
    mapping platform→spider via spider_registry. Falls back to boss if no platform
    configured. Each spider runs independently with error isolation.

    Phase 3.7: 实时进度 — 报告每个数据源爬取中的活动 + URL 样本
    Phase 3.8.7: 已移除错误的 _run_async_with_timeout (sync fn 不能当协程传)
    """
    import time

    # 2026-08-07 修复 (B1): import 失败(如 celery 容器缺 psycopg) 必须回写 run 状态,
    # 否则 run/stage 永远卡 running 0%, 用户看不到失败原因
    try:
        from crawler.persistence import dao
        from crawler.persistence.models import JdStatus
        from crawler.spiders import arbeitnow, jobicy, weworkremotely
        from crawler.spiders.v2ex_remote import run_sync as v2ex_sync
    except Exception as exc:  # noqa: BLE001 — 依赖缺失是环境级失败, 必须显式标记
        _run_async(update_stage_status(run_id, "crawl", StageStatus.FAILED.value,
                                       errors=[f"crawler 依赖不可用: {exc}"]))
        logger.opt(exception=True).error("crawl stage deps unavailable: {}", exc)
        raise

    # Spider registry: platform name → run_sync function
    # PLAN-005/NEW-07: 注册真实 spider；移除 bosszhipin/51job/lagou 的误导映射
    # （真实性红线：禁止用其它源数据冒充平台数据；国内真链路见计划书 D17）
    spider_registry = build_spider_registry()

    # Phase 3.8.6: 确保 jd_raw 表存在 (未在 Pipeline 中调用 init_schema)
    try:
        dao.init_schema()
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.debug("init_schema call (non-fatal): {}", exc)
    default_platform = "v2ex"
    default_keyword = "python"

    # Phase 2 AUTHORITY-03: 跳过 paused 数据源
    _run_async(_skip_paused_sources_if_needed(run_id))

    # Load all active crawler source configs
    source_configs = _run_async(_get_crawl_configs(run_id))

    total_inserted = 0
    total_seen = 0
    errors: list[str] = []
    per_source_stats: dict[str, int] = {}
    recent_samples: list[dict[str, Any]] = []
    sub_breakdown: dict[str, int] = {}
    crawl_start = time.monotonic()

    if not source_configs:
        # Fallback: no configured sources → use v2ex/remotive with defaults
        default_max = 50 if run_type == "incremental" else 200
        logger.info(
            "No active crawler sources configured, falling back to default v2ex: "
            "keyword={}, max_count={}", default_keyword, default_max,
        )
        source_configs = [{
            "platform": default_platform,
            "keyword": default_keyword,
            "max_count": default_max,
            "source_name": "V2EX/Remotive (默认)",        }]

    total_sources = len(source_configs)
    for source_idx, cfg in enumerate(source_configs):
        platform = cfg.get("platform", default_platform)
        keyword = cfg.get("keyword", default_keyword)
        max_count = cfg.get(
            "max_count",
            50 if run_type == "incremental" else 200,
        )
        source_name = cfg.get("source_name", platform)

        # Phase 3.8.2: 跳过 disabled 源 (config 中 disabled=True)
        if cfg.get("disabled"):
            logger.info(
                "Source '{}' is disabled in config, skipping", source_name,
            )
            sub_breakdown[source_name] = -1  # -1 = disabled
            continue

        spider_fn = spider_registry.get(platform)

        if spider_fn is None:
            reason = f"无蜘蛛适配器: platform={platform} (source: {source_name})"
            logger.warning(reason)
            errors.append(reason)
            sub_breakdown[source_name] = -2  # -2 = no spider
            # Phase 3.8.2: 跳过时也广播状态
            _run_async(_publish_stage_progress(
                run_id, "crawl", "running",
                progress=source_idx / total_sources,
                records_processed=total_inserted,
                current_activity=f"⊘ 跳过 {source_name} (无蜘蛛: {platform})",
                sub_breakdown=sub_breakdown,
                recent_samples=recent_samples[-5:],
                elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
                message=f"跳过 {source_name}: 无蜘蛛",
            ))
            continue

        # Phase 3.7: 报告开始爬取此数据源
        _run_async(_publish_stage_progress(
            run_id, "crawl", "running",
            progress=source_idx / total_sources,
            records_processed=total_inserted,
            current_activity=f"正在爬取 {source_name} (平台: {platform}, 关键词: {keyword}, 目标: {max_count} 条)",
            recent_samples=recent_samples[-5:],
            sub_breakdown=sub_breakdown,
            elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
            message=f"开始爬取 {source_name}",
        ))

        try:
            logger.info(
                "Crawling source '{}' (platform={}, keyword={}, max_count={})",
                source_name, platform, keyword, max_count,
            )
            # Phase 3.8.7 FIX: 直接调用 sync spider
            # (之前的 _run_async_with_timeout 把 sync fn 返回值 [] 当协程 → 报 "a coroutine was expected")
            items = spider_fn(keyword=keyword, max_count=max_count)
            source_inserted = 0
            source_seen = 0
            for item_idx, it in enumerate(items):
                source_seen += 1
                total_seen += 1
                rec = {
                    "source_site": it["source_site"],
                    "source_url": it["source_url"],
                    "raw_html": it["raw_html"],
                    "clean_text": it["clean_text"],
                    "job_title": it["job_title"],
                    "company": it["company"],
                    "salary_min": it["salary_min"],
                    "salary_max": it["salary_max"],
                    "location": it["location"],
                    "publish_date": it["publish_date"],
                    "content_hash": it["content_hash"],
                    "status": JdStatus.raw,
                }
                r = dao.upsert_jd(rec)
                if r in ("inserted", "duplicate"):  # Phase 3.8.10: count dup too
                    source_inserted += 1
                    total_inserted += 1
                    # 收集最近样本（最多 10 个）用于实时预览
                    if len(recent_samples) >= 10:
                        recent_samples.pop(0)
                    recent_samples.append({
                        "title": it.get("job_title", "未命名"),
                        "company": it.get("company", ""),
                        "url": it.get("source_url", ""),
                        "source": it.get("source_site", platform),
                    })

                # Phase 3.7: 定期报告子进度（每 5 个 item）
                if item_idx > 0 and item_idx % 5 == 0:
                    sub_breakdown[source_name] = source_inserted
                    _run_async(_publish_stage_progress(
                        run_id, "crawl", "running",
                        progress=(source_idx + (item_idx + 1) / max(source_seen + (max_count - source_seen), max_count)) / total_sources,
                        records_processed=total_inserted,
                        current_activity=f"{source_name}: 正在处理第 {item_idx + 1} 条 - {it.get('job_title', '未命名')[:30]}",
                        recent_samples=recent_samples[-5:],
                        sub_breakdown=sub_breakdown,
                        elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
                        message=f"{source_name} 已采集 {source_seen} 条",
                    ))

            per_source_stats[source_name] = source_inserted
            sub_breakdown[source_name] = source_inserted
            logger.info(
                "Source '{}' crawl complete: {} items, {} inserted",
                source_name, len(items), source_inserted,
            )
        except PipelineStageError:
            raise
        except Exception as exc:
            err_msg = f"{source_name} ({platform}) crawl failed: {exc}"
            errors.append(err_msg)
            logger.opt(exception=True).error("Crawl stage {} failed: {}", source_name, exc)

    # Phase 3.7: 最终完成报告 (含每源统计)
    per_source_summary = []
    for name, count in sorted(sub_breakdown.items(), key=lambda x: (
        -1 if x[1] >= 0 else 0,  # 正常数据源优先
        -x[1] if x[1] >= 0 else x[1],  # 对正常值按数量降序
    )):
        if count == -1:
            per_source_summary.append(f"{name}: 已禁用")
        elif count == -2:
            per_source_summary.append(f"{name}: 无蜘蛛")
        elif count == 0:
            per_source_summary.append(f"{name}: 0 条")
        else:
            per_source_summary.append(f"{name}: {count} 条")

    _run_async(_publish_stage_progress(
        run_id, "crawl", "completed",
        progress=1.0,
        records_processed=total_inserted,
        current_activity=f"采集完成: 共 {total_seen} 条原始数据，新增 {total_inserted} 条入库",
        recent_samples=recent_samples[-5:],
        sub_breakdown=sub_breakdown,
        elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
        message=f"采集阶段完成: 总览={total_seen} 新增={total_inserted} | {'; '.join(per_source_summary[:5])}",
    ))

    # Phase 3.8.2: 当 0 记录时给出明确警告 (用户最关心的问题)
    if total_inserted == 0 and not errors:
        # 0 记录但无 errors → 爬虫被反爬或选择器失效
        warning_msg = (
            "⚠️ 爬虫采集完成但 0 条入库。可能原因: ① 平台反爬(stealth被识别) "
            "② 选择器失效(网站改版) ③ 数据源配置 max_count=0"
        )
        errors.append(warning_msg)
        logger.warning(warning_msg + f" sources_attempted={total_sources}, total_seen={total_seen}")
    elif total_inserted == 0 and errors:
        logger.warning(f"爬虫 0 记录: 已有 {len(errors)} 个 errors")

    # Phase 2 SOURCE-01: execute_crawl 后更新 DataSourceRecord (UAT 修复)
    try:
        _update_source_after_crawl(run_id, total_inserted)
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.warning("_update_source_after_crawl failed (non-fatal): {}", exc)

    return {
        "records_processed": total_inserted,
        "records_seen": total_seen,        # Phase 3.8.11: 区分抓到 vs 入库
        "errors": errors,
        "per_source": per_source_stats,
        "sub_breakdown": sub_breakdown,
        "recent_samples": recent_samples[-5:],
        "per_source_summary": per_source_summary,
        "current_activity": (
            f"采集完成: 共 {total_seen} 条原始数据，新增 {total_inserted} 条入库 | {'; '.join(per_source_summary[:5])}"
            if total_inserted > 0 else
            f"⚠️ 0 条入库 (尝试 {total_sources} 源, 失败 {len(errors)} 个) | {'; '.join(per_source_summary[:5])}"
        ),
    }


def execute_dedup(run_id: str) -> dict[str, Any]:
    """Execute dedup stage: two-pass dedup on jd_raw records.

    Pass 1 — exact dedup via Redis content-hash lookup (``dedup_service``).
    Pass 2 — fuzzy dedup via SimHash with character 3-grams (``dedup_service``).
    Falls back to the legacy crawler SimHash when Redis is unavailable.

    Phase 3.7: 实时进度 — 报告去重状态
    """
    import time

    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus

    processed = 0
    duplicates_found = 0
    errors: list[str] = []
    start = time.monotonic()

    # 报告启动
    _run_async(_publish_stage_progress(
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
                _run_async(_publish_stage_progress(
                    run_id, "dedup", "completed", progress=1.0,
                    records_processed=0, current_activity="无待去重记录",
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                ))
                return {"records_processed": 0, "errors": errors, "duplicates_found": 0}

            processed = len(raw_jds)
            _run_async(_publish_stage_progress(
                run_id, "dedup", "running",
                progress=0.1,
                records_processed=processed,
                current_activity=f"待去重: {processed} 条 (精确哈希比对 + SimHash 模糊匹配)",
                message=f"已加载 {processed} 条记录",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            ))

            # --- Two-pass dedup via dedup_service ---
            from app.services.dedup_service import dedup_jd_records

            redis_client = app_resources.redis_client

            def _get_clean_text(jd: Any) -> str:
                return jd.clean_text or ""

            unique_jds, dup_jds = _run_async(
                dedup_jd_records(
                    raw_jds,
                    text_getter=_get_clean_text,
                    redis_client=redis_client,
                    threshold=3,
                ),
            )

            # Separate exact vs fuzzy counts from the returned duplicates
            # (dedup_service returns both passes merged; we mark all as duplicate)
            dup_ids = {id(jd) for jd in dup_jds}
            for jd in raw_jds:
                if id(jd) in dup_ids:
                    jd.status = JdStatus.duplicate

            duplicates = len(dup_jds)
            duplicates_found = duplicates
            s.commit()

            _run_async(_publish_stage_progress(
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
        _run_async(_publish_stage_progress(
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

    return {"records_processed": processed, "errors": errors, "duplicates_found": duplicates_found}


def execute_clean(run_id: str) -> dict[str, Any]:
    """Execute clean stage: normalize and validate JD records.

    Phase 3.7: 实时进度 — 报告清洗状态
    """
    import time

    from crawler.persistence.database import get_jd_raw_session
    from crawler.persistence.models import JdRaw, JdStatus

    processed = 0
    errors: list[str] = []
    cleaned_titles: list[str] = []
    start = time.monotonic()

    _run_async(_publish_stage_progress(
        run_id, "clean", "running", progress=0.0,
        current_activity="正在加载待清洗记录...", elapsed_ms=0,
    ))

    try:
        with get_jd_raw_session() as s:
            # Clean raw JDs that passed dedup (status=raw means not duplicate)
            raw_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).all()
            total = len(raw_jds)
            _run_async(_publish_stage_progress(
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
                        # Try to extract title from text
                        first_line = jd.clean_text.split("\n")[0][:200]
                        jd.job_title = first_line or "Unknown"
                    if idx < 5:
                        cleaned_titles.append(jd.job_title[:60])
                processed += 1
                # 每处理 10 条报告一次
                if idx > 0 and idx % 10 == 0:
                    _run_async(_publish_stage_progress(
                        run_id, "clean", "running",
                        progress=0.1 + 0.8 * (idx / total),
                        records_processed=processed,
                        current_activity=f"已清洗 {idx}/{total} 条",
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                    ))
            s.commit()

            _run_async(_publish_stage_progress(
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
        _run_async(_publish_stage_progress(
            run_id, "clean", "failed", current_activity=f"清洗失败: {exc}",
        ))

    return {"records_processed": processed, "errors": errors}


def execute_import(run_id: str) -> dict[str, Any]:
    """Execute import stage: extract skills from JDs and persist to PostgreSQL + Neo4j.

    Phase 3.7: 实时进度 — 报告 LLM 提取状态 + 技能样本
    """
    import time

    from app.tasks.stage3_services import run_batch_extract_jd

    processed = 0
    errors: list[str] = []
    extracted_skills_sample: list[dict[str, Any]] = []
    start = time.monotonic()

    _run_async(_publish_stage_progress(
        run_id, "import", "running", progress=0.0,
        current_activity="正在加载已清洗的JD...", elapsed_ms=0,
    ))

    try:
        # Get cleaned JDs from jd_raw that haven't been extracted yet
        from crawler.persistence.database import get_jd_raw_session
        from crawler.persistence.models import JdRaw, JdStatus

        with get_jd_raw_session() as s:
            clean_jds = s.query(JdRaw).filter(JdRaw.status == JdStatus.raw).limit(100).all()
            jd_texts = []
            jd_titles = []
            for jd in clean_jds:
                if jd.clean_text:
                    jd_texts.append(jd.clean_text)
                    jd_titles.append(jd.job_title)
                    jd.status = JdStatus.extracted
            s.commit()

            total = len(jd_texts)
            _run_async(_publish_stage_progress(
                run_id, "import", "running", progress=0.1,
                current_activity=f"待提取: {total} 条 (LLM: 技能识别 + 标准化 + 验证)",
                records_processed=0,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            ))

        # Extract skills from each JD via LLM
        for idx, (text, title) in enumerate(zip(jd_texts, jd_titles, strict=False)):
            try:
                result = _run_async(run_batch_extract_jd(text))
                if result.get("status") == "completed":
                    processed += 1
                    # 收集样本技能
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
                    _run_async(_publish_stage_progress(
                        run_id, "import", "running",
                        progress=0.1 + 0.85 * (idx / total),
                        records_processed=processed,
                        current_activity=f"LLM 提取 {idx}/{total} 条 - 当前: {title[:30] if title else '...'}",
                        recent_samples=extracted_skills_sample[-5:],
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                    ))
            except PipelineStageError:
                raise
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.opt(exception=True).warning("JD extraction failed in import stage: {}", exc)

        _run_async(_publish_stage_progress(
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
        _run_async(_publish_stage_progress(
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

    return {"records_processed": processed, "errors": errors, "extracted_samples": extracted_skills_sample[-5:]}


def execute_graph_sync(run_id: str) -> dict[str, Any]:
    """Execute graph_sync stage: build Neo4j graph from extraction records.

    Phase 7 P0-1: outbox pattern — 写入 Neo4j 前创建 outbox 记录，防止 PG/Neo4j 数据漂移。
    """
    import time
    import uuid as _uuid

    from app.tasks.stage3_services import run_build_graph_from_extractions

    processed = 0
    errors: list[str] = []
    start = time.monotonic()

    _run_async(_publish_stage_progress(
        run_id, "graph_sync", "running", progress=0.0,
        current_activity="正在连接 Neo4j 并准备图谱同步...", elapsed_ms=0,
    ))

    # Phase 7 P0-1: Create outbox record BEFORE Neo4j write
    outbox_id = _uuid.uuid4()
    try:
        _run_async(_create_outbox_record(get_session_factory(), outbox_id, _uuid.UUID(run_id)))
    except PipelineStageError:
        raise
    except Exception as o_exc:
        logger.warning("graph_sync outbox create failed (non-fatal): {}", o_exc)

    try:
        result = _run_async(run_build_graph_from_extractions(limit=500))
        processed = result.get("processed", 0)
        triples_merged = result.get("triples_merged", 0)
        nodes = result.get("nodes_written", 0)
        edges = result.get("edges_written", 0)
        # Outbox: mark complete on success
        _run_async(_complete_outbox_record(get_session_factory(), outbox_id, triples_merged))
        _run_async(_publish_stage_progress(
            run_id, "graph_sync", "completed", progress=1.0,
            records_processed=processed,
            current_activity=f"图谱完成: {nodes}节点 {edges}关系 {triples_merged} triples",
            sub_breakdown={"节点": nodes, "关系": edges, "triples": triples_merged},
            elapsed_ms=int((time.monotonic() - start) * 1000),
        ))
        if result.get("status") != "completed":
            errors.append(f"graph sync incomplete: {result}")
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"graph_sync failed: {exc}")
        logger.opt(exception=True).error("Graph sync stage failed: {}", exc)
        # Outbox: mark failed for retry
        try:
            _run_async(_fail_outbox_record(get_session_factory(), outbox_id, str(exc)))
        except PipelineStageError:
            raise
        except Exception as o_err:
            logger.warning("outbox fail update error: {}", o_err)
        _run_async(_publish_stage_progress(
            run_id, "graph_sync", "failed", current_activity=f"图谱同步失败: {exc}",
        ))

    return {"records_processed": processed, "errors": errors, "outbox_id": str(outbox_id)}


def execute_timeseries(run_id: str) -> dict[str, Any]:
    """Execute timeseries stage: aggregate skill frequencies from extraction records."""

    processed = 0
    errors: list[str] = []

    try:
        result = _run_async(_run_timeseries_refresh())
        processed = result.get("windows_created", 0)
        skills_updated = result.get("skills_updated", 0)
        logger.info(
            "Timeseries stage: {} skills updated, {} windows created",
            skills_updated, processed,
        )
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"timeseries failed: {exc}")
        logger.opt(exception=True).error("Timeseries stage failed: {}", exc)

    return {"records_processed": processed, "errors": errors}


async def _run_timeseries_refresh() -> dict[str, Any]:
    """Async bridge for execute_timeseries to call refresh_skill_timeseries."""
    from app.services.timeseries_service import refresh_skill_timeseries

    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            return await refresh_skill_timeseries(session)


# ---------------------------------------------------------------------------
# Phase 2: DataSourceRecord 实时更新 (SOURCE-01/02/03)
# 这些函数从 sync Celery worker 调用，使用 _run_async 桥接 async DB
# ---------------------------------------------------------------------------

def _update_source_after_crawl(run_id: str, records_count: int) -> None:
    """execute_crawl 完成后更新 DataSourceRecord.total_records + last_crawl_at."""
    async def _update():
        session_factory = get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import text

            from app.models.pipeline_models import DataSourceRecord

            # 按 source_platform 分组计数
            result = await session.execute(
                text("SELECT source_platform, COUNT(*) as cnt FROM raw_jd_records GROUP BY source_platform")
            )
            rows = result.fetchall()
            for platform, cnt in rows:
                # 找对应 DataSourceRecord（按 name 匹配）
                ds_result = await session.execute(
                    select(DataSourceRecord).where(DataSourceRecord.name == platform)
                )
                ds = ds_result.scalar_one_or_none()
                if ds:
                    ds.total_records = (ds.total_records or 0) + int(cnt)
                    ds.last_crawl_at = datetime.now(UTC)
            await session.commit()
            logger.info("_update_source_after_crawl: updated {} sources for run_id={}", len(rows), run_id)
    _run_async(_update())


def _update_source_after_dedup(run_id: str, duplicates: int, total: int) -> None:
    """execute_dedup 完成后更新 DataSourceRecord.duplicate_rate.

    Looks up all active crawler DataSourceRecords and updates the
    duplicate_rate for each.  When only one source exists the update is
    unambiguous; when multiple exist, the same rate is applied to all
    (dedup operates across the whole raw_jd table).
    """
    async def _update():
        session_factory = get_session_factory()
        async with session_factory() as session:
            from app.models.pipeline_models import DataSourceRecord
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
    _run_async(_update())


def _update_source_after_import(run_id: str, valid_count: int) -> None:
    """execute_import 完成后更新 DataSourceRecord.valid_records + avg_quality_score."""
    async def _update():
        session_factory = get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import text

            from app.models.pipeline_models import DataSourceRecord

            # 重算所有 data_sources 的 avg_quality_score
            ds_list_result = await session.execute(
                select(DataSourceRecord)
            )
            all_ds = ds_list_result.scalars().all()
            for ds in all_ds:
                # 从 extraction_models 查询有效记录数（按 source_platform 匹配）
                rec_result = await session.execute(
                    text("SELECT COUNT(*) FROM raw_jd_records WHERE source_platform = :platform AND status = 'extracted'"),
                    {"platform": ds.name},
                )
                extracted = rec_result.scalar() or 0
                ds.valid_records = extracted
                ds.avg_quality_score = min(extracted / 100.0, 1.0) if extracted > 0 else 0.0

            await session.commit()
            logger.info("_update_source_after_import: updated valid_records for run_id={}", run_id)
    _run_async(_update())


async def _get_crawl_configs(run_id: str) -> list[dict[str, Any]]:
    """Load per-source crawl configurations from active DataSourceRecord(s).

    Returns a list of config dicts, each with: platform, keyword, max_count, source_name.
    Falls back to empty list if no active sources found (caller handles defaults).

    Each DataSourceRecord.config should contain:
        {"keyword": "python", "max_count": 50, "platform": "bosszhipin"}
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from app.models.pipeline_models import DataSourceRecord

            # PLAN-005: api/rss 源同样参与 crawl 阶段（Phase 15 修复在 rebase 中丢失，恢复）
            result = await session.execute(
                select(DataSourceRecord).where(
                    DataSourceRecord.source_type.in_(["crawler", "api", "rss"]),
                    DataSourceRecord.status == "active",
                )
            )
            sources = result.scalars().all()
            configs: list[dict[str, Any]] = []
            for ds in sources:
                if ds.config is None:
                    continue
                # Build per-source config: merge record-level metadata with config JSON
                cfg = dict(ds.config)
                cfg["source_name"] = ds.name
                cfg.setdefault("platform", cfg.get("source_site", "v2ex"))
                configs.append(cfg)
            if configs:
                logger.debug(
                    "Loaded crawl configs from {} active source(s)",
                    len(configs),
                )
            return configs
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.warning("_get_crawl_configs failed (non-fatal, using defaults): {}", exc)
    return []


async def _skip_paused_sources_if_needed(run_id: str) -> None:
    """Phase 2 AUTHORITY-03: Log paused sources (the actual skip happens in the spider call)."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select as sa_select

            from app.models.pipeline_models import DataSourceRecord
            paused = await session.execute(
                sa_select(DataSourceRecord).where(DataSourceRecord.status == "paused")
            )
            paused_sources = paused.scalars().all()
            if paused_sources:
                names = [s.name for s in paused_sources]
                logger.info("Skipping {} paused source(s) for run_id={}: {}", len(names), run_id, names)
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.warning("_skip_paused_sources_if_needed failed (non-fatal): {}", exc)


STAGE_EXECUTORS = {
    StageName.CRAWL.value: execute_crawl,
    StageName.DEDUP.value: execute_dedup,
    StageName.CLEAN.value: execute_clean,
    StageName.IMPORT.value: execute_import,
    StageName.GRAPH_SYNC.value: execute_graph_sync,
    StageName.TIMESERIES.value: execute_timeseries,
}


# ---------------------------------------------------------------------------
# DAG advance logic (async, updates DB + dispatches next Celery tasks)
# ---------------------------------------------------------------------------

async def advance_pipeline(run_id: uuid.UUID) -> None:
    """Check stage statuses and dispatch the next ready stages.

    Called after each stage completes (or fails). Handles:
    - Dispatching ready stages to Celery
    - Skipping optional stages whose deps failed
    - Completing the run when all stages are done

    Phase 1 D-04: STOP flag 检查 — if Redis flag `pipeline:stop:{run_id}` is set,
    skip all stage dispatch and don't complete the run (cancel_run 已经标记 cancelled).
    """
    # Phase 1 D-04: STOP flag 检查
    try:
        from app.core.pipeline.orchestrator import is_run_cancelled
        redis_client = app_resources.redis_client
        if await is_run_cancelled(redis_client, run_id):
            logger.info(
                "advance_pipeline run_id=%s: STOP flag set, skipping advance",
                run_id,
            )
            return
    except PipelineStageError:
        raise
    except Exception:
        logger.exception("advance_pipeline STOP flag check failed (continuing)")

    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return

            raw_stages = run.stages or []
            stages: list[dict[str, Any]] = raw_stages if isinstance(raw_stages, list) else []

            # Skip or fail stages whose deps failed
            # Phase 3.8.7: also fail required stages (not just skip optional ones)
            for s in stages:
                if s["status"] != StageStatus.PENDING.value:
                    continue
                deps = STAGE_DEPS.get(s["name"], [])
                any_dep_failed = any(
                    any(ds["name"] == d and ds["status"] == StageStatus.FAILED.value for ds in stages)
                    for d in deps
                )
                if any_dep_failed:
                    if s["name"] in OPTIONAL_STAGES:
                        s["status"] = StageStatus.SKIPPED.value
                    else:
                        # Phase 3.8.7 FIX: Required dep failed -> 标记下游 stage 为 failed
                        s["status"] = StageStatus.FAILED.value
                    s["completed_at"] = datetime.now(UTC).isoformat()
                    if s["name"] not in OPTIONAL_STAGES:
                        logger.warning(
                            "advance_pipeline: marking {} as FAILED (required dep failed)",
                            s["name"],
                        )

            # Check if all stages are done
            if all_stages_done(stages):
                failed = get_failed_stages(stages)
                total_records = sum(s.get("records_processed", 0) for s in stages)
                run_status = RunStatus.FAILED.value if failed else RunStatus.COMPLETED.value
                error_log = f"Failed stages: {failed}" if failed else None
                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == run_id)
                    .values(
                        stages=stages,
                        status=run_status,
                        completed_at=datetime.now(UTC),
                        total_records=total_records,
                        error_log=error_log,
                    )
                )
                # Broadcast completion
                await _publish_stage_progress(
                    str(run_id), "pipeline", run_status,
                    progress=1.0 if run_status == RunStatus.COMPLETED.value else 0.0,
                    message=f"Pipeline {run_status}",
                )
                return

            # Write back any skipped stage updates
            await session.execute(
                update(PipelineRun).where(PipelineRun.id == run_id).values(stages=stages)
            )

        # Dispatch ready stages (outside transaction so each dispatch is independent)
        ready = get_ready_stages(stages)
        logger.info(f"advance_pipeline run_id={run_id}: ready_stages={ready}")
        for stage_name in ready:
            # Mark as running
            logger.info(f"advance_pipeline run_id={run_id}: marking {stage_name} as RUNNING")
            await update_stage_status(session, run_id, stage_name, status=StageStatus.RUNNING.value)
            await session.commit()  # Phase 3.8 FIX: 显式 commit 确保 running 状态立即持久化
            logger.info(f"advance_pipeline run_id={run_id}: {stage_name} marked running and committed")
            await _publish_stage_progress(
                str(run_id), stage_name, StageStatus.RUNNING.value,
                progress=0.0, message=f"Stage {stage_name} started",
            )
            # Dispatch Celery task
            from app.tasks.celery_app import execute_pipeline_stage
            execute_pipeline_stage.delay(str(run_id), stage_name)


async def trigger_and_start(
    run_type: str = "full",
    selected_stages: list[str] | None = None,
) -> PipelineRun:
    """Create a pipeline run and start executing the first ready stage(s).

    Before creating a new run, cancels any existing runs stuck in 'running'
    status (older than 30 minutes) to prevent accumulation of orphan runs.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            # Cancel any stuck running runs older than 30 minutes
            from datetime import timedelta
            stuck = await session.execute(
                select(PipelineRun)
                .where(PipelineRun.status == "running")
                .where(PipelineRun.started_at < datetime.now(UTC) - timedelta(minutes=30))
            )
            for old_run in stuck.scalars().all():
                old_run.status = "cancelled"
                old_run.completed_at = datetime.now(UTC)
                logger.warning(
                    "Cancelled stuck pipeline run {} (started at {}, {:.1f}h old)",
                    old_run.id, old_run.started_at,
                    (datetime.now(UTC) - old_run.started_at).total_seconds() / 3600,
                )
            run = await create_run(session, run_type=run_type, selected_stages=selected_stages)
            run_id = run.id

    # Advance the DAG — dispatches first stage(s)
    await advance_pipeline(run_id)

    # Re-fetch and return
    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        return result.scalar_one()


async def retry_stage(run_id: uuid.UUID, stage_name: str) -> PipelineRun | None:
    """Reset a failed stage to PENDING and advance the pipeline."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Reset the stage
        await update_stage_status(
            session, run_id, stage_name,
            status=StageStatus.PENDING.value,
            errors=[],
            retry_count=0,
        )
    # Re-advance
    await advance_pipeline(run_id)
    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        return result.scalar_one_or_none()


async def resume_run(run_id: uuid.UUID) -> PipelineRun | None:
    """Resume a failed pipeline run by resetting all failed stages and advancing."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            return None

        stages = list(run.stages or [])
        for s in stages:
            if s["status"] == StageStatus.FAILED.value:
                s["status"] = StageStatus.PENDING.value
                s["errors"] = []
                s["retry_count"] = 0
                s["started_at"] = None
                s["completed_at"] = None

        # Reset run status to running
        run.status = RunStatus.RUNNING.value
        run.completed_at = None
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == run_id)
            .values(stages=stages, status=RunStatus.RUNNING.value, completed_at=None)
        )

    await advance_pipeline(run_id)

    async with session_factory() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        return result.scalar_one_or_none()


# ── Phase 7 P0-1: Graph Write Outbox helpers ──


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
    from datetime import UTC, datetime

    from app.models.pipeline_models import GraphWriteOutbox

    async with session_factory() as session:
        async with session.begin():
            record = GraphWriteOutbox(
                id=outbox_id,
                run_id=uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
                extraction_ids=extraction_ids or [],
                status="pending",
                created_at=datetime.now(UTC),
            )
            session.add(record)


async def _complete_outbox_record(
    session_factory: Any, outbox_id: uuid.UUID, triples_written: int,
) -> None:
    """Mark outbox record as completed after successful Neo4j write."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.models.pipeline_models import GraphWriteOutbox

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                update(GraphWriteOutbox)
                .where(GraphWriteOutbox.id == outbox_id)
                .values(status="completed", triples_written=triples_written, updated_at=datetime.now(UTC)),
            )


async def _fail_outbox_record(
    session_factory: Any, outbox_id: uuid.UUID, error_msg: str,
) -> None:
    """Mark outbox record as failed (will be retried on next pipeline run)."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.models.pipeline_models import GraphWriteOutbox

    async with session_factory() as session:
        async with session.begin():
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
