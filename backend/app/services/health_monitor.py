"""Health monitor for data sources (Phase 15-04).

三个关键修复:
- Fix H1: 启动探针自动 disable 404/5xx 源 (probe_sources_at_startup)
- Fix M1: 错误类型加权熔断 (check_and_auto_pause_v2)
- Fix M2: Rate limit 指数退避 (rate_limit_backoff)

集成点:
- execute_crawl 在每个 source 完成后调用 record_metric
- 启动时调用 probe_sources_at_startup
- 每次触发 pipeline 前调用 check_and_auto_pause_v2
"""
from __future__ import annotations

import asyncio
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_models import DataSourceRecord
from app.utils.audit import AuditEntry, AuditEvent, audit_log

# Fix M1: 不同错误类型权重不同
# - rate_limit: 0.0 (不算 consecutive failure，单独 backoff 处理)
# - timeout: 0.5 (可能是大 payload)
# - connection: 1.0 (网络瞬时错误)
# - parse: 1.5 (数据格式问题，更可能是真的坏了)
# - blocked: 1.5 (被反爬)
# - auth: 2.0 (认证失败，最严重)
ERROR_WEIGHTS = {
    "rate_limit": 0.0,
    "timeout": 0.5,
    "connection": 1.0,
    "parse": 1.5,
    "blocked": 1.5,
    "auth": 2.0,
}

CIRCUIT_BREAKER_THRESHOLD = 3.0  # 累计加权失败分 >= 3.0 自动暂停
PROBE_TIMEOUT = 10  # 启动探针超时（秒）


async def record_metric(
    session: AsyncSession,
    source_id: uuid.UUID,
    run_id: uuid.UUID | None,
    status: str,
    records_inserted: int,
    error_type: str | None = None,
    error_message: str | None = None,
    duration_ms: int = 0,
) -> None:
    """记录每次爬取结果（每个 source 每次爬一次）。"""
    from app.models.data_source_metric import DataSourceMetric

    metric = DataSourceMetric(
        source_id=source_id,
        run_id=run_id,
        status=status,
        records_inserted=records_inserted,
        error_type=error_type,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    session.add(metric)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.debug("record_metric failed (non-fatal): {}", exc)


async def check_and_auto_pause_v2(
    session: AsyncSession, source_id: uuid.UUID
) -> bool:
    """Fix M1: 错误类型加权的熔断逻辑。

    与 v1 的区别:
    - v1: 3 次连续失败就暂停（不区分错误类型）
    - v2: 累计加权失败分 >= 3.0 才暂停
      - 3 次 connection = 3.0
      - 2 次 auth = 4.0 (会触发)
      - 1 次 auth + 1 次 parse = 3.5 (会触发)
      - rate_limit 错误**不**计入（权重 0.0），单独走 backoff

    Returns: True if source was auto-paused
    """
    from app.models.data_source_metric import DataSourceMetric

    recent = await session.execute(
        select(DataSourceMetric)
        .where(DataSourceMetric.source_id == source_id)
        .order_by(DataSourceMetric.started_at.desc())
        .limit(10)
    )
    failure_score = 0.0
    for m in recent.scalars():
        if m.status not in ("failed", "blocked"):
            continue
        failure_score += ERROR_WEIGHTS.get(m.error_type or "connection", 1.0)

    if failure_score >= CIRCUIT_BREAKER_THRESHOLD:
        source = await session.get(DataSourceRecord, source_id)
        if source and source.status == "active":
            source.status = "paused"
            source.config = {
                **(source.config or {}),
                "auto_paused_at": datetime.now(UTC).isoformat(),
                "auto_paused_reason": f"failure_score={failure_score:.1f} >= {CIRCUIT_BREAKER_THRESHOLD}",
            }
            await session.commit()
            audit_log(
                AuditEntry(
                    event=AuditEvent.AUTO_PAUSE,
                    actor="health_monitor",
                    action="weighted_circuit_breaker",
                    detail=f"source={source.name}, score={failure_score:.1f}",
                )
            )
            logger.warning("Auto-paused {}: failure_score={:.1f}", source.name, failure_score)
            return True
    return False


async def probe_sources_at_startup(session: AsyncSession) -> dict[str, str]:
    """Fix H1: 启动时探测每个 api/rss 源，4xx/5xx 自动 paused。

    Returns: {source_name: status_string}
    """
    sources = await session.execute(
        select(DataSourceRecord).where(
            DataSourceRecord.source_type.in_(["api", "rss"]),
            DataSourceRecord.status == "active",
        )
    )
    results: dict[str, str] = {}
    for src in sources.scalars():
        config = src.config or {}
        url = config.get("probe_url") or _derive_probe_url(src.name)
        if not url:
            results[src.name] = "no_url"
            continue

        # 在线程池里跑同步 urllib，避免阻塞 event loop
        loop = asyncio.get_running_loop()
        try:
            status = await loop.run_in_executor(None, _probe_sync, url, PROBE_TIMEOUT)
            if status.startswith("ok"):
                results[src.name] = "ok"
            else:
                # 4xx/5xx/网络错误 → 自动暂停
                src.status = "paused"
                src.config = {
                    **(src.config or {}),
                    "auto_paused_at": datetime.now(UTC).isoformat(),
                    "auto_paused_reason": f"startup probe: {status}",
                }
                await session.commit()
                audit_log(
                    AuditEntry(
                        event=AuditEvent.AUTO_PAUSE,
                        actor="health_monitor",
                        action="startup_probe_failed",
                        detail=f"source={src.name}, status={status}",
                    )
                )
                results[src.name] = f"auto_paused:{status}"
        except Exception as exc:
            results[src.name] = f"error:{exc}"

    return results


def _probe_sync(url: str, timeout: int) -> str:
    """同步 HTTP 探针（在线程池里跑）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "StarMap-HealthCheck/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 400:
                return f"http_{resp.status}"
            return "ok"
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except urllib.error.URLError as e:
        return f"url_error:{e.reason}"
    except Exception as e:
        return f"error:{e}"


def _derive_probe_url(source_name: str) -> str | None:
    """从 source_name 推导 probe_url（fallback）。"""
    mapping = {
        "Arbeitnow (远程)": "https://arbeitnow.com/api/job-board-api",
        "Jobicy (远程)": "https://jobicy.com/api/v2/remote-jobs?count=1",
        "WeWorkRemotely (远程)": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "Remotive (远程)": "https://remotive.com/api/remote-jobs?limit=1",
    }
    return mapping.get(source_name)


# Fix M2: Rate limit 指数退避状态 (per source)
_rate_limit_state: dict[str, int] = {}


async def rate_limit_backoff(source_name: str, max_wait: int = 60) -> int:
    """Fix M2: rate_limit 错误自动指数退避 (1s/2s/4s/8s/16s/.../max_wait)。

    Returns: 等待秒数（已 sleep）
    """
    attempt = _rate_limit_state.get(source_name, 0)
    wait_seconds = min(2 ** attempt, max_wait)
    _rate_limit_state[source_name] = attempt + 1
    logger.info(
        "Rate limit backoff for {}: attempt={}, sleeping {}s",
        source_name, attempt, wait_seconds,
    )
    await asyncio.sleep(wait_seconds)
    return wait_seconds


def reset_rate_limit_backoff(source_name: str) -> None:
    """成功调用后重置 backoff 计数。"""
    _rate_limit_state.pop(source_name, None)


async def get_health_dashboard(session: AsyncSession) -> list[dict[str, Any]]:
    """返回每个源的健康度摘要。"""
    from app.models.data_source_metric import DataSourceMetric

    sources = await session.execute(select(DataSourceRecord))
    dashboard: list[dict[str, Any]] = []
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    for src in sources.scalars():
        # 最近 24h 的 metrics
        recent = await session.execute(
            select(DataSourceMetric)
            .where(
                DataSourceMetric.source_id == src.id,
                DataSourceMetric.started_at >= cutoff,
            )
        )
        metrics = recent.scalars().all()
        total = len(metrics)
        successes = sum(1 for m in metrics if m.status == "success")
        blocked = sum(1 for m in metrics if m.status in ("failed", "blocked"))
        success_rate = (successes / total) if total else None
        total_records = sum(m.records_inserted for m in metrics)

        dashboard.append({
            "source_id": str(src.id),
            "name": src.name,
            "source_type": src.source_type,
            "status": src.status,
            "last_crawl_at": src.last_crawl_at.isoformat() if src.last_crawl_at else None,
            "last_successful_crawl_at": (
                src.last_successful_crawl_at.isoformat()
                if hasattr(src, "last_successful_crawl_at") and src.last_successful_crawl_at
                else None
            ),
            "success_rate_24h": success_rate,
            "calls_24h": total,
            "blocked_24h": blocked,
            "records_24h": total_records,
            "authority_score": src.authority_score,
        })

    return dashboard
