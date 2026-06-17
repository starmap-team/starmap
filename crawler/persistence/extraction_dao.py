"""R3 jd_extraction_records 表的 DAO。

提供 upsert + count + query 函数。R1 联调脚本通过这些函数写抽取结果。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .database import engine, get_jd_raw_session
from .extraction_models import Base, JdExtractionRecord

log = logging.getLogger(__name__)


def init_extraction_schema() -> None:
    """开发期快速建表（生产用 Alembic 迁移）。"""
    Base.metadata.create_all(bind=engine)
    log.info("jd_extraction_records 表已创建（若不存在）")


def upsert_extraction(
    jd_content: str,
    job_title: str,
    extracted_skills: dict[str, Any],
    experience_years: int | None = None,
    education: str | None = None,
    confidence: float = 0.0,
    hallucination_score: float | None = None,
    status: str = "completed",
) -> str:
    """插入一条抽取结果。返回 'inserted' / 'failed'。

    注：jd_extraction_records 没有 unique 约束，所以单纯 INSERT。
    如需去重可加 (jd_content, job_title) 唯一索引，但 schema 变更权属 R3。
    """
    try:
        with get_jd_raw_session() as s:
            stmt = (
                pg_insert(JdExtractionRecord)
                .values(
                    jd_content=jd_content,
                    job_title=job_title,
                    extracted_skills=extracted_skills,
                    experience_years=experience_years,
                    education=education,
                    confidence=confidence,
                    hallucination_score=hallucination_score,
                    status=status,
                )
            )
            s.execute(stmt)
            s.commit()
            return "inserted"
    except Exception as e:  # noqa: BLE001
        log.error("upsert_extraction 失败: %s", e)
        return "failed"


def count_extractions() -> int:
    with get_jd_raw_session() as s:
        return s.scalar(select(func.count(JdExtractionRecord.id))) or 0


def count_by_status() -> dict[str, int]:
    with get_jd_raw_session() as s:
        rows = s.execute(
            select(JdExtractionRecord.status, func.count(JdExtractionRecord.id)).group_by(
                JdExtractionRecord.status
            )
        ).all()
    return {status: cnt for status, cnt in rows}


__all__ = [
    "init_extraction_schema",
    "upsert_extraction",
    "count_extractions",
    "count_by_status",
]
