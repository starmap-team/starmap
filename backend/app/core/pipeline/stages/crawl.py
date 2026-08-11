"""Pipeline crawl 阶段（D-01 + D-15 + D-18 Task 4）。

按数据源/平台调度爬虫，写入 jd_raw。每启用的数据源发送 1 条 sub_step 事件（D-15）。
本模块从 executor.execute_crawl 迁出；executor.py 保留兼容重导出，存量调用方零改动（D-11）。
同时收纳 crawl 相关辅助（spider 注册表、crawl 配置加载、DataSourceRecord 更新）——
Phase 03 Plan 03 拆分：这些辅助原在 executor.py，随阶段迁入本模块。
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
    select,
)

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


def _update_source_after_crawl(run_id: str, records_count: int) -> None:
    """execute_crawl 完成后更新 DataSourceRecord.total_records + last_crawl_at.

    E20 fix: two critical bugs in the previous version:
      1. "cnt" was the *cumulative* raw_jd_records count for each platform,
         not the delta of THIS run. Calling sync N times added N× the
         existing total to DataSourceRecord.total_records (累加 bug).
      2. Match logic was too permissive — substring fallback would match
         unrelated DS rows, attributing Boss Zhipin crawls to ESCO Skills.

    Fix: filter raw_jd_records by `crawled_at >= run.started_at` so we
    only count the rows produced by THIS pipeline run. Use a strict
    two-step match (case-insensitive equality, then strip parens), no
    substring fallback.
    """
    async def _update():
        from sqlalchemy import text

        from app.models.pipeline_models import DataSourceRecord, PipelineRun

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. Find this run's start time so we only count THIS run's rows.
            run_row = (
                await session.execute(
                    select(PipelineRun.started_at).where(PipelineRun.id == uuid.UUID(run_id))
                )
            ).one_or_none()
            if not run_row:
                logger.warning(
                    "_update_source_after_crawl: run_id={} not found, skipping update",
                    run_id,
                )
                return
            run_started_at = run_row[0]
            if run_started_at.tzinfo is None:
                run_started_at = run_started_at.replace(tzinfo=UTC)

            # 2. Count rows by source_platform, but only those crawled
            #    DURING this run. This is the delta, not a cumulative.
            result = await session.execute(
                text("""
                    SELECT source_platform, COUNT(*) AS cnt
                    FROM raw_jd_records
                    WHERE crawled_at >= :started_at
                    GROUP BY source_platform
                """),
                {"started_at": run_started_at},
            )
            rows = result.fetchall()

            # 3. Build DS index (case-insensitive). Skip substring fallback.
            ds_index_result = await session.execute(select(DataSourceRecord))
            all_ds = list(ds_index_result.scalars().all())
            now = datetime.now(UTC)

            for platform, cnt in rows:
                if not platform:
                    continue
                p_norm = str(platform).strip().lower()
                matched = None
                # Step 1: exact lower match
                for ds in all_ds:
                    if ds.name.strip().lower() == p_norm:
                        matched = ds
                        break
                # Step 2: strip " (远程)" / "(国内)" annotations, then exact match
                if matched is None:
                    for ds in all_ds:
                        if ds.name.split("(")[0].strip().lower() == p_norm:
                            matched = ds
                            break
                # NOTE: NO substring fallback. If we cannot strictly identify
                # the DS for this platform, log and skip — better to under-
                # count than to mis-attribute.
                if matched is None:
                    logger.warning(
                        "_update_source_after_crawl: no DataSourceRecord matches "
                        "platform={!r} (run_id={}); skipping",
                        platform, run_id,
                    )
                    continue

                delta = int(cnt)
                matched.total_records = (matched.total_records or 0) + delta
                matched.last_crawl_at = now
                logger.info(
                    "_update_source_after_crawl: matched platform={!r} → DS {!r} (+{} records)",
                    platform, matched.name, delta,
                )
            await session.commit()
            logger.info("_update_source_after_crawl: updated for run_id={}", run_id)
    run_async(_update())


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
            from app.models.pipeline_models import DataSourceRecord
            paused = await session.execute(
                select(DataSourceRecord).where(DataSourceRecord.status == "paused")
            )
            paused_sources = paused.scalars().all()
            if paused_sources:
                names = [s.name for s in paused_sources]
                logger.info("Skipping {} paused source(s) for run_id={}: {}", len(names), run_id, names)
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.warning("_skip_paused_sources_if_needed failed (non-fatal): {}", exc)


def execute_crawl(run_id: str, run_type: str) -> dict[str, Any]:
    """执行 crawl 阶段：多源爬虫调度 + jd_raw 写入。"""
    # 2026-08-07 修复 (B1): import 失败(如 celery 容器缺 psycopg) 必须回写 run 状态,
    # 否则 run/stage 永远卡 running 0%, 用户看不到失败原因
    try:
        from crawler.persistence import dao
        from crawler.persistence.models import JdStatus

        # noqa: F401 — 依赖可用性探测
        from crawler.spiders import arbeitnow, jobicy, weworkremotely  # noqa: F401
        from crawler.spiders.v2ex_remote import run_sync as v2ex_sync  # noqa: F401
    except Exception as exc:  # noqa: BLE001 — 依赖缺失是环境级失败
        dep_err = f"crawler 依赖不可用: {exc}"
        from app.core.pipeline.orchestrator import StageStatus, update_stage_status
        from app.db.session import get_session_factory

        async def _mark_crawl_failed() -> None:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    await update_stage_status(
                        session, uuid.UUID(str(run_id)), "crawl",
                        status=StageStatus.FAILED.value,
                        errors=[dep_err],
                    )

        run_async(_mark_crawl_failed())
        logger.opt(exception=True).error("crawl stage deps unavailable: {}", exc)
        raise

    # 复用本模块的 build_spider_registry (PLAN-005/NEW-07 注册)
    spider_registry = build_spider_registry()

    try:
        dao.init_schema()
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.debug("init_schema call (non-fatal): {}", exc)

    default_platform = "v2ex"
    default_keyword = "python"

    run_async(_skip_paused_sources_if_needed(run_id))

    source_configs = run_async(_get_crawl_configs(run_id))

    total_inserted = 0
    total_seen = 0
    errors: list[str] = []
    per_source_stats: dict[str, int] = {}
    recent_samples: list[dict[str, Any]] = []
    sub_breakdown: dict[str, int] = {}
    crawl_start = time.monotonic()

    if not source_configs:
        default_max = 50 if run_type == "incremental" else 200
        logger.info(
            "No active crawler sources configured, falling back to default v2ex: "
            "keyword={}, max_count={}", default_keyword, default_max,
        )
        source_configs = [{
            "platform": default_platform,
            "keyword": default_keyword,
            "max_count": default_max,
            "source_name": "V2EX/Remotive (默认)",
        }]

    total_sources = len(source_configs)
    for source_idx, cfg in enumerate(source_configs):
        platform = cfg.get("platform", default_platform)
        keyword = cfg.get("keyword", default_keyword)
        max_count = cfg.get(
            "max_count",
            50 if run_type == "incremental" else 200,
        )
        source_name = cfg.get("source_name", platform)

        if cfg.get("disabled"):
            logger.info("Source '{}' is disabled in config, skipping", source_name)
            sub_breakdown[source_name] = -1
            continue

        spider_fn = spider_registry.get(platform)

        if spider_fn is None:
            reason = f"无蜘蛛适配器: platform={platform} (source: {source_name})"
            logger.warning(reason)
            errors.append(reason)
            sub_breakdown[source_name] = -2
            run_async(publish_stage_progress(
                run_id, "crawl", "running",
                progress=source_idx / total_sources,
                records_processed=total_inserted,
                current_activity=f"⊘ 跳过 {source_name} (无蜘蛛: {platform})",
                sub_breakdown=sub_breakdown,
                recent_samples=recent_samples[-5:],
                elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
                message=f"跳过 {source_name}: 无蜘蛛",
                sub_step=f"crawl:{source_name}",  # D-15
            ))
            continue

        # D-15: 每个数据源发 1 条 sub_step 事件
        run_async(publish_stage_progress(
            run_id, "crawl", "running",
            progress=source_idx / total_sources,
            records_processed=total_inserted,
            current_activity=f"正在爬取 {source_name} (平台: {platform}, 关键词: {keyword}, 目标: {max_count} 条)",
            recent_samples=recent_samples[-5:],
            sub_breakdown=sub_breakdown,
            elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
            message=f"开始爬取 {source_name}",
            sub_step=f"crawl:{source_name}",  # D-15
        ))

        try:
            logger.info(
                "Crawling source '{}' (platform={}, keyword={}, max_count={})",
                source_name, platform, keyword, max_count,
            )
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
                if r in ("inserted", "duplicate"):
                    source_inserted += 1
                    total_inserted += 1
                    if len(recent_samples) >= 10:
                        recent_samples.pop(0)
                    recent_samples.append({
                        "title": it.get("job_title", "未命名"),
                        "company": it.get("company", ""),
                        "url": it.get("source_url", ""),
                        "source": it.get("source_site", platform),
                    })

                if item_idx > 0 and item_idx % 5 == 0:
                    sub_breakdown[source_name] = source_inserted
                    run_async(publish_stage_progress(
                        run_id, "crawl", "running",
                        progress=(source_idx + (item_idx + 1) / max(source_seen + (max_count - source_seen), max_count)) / total_sources,
                        records_processed=total_inserted,
                        current_activity=f"{source_name}: 正在处理第 {item_idx + 1} 条 - {it.get('job_title', '未命名')[:30]}",
                        recent_samples=recent_samples[-5:],
                        sub_breakdown=sub_breakdown,
                        elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
                        message=f"{source_name} 已采集 {source_seen} 条",
                        sub_step=f"crawl:{source_name}",  # D-15
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

    per_source_summary = []
    for name, count in sorted(sub_breakdown.items(), key=lambda x: (
        -1 if x[1] >= 0 else 0,
        -x[1] if x[1] >= 0 else x[1],
    )):
        if count == -1:
            per_source_summary.append(f"{name}: 已禁用")
        elif count == -2:
            per_source_summary.append(f"{name}: 无蜘蛛")
        elif count == 0:
            per_source_summary.append(f"{name}: 0 条")
        else:
            per_source_summary.append(f"{name}: {count} 条")

    run_async(publish_stage_progress(
        run_id, "crawl", "completed",
        progress=1.0,
        records_processed=total_inserted,
        current_activity=f"采集完成: 共 {total_seen} 条原始数据，新增 {total_inserted} 条入库",
        recent_samples=recent_samples[-5:],
        sub_breakdown=sub_breakdown,
        elapsed_ms=int((time.monotonic() - crawl_start) * 1000),
        message=f"采集阶段完成: 总览={total_seen} 新增={total_inserted} | {'; '.join(per_source_summary[:5])}",
    ))

    if total_inserted == 0 and not errors:
        warning_msg = (
            "⚠️ 爬虫采集完成但 0 条入库。可能原因: ① 平台反爬(stealth被识别) "
            "② 选择器失效(网站改版) ③ 数据源配置 max_count=0"
        )
        errors.append(warning_msg)
        logger.warning(warning_msg + f" sources_attempted={total_sources}, total_seen={total_seen}")
    elif total_inserted == 0 and errors:
        logger.warning(f"爬虫 0 记录: 已有 {len(errors)} 个 errors")

    try:
        _update_source_after_crawl(run_id, total_inserted)
    except PipelineStageError:
        raise
    except Exception as exc:
        logger.warning("_update_source_after_crawl failed (non-fatal): {}", exc)

    return {
        "records_processed": total_inserted,
        "records_seen": total_seen,
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


__all__ = [
    "SPIDER_REGISTRY",
    "build_spider_registry",
    "execute_crawl",
]
