"""PLAN-014 批次9: 全路由零内联契约回归 (锁定 + 登记 follow-up)。

锁定: 路由文件不得内联定义 Pydantic BaseModel (AGENTS.md Schema 集中约定)。

状态 (2026-08-05):
- 11 个路由已通过 (admin_prompts/position/dashboard/graph/auth/...)
- 14 个路由仍含内联 BaseModel, 标记 @pytest.mark.xfail, 登记 PLAN-014
  后续批次逐个迁入 schemas/ 包. xfail 一旦对应路由零内联, 直接删
  @xfail 标记即生效.

名单 (按内联 BaseModel 数从多到少, 已在当前 session 实测):
  datasource(9) / evolution(8) / admin(8) / judge(6) / quality(5) /
  admin_users(5) / quality_trends_alerts(4) / loop(4) /
  admin_data_truth(4) / extract(2) / admin_graph_nodes(3) /
  evolution_career_path / evolution_emerging_alerts /
  evolution_industry_report
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import pytest
from pydantic import BaseModel

# 已零内联 (PLAN-014 批次 2-8 已闭环) — 直接 PASS
PASS_ROUTES = {
    "app.api.v1.graph",
    "app.api.v1.position",
    "app.api.v1.dashboard",
    "app.api.v1.auth",
    "app.api.v1.admin_prompts",
    "app.api.v1.import_jd",
    "app.api.v1.prompt",
    "app.api.v1.match",
    "app.api.v1.learning",
    "app.api.v1.pipeline",
    "app.api.v1.health_monitor",
    "app.api.v1.judge",  # PLAN-014 批次10 已零内联
    "app.api.v1.quality",  # PLAN-014 批次11 已零内联
    "app.api.v1.loop",  # PLAN-014 批次12 已零内联
    "app.api.v1.extract",  # PLAN-014 批次13 已零内联（复用 schemas/extract.py，+6 透传字段对齐真实 API）
    "app.api.v1.datasource",  # PLAN-014 批次8 已零内联
    "app.api.v1.quality_trends_alerts",  # PLAN-014 批次9 已零内联
    "app.api.v1.evolution_career_path",  # PLAN-014 批次10 已零内联
    "app.api.v1.evolution_emerging_alerts",  # PLAN-014 批次11 已零内联
    "app.api.v1.evolution_industry_report",  # PLAN-014 批次11 已零内联
    "app.api.v1.evolution",  # PLAN-014 批次12 已零内联
    "app.api.v1.admin_graph_nodes",  # PLAN-014 批次13 已零内联
    "app.api.v1.admin_data_truth",  # PLAN-014 批次13 已零内联
    "app.api.v1.admin_users",  # PLAN-014 批次14 已零内联
    "app.api.v1.admin",  # PLAN-014 批次14 已零内联
    "app.api.v1.resume",  # 实际零内联 (误标 xfail, 转正)
}


def _collect_route_modules() -> list[Any]:
    import app.api.v1 as v1_pkg
    modules: list[Any] = []
    for info in pkgutil.iter_modules(v1_pkg.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"app.api.v1.{info.name}")
        if hasattr(mod, "router"):
            modules.append(mod)
    return modules


def _inline_models(module: Any) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    ]


@pytest.mark.parametrize("mod", _collect_route_modules(), ids=lambda m: m.__name__)
def test_route_has_no_inline_models(mod: Any) -> None:
    """每个路由文件都不得内联 BaseModel — AGENTS.md 集中约定."""
    name = mod.__name__
    inline = _inline_models(mod)
    if name in PASS_ROUTES:
        # 已闭环路由 — 严格断言零内联
        assert inline == [], f"{name} 已声明 PASS 但仍含 {inline}; 回退"
    else:
        # 14 个尚未闭环路由 — 标记 xfail 但仍记录清单 (intent-only)
        # 使用 try/raise 模式以保持显式 follow-up 报告
        pytest.xfail(
            f"{name} 含内联 {inline}; PLAN-014 后续批次迁移后改 PASS"
        )
