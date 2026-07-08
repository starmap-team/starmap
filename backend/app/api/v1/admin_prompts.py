"""Admin prompts management endpoints — extracted from admin.py (Phase 7 admin domain split).

业务说明：提示词模板与 A/B 测试管理 API。
注册到 admin.py 的主 router（prefix="/admin"），最终路径形如 /admin/prompts/{name}。
"""
from __future__ import annotations

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
    versions = list_prompt_versions(name)
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
    raw = get_prompt_template_raw(name)
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
        prompt_name=name,
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
    set_active_version(name, req.version)
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
