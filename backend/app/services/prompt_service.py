"""Prompt service layer — thin re-export of the prompt registry/AB-test API.

Layer-boundary rule: api/v1 → services → core. admin_prompts.py must not
import app.core.extraction.prompt directly.
"""
from __future__ import annotations

from app.core.extraction.prompt import (  # noqa: F401 — §prompt re-export (路由经 service 访问 core)
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

__all__ = [
    "get_ab_test",
    "get_active_version",
    "get_prompt_template_raw",
    "get_prompt_version_content",
    "list_prompt_names",
    "list_prompt_versions",
    "register_prompt_version",
    "set_ab_test",
    "set_active_version",
    "stop_ab_test",
]
