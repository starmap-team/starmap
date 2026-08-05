"""契约回归: admin_prompts 路由零内联模型 (PLAN-014 批次7)。

锁定 4 个 Request 模型已迁入 schemas/prompt.py, 路由文件不再内联。
契约防御: ABResultRequest.success 默认 True, 约定与原路由一致。
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from app.api.v1 import admin_prompts as prompts_router
from app.schemas.prompt import (
    ABResultRequest,
    ABTestRequest,
    RegisterVersionRequest,
    SetActiveRequest,
)


def _inline_models(module: Any) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    ]


class TestPromptsRouteModelCentralization:
    """路由文件不得内联定义 Pydantic 模型 (AGENTS.md 集中约定)."""

    def test_prompts_route_has_no_inline_models(self) -> None:
        assert _inline_models(prompts_router) == []


class TestPromptSchemasExported:
    """4 个 Request 类已集中导出."""

    def test_all_exports_reachable(self) -> None:
        from app.schemas import (  # noqa: F401
            ABResultRequest as A,
            ABTestRequest as B,
            RegisterVersionRequest as C,
            SetActiveRequest as D,
        )
        assert all((A, B, C, D))

    def test_ab_result_request_success_default_true(self) -> None:
        """约定保持: 不传 success 默认 True, 与原路由一致."""
        req = ABResultRequest(version="v1")
        assert req.success is True
        assert req.f1 is None
        assert req.latency_ms is None

    def test_ab_test_request_traffic_bounds(self) -> None:
        """A/B 流量分桶: 0.0-0.5 之间."""
        with_valid = ABTestRequest(canary_version="v2", traffic_fraction=0.1)
        assert with_valid.traffic_fraction == 0.1
        # 超出 0.5 应报错
        import pytest
        with pytest.raises(ValueError):
            ABTestRequest(canary_version="v2", traffic_fraction=0.6)

    def test_register_version_minimum_required(self) -> None:
        """template 必填, version/activate 有默认值."""
        req = RegisterVersionRequest(template="hello {{name}}")
        assert req.template == "hello {{name}}"
        assert req.version is None
        assert req.activate is False
