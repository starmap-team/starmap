"""Import service — 复用 dao.upsert_jd 路径 (Phase 15-02 Task 2)."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pii_detector import detect_pii
from app.utils.audit import AuditEntry, AuditEvent, audit_log


async def import_items(
    session: AsyncSession,
    items: list[dict[str, Any]],
    source_name: str,
    platform: str,
    actor: str,
) -> dict[str, Any]:
    """导入用户提供的 JDs，复用 dao.upsert_jd 路径。

    Returns:
        dict with total/inserted/duplicate/errors/pii_warnings
    """
 # Lazy import to avoid circular dependency
    from crawler.persistence import dao
    from crawler.persistence.models import JdStatus

    inserted = 0
    duplicate = 0
    errors: list[dict[str, Any]] = []
    pii_warnings = 0
    now = datetime.now(UTC)

    for idx, item in enumerate(items):
        try:
 # Fix H3 ( review): 全量 hash 而非 [:500] 截断
            content_hash = hashlib.sha256(
                (
                    item.get("clean_text", "")
                    + "|"
                    + item.get("job_title", "")
                    + "|"
                    + item.get("company", "")
                ).encode("utf-8")
            ).hexdigest()

 # Fix H2 ( review): PII 检测
            text_for_pii = (
                item.get("clean_text", "")
                + " "
                + item.get("job_title", "")
                + " "
                + item.get("company", "")
            )
            pii_types = detect_pii(text_for_pii)

            rec = {
                "source_site": platform,
                "source_url": item.get("source_url", ""),
                "raw_html": (item.get("clean_text", "") or "")[:10000],
                "clean_text": item.get("clean_text", ""),
                "job_title": item.get("job_title", "")[:200],
                "company": item.get("company", ""),
                "salary_min": int(item.get("salary_min", 0) or 0),
                "salary_max": int(item.get("salary_max", 0) or 0),
                "location": item.get("location", ""),
                "publish_date": now.strftime("%Y-%m-%d"),
                "content_hash": content_hash,
                "status": JdStatus.raw,
            }
            r = dao.upsert_jd(rec)
            if r == "inserted":
                inserted += 1
                if pii_types:
                    pii_warnings += 1
 # 记录 PII 警告到 audit log（不阻断入库）
                    audit_log(
                        AuditEntry(
                            event=AuditEvent.PII_DETECTED,
                            actor=actor,
                            action="import_pii_warning",
                            detail=f"row={idx}, source={source_name}, types={pii_types}",
                        )
                    )
            elif r == "duplicate":
                duplicate += 1
        except Exception as e:
            errors.append({"row": idx, "field": "all", "message": str(e)[:200]})

 # Audit log 记录导入操作
    audit_log(
        AuditEntry(
            event=AuditEvent.MANUAL_IMPORT,
            actor=actor,
            action="import_jd",
            detail=(
                f"source={source_name}, platform={platform}, "
                f"total={len(items)}, inserted={inserted}, duplicate={duplicate}, "
                f"pii_warnings={pii_warnings}"
            ),
        )
    )

    return {
        "total": len(items),
        "inserted": inserted,
        "duplicate": duplicate,
        "errors": errors,
        "pii_warnings": pii_warnings,
    }
