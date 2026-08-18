"""Pipeline crawl 阶段（ + + Task 4）。

按数据源/平台调度爬虫，写入 jd_raw。每启用的数据源发送 1 条 sub_step 事件（）。
本模块从 executor.execute_crawl 迁出；executor.py 保留兼容重导出，存量调用方零改动（）。
同时收纳 crawl 相关辅助（spider 注册表、crawl 配置加载、DataSourceRecord 更新）——
拆分：这些辅助原在 executor.py，随阶段迁入本模块。
"""
from __future__ import annotations

import time
import uuid
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
# executor 与单源调度端点共用; 补入 juejin/remoteok (/003 落地后遗漏注册)
SPIDER_REGISTRY: dict[str, Any] = {
 "v2ex": None, # 延迟导入避免循环
}

def build_spider_registry -> dict[str, Any]:
 """Re-export of ``app.services.spider_registry.build_spider_registry``.

 Layer-boundary conformance: API routes must not import from ``core/``,
 so the canonical implementation lives in ``services/spider_registry.py``
 and this module re-exports it for in-core callers (executor, pipeline_service).
 """
 from app.services.spider_registry import build_spider_registry as _impl

 return _impl

def _update_source_after_crawl(run_id: str, records_count: int) -> None:
 """execute_crawl 完成后刷新 DataSourceRecord 统计字段。

 D4 fix (2026-08-12): 原实现读遗留死表 raw_jd_records（当前管线 crawl 经
 dao.upsert_jd 写 jd_raw；status_aggregator 注释明确 "RawJDRecord 永不被写入"）
 并**累加** total_records，与 sync_source_quality（D3 真实来源，从 jd_raw 聚合
 绝对量）互相污染：累加使 total 漂移、死表计数污染正确值。此处改为直接委托
 sync_source_quality —— jd_raw 是唯一真实采集数据源，total/valid/quality/dup/
 last_crawl_at 全部由它按绝对量回写，消除死表污染与累加漂移。
 """
 async def _update:
 from app.core.pipeline.source_quality_sync import sync_source_quality

 session_factory = get_session_factory
 async with session_factory as session:
 await sync_source_quality(session)
 logger.info("_update_source_after_crawl: stats refreshed via sync_source_quality (run_id={})", run_id)
 run_async(_update)

async def _get_crawl_configs(run_id: str) -> list[dict[str, Any]]:
 """Load per-source crawl configurations from active DataSourceRecord(s).

 Returns a list of config dicts, each with: platform, keyword, max_count, source_name.
 Falls back to empty list if no active sources found (caller handles defaults).

 D8: 若 run 指定了 selected_sources（触发/调度时自选源），按名称过滤；
 null/空 = 全部 active 的 crawler/api/rss 源（向后兼容）。
 Each DataSourceRecord.config should contain:
 {"keyword": "python", "max_count": 50, "platform": "bosszhipin"}
 """
 try:
 session_factory = get_session_factory
 async with session_factory as session:
 from app.models.pipeline_models import DataSourceRecord, PipelineRun

 # 读取 run 的 selected_sources（触发/调度时手动自选源）
 selected: list[str] | None = None
 if run_id:
 run_row = await session.execute(
 select(PipelineRun.id, PipelineRun.selected_sources)
 .where(PipelineRun.id == run_id)
 )
 run_meta = run_row.first
 if run_meta and run_meta.selected_sources:
 selected = list(run_meta.selected_sources)

 # : api/rss 源同样参与 crawl 阶段（ 修复在 rebase 中丢失，恢复）
 # 当手动指定了 selected_sources 时，直接按名称查这些源（不限制
 # source_type —— job_board/blog 型如 V2EX/掘金也在可选项内），否则用户
 # 选了源却因 source_type 过滤被排除 → fallback 默认源（日志实证）。
 if selected:
 result = await session.execute(
 select(DataSourceRecord).where(
 DataSourceRecord.name.in_(selected),
 DataSourceRecord.status == "active",
 )
 )
 else:
 result = await session.execute(
 select(DataSourceRecord).where(
 DataSourceRecord.source_type.in_(["crawler", "api", "rss"]),
 DataSourceRecord.status == "active",
 )
 )
 sources = result.scalars.all
 configs: list[dict[str, Any]] = []
 for ds in sources:
 if ds.config is None:
 continue
 # 选源过滤 —— 指定了源但当前 ds 不在列表内则跳过
 if selected and ds.name not in selected:
 logger.info(
 "D8 source filter: skip '{}' (not in selected_sources={})",
 ds.name, selected,
 )
 continue
 # Build per-source config: merge record-level metadata with config JSON
 cfg = dict(ds.config)
 cfg["source_name"] = ds.name
 # (2026-08-15): 禁止静默回退 v2ex —— 无 platform 的源直接跳过，
 # 避免 V2EX 内容被错误归属到 bosszhipin/zhaopin 等未配置源。
 platform = cfg.get("platform") or cfg.get("source_site")
 if not platform:
 logger.warning(
 "crawl config skip '{}': 未配置 platform/source_site，跳过（P0-1）",
 ds.name,
 )
 continue
 cfg["platform"] = platform
 configs.append(cfg)
 if configs:
 logger.debug(
 "Loaded {} crawl config(s) from {} active source(s) (selected={})",
 len(configs), len(sources), bool(selected),
 )
 return configs
 except PipelineStageError:
 raise
 except Exception as exc:
 logger.warning("_get_crawl_configs failed (non-fatal, using defaults): {}", exc)
 return []

async def _skip_paused_sources_if_needed(run_id: str) -> None:
 """Log paused sources (the actual skip happens in the spider call)."""
 try:
 session_factory = get_session_factory
 async with session_factory as session:
 from app.models.pipeline_models import DataSourceRecord
 paused = await session.execute(
 select(DataSourceRecord).where(DataSourceRecord.status == "paused")
 )
 paused_sources = paused.scalars.all
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
 from crawler.spiders import arbeitnow, jobicy, weworkremotely # noqa: F401
 from crawler.spiders.v2ex_remote import run_sync as v2ex_sync # noqa: F401
 except Exception as exc: # noqa: BLE001 — 依赖缺失是环境级失败
 dep_err = f"crawler 依赖不可用: {exc}"
 from app.core.pipeline.orchestrator import StageStatus, update_stage_status
 from app.db.session import get_session_factory

 async def _mark_crawl_failed -> None:
 session_factory = get_session_factory
 async with session_factory as session:
 async with session.begin:
 await update_stage_status(
 session, uuid.UUID(str(run_id)), "crawl",
 status=StageStatus.FAILED.value,
 errors=[dep_err],
 )

 run_async(_mark_crawl_failed)
 logger.opt(exception=True).error("crawl stage deps unavailable: {}", exc)
 raise

 # 复用本模块的 build_spider_registry (/注册)
 spider_registry = build_spider_registry

 try:
 dao.init_schema
 except PipelineStageError:
 raise
 except Exception as exc:
 logger.debug("init_schema call (non-fatal): {}", exc)

 default_platform = "v2ex"
 default_keyword = "python"

 run_async(_skip_paused_sources_if_needed(run_id))

 source_configs = run_async(_get_crawl_configs(run_id))

 total_inserted = 0
 total_new = 0 # 真正新增行（upsert 返回 inserted）
 total_duplicate = 0 # content_hash 已存在（重复）
 total_seen = 0
 errors: list[str] = []
 warnings: list[str] = [] # 非致命提示（0 条采集等），仅告警不判 failed
 per_source_stats: dict[str, int] = {}
 recent_samples: list[dict[str, Any]] = []
 sub_breakdown: dict[str, int] = {}
 crawl_start = time.monotonic

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
 elapsed_ms=int((time.monotonic - crawl_start) * 1000),
 message=f"跳过 {source_name}: 无蜘蛛",
 sub_step=f"crawl:{source_name}", # 
 ))
 continue

 # : 每个数据源发 1 条 sub_step 事件
 run_async(publish_stage_progress(
 run_id, "crawl", "running",
 progress=source_idx / total_sources,
 records_processed=total_inserted,
 current_activity=f"正在爬取 {source_name} (平台: {platform}, 关键词: {keyword}, 目标: {max_count} 条)",
 recent_samples=recent_samples[-5:],
 sub_breakdown=sub_breakdown,
 elapsed_ms=int((time.monotonic - crawl_start) * 1000),
 message=f"开始爬取 {source_name}",
 sub_step=f"crawl:{source_name}", # 
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
 # 2026-08-12 (pipeline 联调): 区分新增 vs 重复 —— "入库 0" 通常是因为
 # 本次爬取 70 条 content_hash 与库中已有记录重复（upsert 返回 duplicate），
 # 而非爬虫没抓到。source_inserted 计入新增+重复（= 本源处理量，供
 # sub_breakdown/实时状态展示），新增/重复总数由 records_new/records_duplicate
 # 承载（DAG tooltip 与详情抽屉解释"为何入库 0"）。
 if r in ("inserted", "duplicate"):
 source_inserted += 1
 total_inserted += 1
 if r == "inserted":
 total_new += 1
 else:
 total_duplicate += 1
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
 elapsed_ms=int((time.monotonic - crawl_start) * 1000),
 message=f"{source_name} 已采集 {source_seen} 条",
 sub_step=f"crawl:{source_name}", # 
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
 for name, count in sorted(sub_breakdown.items, key=lambda x: (
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
 records_processed=total_seen,
 # fix: 文案用真实新增 total_new（原用 total_inserted=新增+重复 冒充"新增"）
 current_activity=(
 f"采集完成: 抓到 {total_seen} 条，新增 {total_new} 条入库，{total_duplicate} 条与库中重复"
 if total_new > 0 else
 f"采集完成: 抓到 {total_seen} 条，全部 {total_duplicate} 条与库中已有重复（未新增）"
 ),
 recent_samples=recent_samples[-5:],
 sub_breakdown=sub_breakdown,
 elapsed_ms=int((time.monotonic - crawl_start) * 1000),
 message=f"采集阶段完成: 抓到={total_seen} 新增={total_new} 重复={total_duplicate} | {'; '.join(per_source_summary[:5])}",
 ))

 if total_seen == 0 and not errors:
 warning_msg = (
 "⚠️ 爬虫采集完成但 0 条入库。可能原因: ① 平台反爬(stealth被识别) "
 "② 选择器失效(网站改版) ③ 数据源配置 max_count=0"
 )
 # 0 条采集 = 非致命警告（进入 warnings），不再判 failed —— 否则定时任务
 # 在部分源返回 0（如 v2ex 超时 / arbeitnow 握手失败）时会每小时刷失败记录
 warnings.append(warning_msg)
 logger.warning(warning_msg + f" sources_attempted={total_sources}, total_seen={total_seen}")
 elif total_seen == 0 and errors:
 logger.warning(f"爬虫 0 记录: 已有 {len(errors)} 个 errors")

 try:
 _update_source_after_crawl(run_id, total_inserted)
 except PipelineStageError:
 raise
 except Exception as exc:
 logger.warning("_update_source_after_crawl failed (non-fatal): {}", exc)

 return {
 "records_processed": total_seen,
 "records_seen": total_seen,
 "records_new": total_new,
 "records_duplicate": total_duplicate,
 "errors": errors,
 "warnings": warnings,
 "per_source": per_source_stats,
 "sub_breakdown": sub_breakdown,
 "recent_samples": recent_samples[-5:],
 "per_source_summary": per_source_summary,
 "current_activity": (
 f"采集完成: 抓到 {total_seen} 条，新增 {total_new} 条入库，{total_duplicate} 条与库中重复 | {'; '.join(per_source_summary[:5])}"
 if total_new > 0 else
 f"采集完成: 抓到 {total_seen} 条，全部与库中已有重复（未新增） | {'; '.join(per_source_summary[:5])}"
 ),
 }

__all__ = [
 "SPIDER_REGISTRY",
 "build_spider_registry",
 "execute_crawl",
]
