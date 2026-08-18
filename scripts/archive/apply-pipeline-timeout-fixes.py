#!/usr/bin/env python3
"""Re-apply pipeline import timeout fixes that were lost during concurrent session commits."""
from pathlib import Path

# C1: llm_client.py
p = Path("backend/app/core/extraction/llm_client.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "import json\nfrom typing import Any",
    "import json\nimport time\nfrom typing import Any"
)
text = text.replace(
    "async with httpx.AsyncClient(timeout=httpx.Timeout(actual_timeout)) as client:",
    """async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=actual_timeout,
                write=actual_timeout,
                pool=10.0,
            )
        ) as client:"""
)
text = text.replace(
    "errors: list[str] = []\n\n    async def _call_and_track(coro_factory):",
    """errors: list[str] = []
    fallback_budget_seconds = 180.0
    fallback_start = time.monotonic()

    async def _call_and_track(coro_factory):"""
)
text = text.replace(
    """async def _call_and_track(coro_factory):  # type: ignore[no-untyped-def]
        \"\"\"Run a provider call and record its cost before returning.\"\"\"
        resp = await coro_factory(prompt)""",
    """async def _call_and_track(coro_factory):  # type: ignore[no-untyped-def]
        \"\"\"Run a provider call and record its cost before returning.\"\"\"
        elapsed = time.monotonic() - fallback_start
        if elapsed > fallback_budget_seconds:
            raise LLMConnectionError(
                f\"Fallback budget exceeded ({elapsed:.0f}s > {fallback_budget_seconds:.0f}s); \"
                f\"tried: {'; '.join(errors) if errors else 'no providers'}\"
            )
        resp = await coro_factory(prompt)"""
)
p.write_text(text, encoding="utf-8")
print("llm_client.py updated")

# C2: import_.py
p = Path("backend/app/core/pipeline/stages/import_.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "import time\nfrom typing import Any\n\nfrom loguru import logger",
    "import time\nfrom typing import Any\n\nfrom celery.exceptions import SoftTimeLimitExceeded\nfrom loguru import logger"
)
text = text.replace(
    "    start = time.monotonic()",
    """    start = time.monotonic()
    # 2026-08-16: stage budget (independent of Celery soft_time_limit).
    from app.config import settings as _settings
    stage_budget_seconds = max(_settings.pipeline_stage_timeout - 300, 60)"""
)
old_loop = '''        for idx, (text, title) in enumerate(zip(jd_texts, jd_titles, strict=False)):
            try:
                # D-15: persist
                # D5 fix: job_title fallback
                result = run_async(run_batch_extract_jd(text, job_title=title))
                if result.get("status") == "completed":
                    processed += 1
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
                    run_async(publish_stage_progress(
                        run_id, "import", "running",
                        progress=0.15 + 0.8 * (idx / max(total, 1)),
                        records_processed=processed,
                        current_activity=f"LLM 提取 {idx}/{total} 条 - 当前: {title[:30] if title else '...'}",
                        recent_samples=extracted_skills_sample[-5:],
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                        sub_step="persist",
                    ))
            except PipelineStageError:
                raise
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.opt(exception=True).warning("JD extraction failed in import stage: {}", exc)'''
new_loop = '''        for idx, (text, title) in enumerate(zip(jd_texts, jd_titles, strict=False)):
            elapsed_sec = time.monotonic() - start
            if elapsed_sec > stage_budget_seconds:
                msg = f"Stage budget exceeded ({elapsed_sec:.0f}s > {stage_budget_seconds}s); processed {processed}/{total}"
                logger.warning("import stage {}: {}", run_id, msg)
                errors.append(msg)
                run_async(publish_stage_progress(
                    run_id, "import", "running",
                    progress=0.15 + 0.8 * (idx / max(total, 1)),
                    records_processed=processed,
                    current_activity=f"Stage budget exceeded ({elapsed_sec:.0f}s)",
                    elapsed_ms=int(elapsed_sec * 1000),
                    sub_step="persist",
                ))
                break
            try:
                result = run_async(run_batch_extract_jd(text, job_title=title))
                if result.get("status") == "completed":
                    processed += 1
                    if result.get("data", {}).get("required_skills"):
                        for sk in result["data"]["required_skills"][:3]:
                            extracted_skills_sample.append({
                                "title": title[:40] if title else "未命名",
                                "skill": sk.get("name", ""),
                                "category": sk.get("category", ""),
                            })
                else:
                    errors.append(f"extraction failed: {result.get('error', 'unknown')}")

                # 2026-08-16: every record, not every 3rd
                run_async(publish_stage_progress(
                    run_id, "import", "running",
                    progress=0.15 + 0.8 * ((idx + 1) / max(total, 1)),
                    records_processed=processed,
                    current_activity=f"LLM 提取 {idx + 1}/{total} 条 - 当前: {title[:30] if title else '...'}",
                    recent_samples=extracted_skills_sample[-5:],
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                    sub_step="persist",
                ))
            except PipelineStageError:
                raise
            except SoftTimeLimitExceeded:
                logger.warning("import stage {}: SoftTimeLimitExceeded, breaking", run_id)
                errors.append("Celery soft_time_limit reached")
                break
            except Exception as exc:
                errors.append(f"extraction error: {exc}")
                logger.opt(exception=True).warning("JD extraction failed in import stage: {}", exc)'''
if old_loop in text:
    text = text.replace(old_loop, new_loop)
    print("import_.py loop replaced")
else:
    print("WARN: old_loop not found in import_.py — manual edit needed")
p.write_text(text, encoding="utf-8")

# C3: config.py
p = Path("backend/app/config.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "pipeline_import_batch_size: int = 500  # 阶段 import 每次读取已清洗 JD 的批量上限",
    "pipeline_import_batch_size: int = 200  # 阶段 import 每次读取已清洗 JD 的批量上限 (2026-08-16: 500 -> 200)"
)
p.write_text(text, encoding="utf-8")
print("config.py updated")
print("All changes applied")