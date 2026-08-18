"""jd_raw 入库：单条 upsert + 批量。"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .database import engine, get_jd_raw_session
from .models import Base, JdRaw

log = logging.getLogger(__name__)

# jd_raw 表里 date / 数值列：上游 spider 偶发传空串/None，
# 直接传 PG 会抛 InvalidDatetimeFormat 之类类型错误，整 batch 失败被吞。
# D5 fix (2026-08-12): 空串/None → 剔除该字段（PG DEFAULT NULL / nullable）。
_DATE_KEYS = ("publish_date")
_NUMERIC_KEYS = ("salary_min", "salary_max")

def _sanitize(record: dict) -> dict:
    """剔除空日期/数值字段，避免 PG 类型错误；非法值记 warning。"""
    out = dict(record)
    for k in _DATE_KEYS:
        v = out.get(k)
        if v is None:
            out.pop(k, None)
        elif isinstance(v, str) and (not v.strip or v.strip in ("None", "null")):
            log.warning("dao.upsert_jd: 剔除空日期字段 %s (source=%s)", k, out.get("source_site"))
            out.pop(k, None)
        elif isinstance(v, str) and v.strip:
            try:
                datetime.fromisoformat(v.strip)
            except ValueError:
                log.warning("dao.upsert_jd: 非法日期 %r → 剔除", v)
                out.pop(k, None)
    for k in _NUMERIC_KEYS:
        v = out.get(k)
        if v is None or (isinstance(v, str) and not v.strip):
            out.pop(k, None)
        elif isinstance(v, str):
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out.pop(k, None)
    return out

def init_schema -> None:
    """开发期快速建表（生产用 Alembic 迁移）。"""
    Base.metadata.create_all(bind=engine)
    log.info("jd_raw / compliance_log 表已创建（若不存在）")

# D5 fix (2026-08-12): 暴露最近一次异常供 /crawl-source 端点向上层传播。
# 之前 `except Exception: return "failed"` 把 InvalidDatetimeFormat 等根因完全吞没，
# 上层只看到 inserted=0 / duplicate=N / failed=N，无法定位问题。
_last_error: dict[str, str] = {}

def upsert_jd(record: dict) -> str:
    """单条 upsert。返回 'inserted' / 'duplicate' / 'failed'。-02: 改用 content_hash 作为 dedup key（而非 source_url）。
    因 psycopg + SQLAlchemy pg_insert.on_conflict_do_nothing 返回的
    rowcount 为 -1（即使实际插入了），改用 inserted_primary_key 判断。
    """
    try:
        clean = _sanitize(record)
        with get_jd_raw_session as s:
            stmt = (
                pg_insert(JdRaw)
                .values(**clean)
                .on_conflict_do_nothing(index_elements=["content_hash"])
            )
            result = s.execute(stmt)
            s.commit
            # rowcount 在 ON CONFLICT DO NOTHING 时返回 -1，需用 inserted_primary_key 判断
            inserted_pk = getattr(result, "inserted_primary_key", None)
            if inserted_pk:
                return "inserted"
            # Fallback: 检查 rowcount (兼容老 driver)
            return "inserted" if (result.rowcount and result.rowcount > 0) else "duplicate"
    except Exception as e:  # noqa: BLE001
        key = f"{record.get('source_site', '?')}/{record.get('content_hash', '?')[:12]}"
        _last_error[key] = f"{type(e).__name__}: {e}"
        log.error("upsert_jd 失败 source=%s: %s", key, e)
        return "failed"

def get_last_error -> dict[str, str]:
    """返回自进程启动以来每次 upsert 失败的 key→err 摘要，供上层（/crawl-source）回传前端。"""
    return dict(_last_error)

def clear_last_error -> None:
    _last_error.clear

def count_jd -> int:
    with get_jd_raw_session as s:
        return s.scalar(select(func.count(JdRaw.id))) or 0

def count_by_status -> dict[str, int]:
    with get_jd_raw_session as s:
        rows = s.execute(
            select(JdRaw.status, JdRaw.id).order_by(None)
        ).all
    out: dict[str, int] = {}
    for status, _id in rows:
        out[str(status.value)] = out.get(str(status.value), 0) + 1
    return out

__all__ = ["count_by_status", "count_jd", "init_schema", "upsert_jd", "get_last_error", "clear_last_error"]
