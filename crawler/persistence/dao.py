"""jd_raw 入库：单条 upsert + 批量。"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .database import get_jd_raw_session, engine
from .models import Base, JdRaw, JdStatus

log = logging.getLogger(__name__)


def init_schema() -> None:
    """开发期快速建表（生产用 Alembic 迁移）。"""
    Base.metadata.create_all(bind=engine)
    log.info("jd_raw / compliance_log 表已创建（若不存在）")


def upsert_jd(record: dict) -> str:
    """单条 upsert。返回 'inserted' / 'duplicate' / 'failed'。

    Phase 15-02: 改用 content_hash 作为 dedup key（而非 source_url）。
    因 psycopg + SQLAlchemy pg_insert().on_conflict_do_nothing() 返回的
    rowcount 为 -1（即使实际插入了），改用 inserted_primary_key 判断。
    """
    try:
        with get_jd_raw_session() as s:
            stmt = (
                pg_insert(JdRaw)
                .values(**record)
                .on_conflict_do_nothing(index_elements=["content_hash"])
            )
            result = s.execute(stmt)
            s.commit()
            # rowcount 在 ON CONFLICT DO NOTHING 时返回 -1，需用 inserted_primary_key 判断
            inserted_pk = getattr(result, "inserted_primary_key", None)
            if inserted_pk:
                return "inserted"
            # Fallback: 检查 rowcount (兼容老 driver)
            return "inserted" if (result.rowcount and result.rowcount > 0) else "duplicate"
    except Exception as e:  # noqa: BLE001
        log.error("upsert_jd 失败: %s", e)
        return "failed"


def count_jd() -> int:
    with get_jd_raw_session() as s:
        return s.scalar(select(func.count(JdRaw.id))) or 0


def count_by_status() -> dict[str, int]:
    with get_jd_raw_session() as s:
        rows = s.execute(
            select(JdRaw.status, JdRaw.id).order_by(None)
        ).all()
    out: dict[str, int] = {}
    for status, _id in rows:
        out[str(status.value)] = out.get(str(status.value), 0) + 1
    return out


__all__ = ["init_schema", "upsert_jd", "count_jd", "count_by_status"]
