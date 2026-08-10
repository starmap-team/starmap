"""Admin prompts management endpoints — thin HTTP layer.

Business logic for A/B aggregation lives in app.services.admin_ab_service.
Prompt version management delegates to app.core.extraction.prompt.
This file only handles: request parsing, storage routing (Redis vs in-memory),
domain-exception → HTTP-exception mapping, and response serialization.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_redis_client
from app.models.prompt_version import PromptVersion
from app.schemas.prompt import (
    ABResultRequest,
    ABTestRequest,
    RegisterVersionRequest,
    SetActiveRequest,
)
from app.services.admin_ab_service import aggregate_ab_results
from app.services.prompt_service import (
    get_ab_test,
    get_active_version,
    get_prompt_template_raw,
    get_prompt_version_content,
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


# 4 个 Request 类已迁入 schemas/prompt.py 集中管理 (PLAN-014 批次7)

router = APIRouter(tags=["prompts"])


def _build_serving_version(active: str | None, ab: Any) -> tuple[str | None, str]:
    """BUG-14 fix: compute `serving_version` and `serving_source`.

    When an A/B test is configured with a canary_version, real traffic
    splits between active (control) and canary. Surface that distinction so
    the UI can show "this version is being served right now" rather than
    just "this is the active version".
    """
    ab_dict = ab.to_dict() if ab else None
    if ab_dict and ab_dict.get("canary_version"):
        return ab_dict["canary_version"], "canary"
    return active, "active"


@router.get("/prompts")
async def list_prompts() -> dict[str, Any]:
    """List all prompt templates and versions."""
    result: dict[str, Any] = {}
    for name in list_prompt_names():
        versions = list_prompt_versions(name)
        active = get_active_version(name)
        ab = get_ab_test(name)
        serving, source = _build_serving_version(active, ab)
        result[name] = {
            "versions": versions,
            "active": active,
            "ab_test": ab.to_dict() if ab else None,
            "serving_version": serving,
            "serving_source": source,
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
    serving, source = _build_serving_version(active, ab)
    return {
        "name": name,
        "versions": versions,
        "active": active,
        "ab_test": ab.to_dict() if ab else None,
        "serving_version": serving,
        "serving_source": source,
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Register a new prompt version."""
    # ponytail: 持久化优先 —— 先落 prompt_versions 表（重启不丢），再更新内存注册表
    if req.activate:
        await session.execute(
            update(PromptVersion)
            .where(PromptVersion.prompt_name == name)
            .values(is_active=False)
        )
    existing = (
        await session.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_name == name,
                PromptVersion.version == req.version,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(PromptVersion(
            prompt_name=name,
            version=req.version,
            content=req.template,
            is_active=bool(req.activate),
        ))
    else:
        existing.content = req.template
        if req.activate:
            existing.is_active = True
    await session.commit()

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
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Change the active prompt version."""
    try:
        set_active_version(name, req.version)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    # ponytail: 持久化活跃选择 —— 该 (name, version) 若已注册则置 active，
    # 否则（内置版本）插入快照行
    await session.execute(
        update(PromptVersion)
        .where(PromptVersion.prompt_name == name)
        .values(is_active=False)
    )
    row = (
        await session.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_name == name,
                PromptVersion.version == req.version,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # 内置版本激活：插入空 content 快照（仅记录活跃标记，不覆盖内置模板）
        try:
            get_prompt_version_content(name, req.version)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        session.add(PromptVersion(
            prompt_name=name,
            version=req.version,
            content="",
            is_active=True,
        ))
    else:
        row.is_active = True
    await session.commit()
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
# ABResultRequest 已迁入 schemas/prompt.py (PLAN-014 批次7)


@router.post("/prompts/{name}/ab-results")
async def record_ab_result(name: str, req: ABResultRequest, redis: Any = Depends(get_redis_client)) -> dict[str, Any]:
    """Record an A/B test result for later analysis."""
    entry = {
        "version": req.version,
        "success": req.success,
        "f1": req.f1,
        "latency_ms": req.latency_ms,
        "timestamp": time.time(),
    }

    if redis is not None:
        key = f"ab:results:{name}"
        await redis.lpush(key, json.dumps(entry))
        await redis.ltrim(key, 0, _MAX_RESULTS_PER_PROMPT - 1)
    else:
        _ab_results[name].append(entry)
        if len(_ab_results[name]) > _MAX_RESULTS_PER_PROMPT:
            _ab_results[name] = _ab_results[name][-_MAX_RESULTS_PER_PROMPT:]

    return {"prompt": name, "recorded": True}


@router.get("/prompts/{name}/ab-results")
async def get_ab_results(name: str, redis: Any = Depends(get_redis_client)) -> dict[str, Any]:
    """Get aggregated A/B test results for a prompt.

    BUG-13 fix: surface data-source warning when Redis is unavailable and
    we fall back to in-memory dict. In-memory dict resets on backend
    restart, which silently destroys A/B history. Frontend now sees
    `data_source: "in_memory_stale"` and can warn the admin.
    """
    results: list[dict[str, Any]] = []
    data_source = "redis"

    if redis is not None:
        key = f"ab:results:{name}"
        raw_results = await redis.lrange(key, 0, -1)
        for raw in raw_results:
            try:
                results.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    else:
        data_source = "in_memory_stale"
        results = _ab_results.get(name, [])

    aggregated = aggregate_ab_results(results)
    return {"prompt": name, "data_source": data_source, **aggregated}
