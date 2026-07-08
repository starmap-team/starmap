"""Admin prompts management endpoints — extracted from admin.py (Phase 7 admin domain split).

业务说明：提示词模板与 A/B 测试管理 API。
注册到 admin.py 的主 router（prefix="/admin"），最终路径形如 /admin/prompts/{name}。
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.core.extraction.prompt import (
    get_ab_test,
    get_active_version,
    get_prompt_template_raw,
    list_prompt_names,
    list_prompt_versions,
    register_prompt_version,
    set_ab_test,
    set_active_version,
    stop_ab_test,
)

# FE-02: A/B test result tracking (in-memory, process-local)
_ab_results: dict[str, list[dict[str, Any]]] = defaultdict(list)
_MAX_RESULTS_PER_PROMPT = 10000


class SetActiveRequest(BaseModel):
    version: str = Field(..., description="Target prompt version to activate, e.g. v1, v2")


class ABTestRequest(BaseModel):
    canary_version: str = Field(..., description="Candidate version")
    traffic_fraction: float = Field(
        default=0.1,
        ge=0.0,
        le=0.5,
        description="Traffic fraction sent to canary in (0.0, 0.5]",
    )


class RegisterVersionRequest(BaseModel):
    template: str = Field(..., description="Prompt template content with placeholders")
    version: str | None = Field(default=None, description="Version label, e.g. v4; auto-increment if omitted")
    activate: bool = Field(default=False, description="Activate this version immediately")


router = APIRouter(tags=["prompts"])


@router.get("/prompts")
async def list_prompts() -> dict[str, Any]:
    """List all prompt templates and versions."""
    result: dict[str, Any] = {}
    for name in list_prompt_names():
        versions = list_prompt_versions(name)
        active = get_active_version(name)
        ab = get_ab_test(name)
        result[name] = {
            "versions": versions,
            "active": active,
            "ab_test": ab.to_dict() if ab else None,
        }
    return result


@router.get("/prompts/{name}")
async def get_prompt_info(name: str) -> dict[str, Any]:
    """Return prompt metadata for a specific template."""
    try:
        versions = list_prompt_versions(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found") from None
    if not versions:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    active = get_active_version(name)
    ab = get_ab_test(name)
    return {
        "name": name,
        "versions": versions,
        "active": active,
        "ab_test": ab.to_dict() if ab else None,
    }


@router.get("/prompts/{name}/template")
async def get_prompt_template_content(name: str) -> dict[str, Any]:
    """Return raw prompt template content."""
    try:
        raw = get_prompt_template_raw(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found") from None
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found")
    return {"name": name, "template": raw}


@router.post("/prompts/{name}/versions")
async def create_prompt_version(
    name: str,
    req: RegisterVersionRequest,
) -> dict[str, Any]:
    """Register a new prompt version."""
    version = register_prompt_version(
        name=name,
        template=req.template,
        version=req.version,
        activate=req.activate,
    )
    logger.info(
        "Prompt '{}' registered version {} activate={}",
        name,
        version,
        req.activate,
    )
    return {
        "prompt": name,
        "registered_version": version,
        "active": get_active_version(name),
    }


@router.put("/prompts/{name}/active")
async def change_active_version(
    name: str,
    req: SetActiveRequest,
) -> dict[str, Any]:
    """Change the active prompt version."""
    try:
        set_active_version(name, req.version)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    logger.info("Prompt '{}' active version set to {}", name, req.version)
    return {
        "prompt": name,
        "active": get_active_version(name),
    }


@router.post("/prompts/{name}/ab-test")
async def start_ab_test(
    name: str,
    req: ABTestRequest,
) -> dict[str, Any]:
    """Start an A/B test for a prompt."""
    cfg = set_ab_test(
        prompt_name=name,
        canary_version=req.canary_version,
        traffic_fraction=req.traffic_fraction,
    )
    logger.info(
        "Prompt '{}' A/B test started with canary={} traffic={}",
        name,
        req.canary_version,
        req.traffic_fraction,
    )
    return {
        "prompt": name,
        "active": get_active_version(name),
        "ab_test": cfg.to_dict(),
    }


@router.delete("/prompts/{name}/ab-test")
async def remove_ab_test(name: str) -> dict[str, Any]:
    """Stop an A/B test for a prompt."""
    stop_ab_test(name)
    logger.info("Prompt '{}' A/B test removed", name)
    return {"prompt": name, "ab_test": None}


@router.get("/prompts/{name}/ab-test")
async def get_ab_test_config(name: str) -> dict[str, Any]:
    """Return current A/B test configuration, or null if none."""
    ab = get_ab_test(name)
    return {
        "prompt": name,
        "ab_test": ab.to_dict() if ab else None,
    }


# ── FE-02: A/B test result tracking ──


class ABResultRequest(BaseModel):
    """Record an A/B test result for aggregation."""
    version: str = Field(..., description="Prompt version used for this request")
    success: bool = Field(default=True, description="Whether the extraction succeeded")
    f1: float | None = Field(default=None, ge=0.0, le=1.0, description="F1 score if evaluated")
    latency_ms: float | None = Field(default=None, ge=0.0, description="Request latency in ms")


@router.post("/prompts/{name}/ab-results")
async def record_ab_result(name: str, req: ABResultRequest) -> dict[str, Any]:
    """Record an A/B test result for later analysis."""
    entry = {
        "version": req.version,
        "success": req.success,
        "f1": req.f1,
        "latency_ms": req.latency_ms,
        "timestamp": time.time(),
    }
    _ab_results[name].append(entry)
    # Cap results to prevent unbounded memory
    if len(_ab_results[name]) > _MAX_RESULTS_PER_PROMPT:
        _ab_results[name] = _ab_results[name][-_MAX_RESULTS_PER_PROMPT:]
    return {"prompt": name, "recorded": True}


@router.get("/prompts/{name}/ab-results")
async def get_ab_results(name: str) -> dict[str, Any]:
    """Get aggregated A/B test results for a prompt."""
    results = _ab_results.get(name, [])
    if not results:
        return {"prompt": name, "total": 0, "versions": {}}

    # Aggregate by version
    by_version: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0, "success_count": 0, "f1_sum": 0.0, "f1_count": 0,
        "latency_sum": 0.0, "latency_count": 0,
    })
    for r in results:
        v = r["version"]
        by_version[v]["count"] += 1
        if r["success"]:
            by_version[v]["success_count"] += 1
        if r["f1"] is not None:
            by_version[v]["f1_sum"] += r["f1"]
            by_version[v]["f1_count"] += 1
        if r["latency_ms"] is not None:
            by_version[v]["latency_sum"] += r["latency_ms"]
            by_version[v]["latency_count"] += 1

    # Compute averages
    summary = {}
    for v, stats in by_version.items():
        summary[v] = {
            "count": stats["count"],
            "success_rate": round(stats["success_count"] / stats["count"], 4),
            "avg_f1": round(stats["f1_sum"] / stats["f1_count"], 4) if stats["f1_count"] else None,
            "avg_latency_ms": round(stats["latency_sum"] / stats["latency_count"], 1) if stats["latency_count"] else None,
        }

    return {"prompt": name, "total": len(results), "versions": summary}
