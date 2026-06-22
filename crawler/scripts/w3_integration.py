"""W3 联调主脚本：jd_raw → backend /api/v1/extract/jd → jd_extraction_records。

流 A (R1) 与流 B (R3) 的端到端集成验证。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# 绕过系统代理（Windows 上 127.0.0.1:8080）
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

# 强制 UTF-8 stdout（Windows 兼容）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 让脚本可独立运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx

from crawler.persistence import dao as jd_dao
from crawler.persistence import extraction_dao
from crawler.persistence.database import get_jd_raw_session
from crawler.persistence.models import JdRaw, JdStatus
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("w3-integration")


# 默认 backend 地址（容器内是 'backend:8000'，宿主是 'localhost:8000'）
DEFAULT_BACKEND = "http://localhost:8000"


MAX_JD_CONTENT_LEN = 50000  # 后端 jd_content max_length 限制

# 可重试错误关键词（连接问题、服务端临时故障）
_RETRYABLE_KEYWORDS = (
    "Connection refused", "Connection reset", "Connection aborted",
    "connect timeout", "read timeout", "connect error",
    "HTTP 502", "HTTP 503", "HTTP 504",
)


def _is_retryable(error_msg: str) -> bool:
    """判断错误是否可重试（连接问题 / 5xx）。"""
    return any(kw in error_msg for kw in _RETRYABLE_KEYWORDS)


def call_extract_api(jd_content: str, backend_url: str) -> dict:
    """调用 R3 的 /api/v1/extract/jd 端点。"""
    # 前置截断，避免 API 422
    if len(jd_content) > MAX_JD_CONTENT_LEN:
        log.warning("jd_content 长度 %d 超限，截断至 %d", len(jd_content), MAX_JD_CONTENT_LEN)
        jd_content = jd_content[:MAX_JD_CONTENT_LEN]
    endpoint = f"{backend_url}/api/v1/extract/jd"
    payload = {
        "jd_content": jd_content,
        "options": {
            "anti_hallucination_enabled": False,  # 关掉反幻觉检查加速
            "normalize_skills_enabled": True,
        },
    }
    try:
        resp = httpx.post(endpoint, json=payload, timeout=60.0, proxy=None)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Request failed: {e}"}


def fetch_pending_jd_raw(limit: int) -> list[dict]:
    """从 jd_raw 取 status=raw 的待抽取 JD。"""
    with get_jd_raw_session() as s:
        rows = s.execute(
            select(JdRaw)
            .where(JdRaw.status == JdStatus.raw)
            .limit(limit)
        ).all()
        # 在 session 内提取数据，避免 DetachedInstanceError
        return [
            {
                "id": r[0].id,
                "source_site": r[0].source_site,
                "source_url": r[0].source_url,
                "job_title": r[0].job_title,
                "clean_text": r[0].clean_text,
            }
            for r in rows
        ]


def mark_jd_extracted(jd_raw_id: int, success: bool, error: str | None = None) -> None:
    """更新 jd_raw.status：成功=extracted，失败=failed。"""
    with get_jd_raw_session() as s:
        row = s.get(JdRaw, jd_raw_id)
        if row is None:
            log.warning("jd_raw id=%s 不存在", jd_raw_id)
            return
        row.status = JdStatus.extracted if success else JdStatus.failed
        if error:
            row.error_msg = error
        s.commit()


def run_integration(limit: int, backend_url: str, skip_existing: bool = True) -> dict:
    """主流程：取 N 条 jd_raw → 调 API → 写 jd_extraction_records。

    Returns:
        统计 dict {total, inserted, failed, skipped, errors}
    """
    pending = fetch_pending_jd_raw(limit)
    log.info("从 jd_raw 取到 %d 条 status=raw 的 JD", len(pending))

    inserted = 0
    failed = 0
    retryable = 0
    errors: list[dict] = []

    for i, item in enumerate(pending, 1):
        log.info(
            "[%d/%d] 处理 jd_raw id=%d (%s): %s",
            i, len(pending), item["id"], item["source_site"], item["job_title"][:40],
        )

        t0 = time.time()
        result = call_extract_api(item["clean_text"], backend_url)
        elapsed = time.time() - t0

        if "error" in result and "position_name" not in result:
            err_msg = result["error"]
            if _is_retryable(err_msg):
                # 可重试错误：不改 status，下次运行自动重试
                log.warning("可重试错误（跳过，下次重试）: %s", err_msg)
                retryable += 1
                errors.append({"jd_raw_id": item["id"], "error": f"[retryable] {err_msg}"})
            else:
                # 不可重试错误：标记为 failed
                log.error("抽取失败（永久）: %s", err_msg)
                mark_jd_extracted(item["id"], success=False, error=err_msg)
                failed += 1
                errors.append({"jd_raw_id": item["id"], "error": err_msg})
            continue

        # 写 jd_extraction_records
        position_name = result.get("position_name", "") or item["job_title"]
        required_skills = result.get("required_skills", [])
        preferred_skills = result.get("preferred_skills", [])
        experience = result.get("experience_required")
        education = result.get("education_required")
        confidence = result.get("confidence", 0.0)
        hallucination = result.get("hallucination_score")

        # extracted_skills 字段存 dict
        skills_payload = {
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "normalized_skills": result.get("normalized_skills", []),
            "responsibilities": result.get("responsibilities", []),
        }

        r = extraction_dao.upsert_extraction(
            jd_content=item["clean_text"][:MAX_JD_CONTENT_LEN],  # DB 字段限长
            job_title=position_name[:255],
            extracted_skills=skills_payload,
            experience_years=experience,
            education=education,
            confidence=confidence,
            hallucination_score=hallucination,
            status="completed",
        )

        if r == "inserted":
            mark_jd_extracted(item["id"], success=True)
            inserted += 1
            log.info(
                "  ✅ 抽取完成: %d 必需 / %d 加分 (%.1fs, conf=%.2f)",
                len(required_skills), len(preferred_skills), elapsed, confidence,
            )
        else:
            mark_jd_extracted(item["id"], success=False, error=f"DB insert failed: {r}")
            failed += 1
            errors.append({"jd_raw_id": item["id"], "error": f"DB insert failed: {r}"})

    summary = {
        "total": len(pending),
        "inserted": inserted,
        "failed": failed,
        "retryable": retryable,
        "errors": errors[:5],  # 只保留前 5 条详细错误
        "backend_url": backend_url,
    }
    return summary


def main() -> int:
    p = argparse.ArgumentParser(prog="w3-integration")
    p.add_argument("--max", type=int, default=10, help="最多处理多少条 jd_raw")
    p.add_argument("--backend", default=DEFAULT_BACKEND, help="backend base URL")
    p.add_argument("--init-schema", action="store_true", help="建 jd_extraction_records 表")
    args = p.parse_args()

    if args.init_schema:
        log.info("建 jd_extraction_records 表...")
        extraction_dao.init_extraction_schema()

    log.info("=== W3 联调启动 ===")
    log.info("backend: %s", args.backend)
    log.info("max: %d", args.max)

    # 先试连通性
    try:
        r = httpx.get(f"{args.backend}/api/v1/health", timeout=5.0, proxy=None)
        r.raise_for_status()
        log.info("✅ backend 健康检查通过: %s", r.json())
    except Exception as e:
        log.error("❌ backend 连通性失败: %s", e)
        log.error("请确认 docker-compose -f docker-compose.dev.yml up -d 起来了")
        return 1

    # 跑联调
    summary = run_integration(limit=args.max, backend_url=args.backend)

    # 输出统计
    log.info("=" * 50)
    log.info("W3 联调完成")
    log.info("  total:    %d", summary["total"])
    log.info("  inserted: %d", summary["inserted"])
    log.info("  failed:   %d", summary["failed"])
    log.info("  retryable: %d", summary["retryable"])
    log.info("=" * 50)

    # 写一份 JSON 报告
    report_path = Path("crawler/output/w3_integration_report.json")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("报告写入: %s", report_path)

    # 成功条件：至少插入 1 条，且无失败/可重试错误
    ok = summary["inserted"] > 0 and summary["failed"] == 0 and summary["retryable"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
