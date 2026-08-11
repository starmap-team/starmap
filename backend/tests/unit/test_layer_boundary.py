"""Layer boundary tests.

Verifies that the module dependency rules are followed:
- api/v1/ -> services/ -> core/
- No direct api/v1/ -> core/ imports
"""
from __future__ import annotations

import ast
import pathlib


def _get_imports(filepath: str) -> list[tuple[str, str]]:
    """Return (module, name) import tuples from a Python file."""
    tree = ast.parse(pathlib.Path(filepath).read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(("", alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append((mod, alias.name))
    return imports


API_ROUTE_FILES = [
    "app/api/v1/evolution.py",
    "app/api/v1/extract.py",
    "app/api/v1/judge.py",
    "app/api/v1/learning.py",
    "app/api/v1/match.py",
    "app/api/v1/position.py",
    "app/api/v1/quality.py",
    "app/api/v1/resume.py",
    "app/api/v1/evolution_emerging_alerts.py",
    "app/api/v1/evolution_industry_report.py",
    "app/api/v1/evolution_career_path.py",
    "app/api/v1/admin_graph_nodes.py",
    "app/api/v1/admin_prompts.py",
    "app/api/v1/admin_data_truth.py",
    "app/api/v1/admin.py",
    "app/api/v1/auth.py",
    "app/api/v1/dashboard.py",
    "app/api/v1/datasource.py",
    "app/api/v1/loop.py",
    "app/api/v1/quality_trends_alerts.py",
    "app/api/v1/pipeline/routes.py",
    # Phase 03 Plan 03 Task 7: pipeline 按领域拆 6 子路由，逐一纳入层边界守卫
    "app/api/v1/pipeline/status_routes.py",
    "app/api/v1/pipeline/runs_routes.py",
    "app/api/v1/pipeline/trigger_routes.py",
    "app/api/v1/pipeline/schedule_routes.py",
    "app/api/v1/pipeline/config_routes.py",
    "app/api/v1/pipeline/events_routes.py",
]

# 纯数据/格式常量模块豁免：常量无业务副作用，路由直接引用安全
# （app.core.constants / app.core.*.constants / app.core.validation.errors）
_EXEMPT_CONSTANTS = ("app.core.constants", ".constants", "app.core.validation.errors")

# 纯聚合入口：routes.py 仅 include_router 子路由，无业务逻辑（D-02 Task 7），
# 业务逻辑经 app.services 的导入断言由各子路由承担。
_AGGREGATION_ROUTES = {"app/api/v1/pipeline/routes.py"}

# 无业务服务依赖：config_routes.py 端点仅读写 settings（app.config），非业务逻辑层。
_NO_SERVICES_DEPS = {"app/api/v1/pipeline/config_routes.py"}


def test_api_routes_do_not_import_core_directly():
    """API routes must go through services/ layer, not core/ directly."""
    violations = []
    for rel_path in API_ROUTE_FILES:
        imports = _get_imports(rel_path)
        for mod, name in imports:
            if mod.startswith("app.core") or name.startswith("app.core"):
                if any(s in mod for s in _EXEMPT_CONSTANTS):
                    continue
                violations.append(f"{rel_path}: {mod}.{name}")
    assert not violations, (
        f"API routes importing from core/ directly: {violations}"
    )


def test_api_routes_import_from_services():
    """API routes should import from services/ for business logic."""
    for rel_path in API_ROUTE_FILES:
        if rel_path in _AGGREGATION_ROUTES or rel_path in _NO_SERVICES_DEPS:
            continue  # 聚合入口 / 纯 settings 端点，无业务服务依赖
        imports = _get_imports(rel_path)
        service_imports = [
            (mod, name) for mod, name in imports
            if mod.startswith("app.services") or name.startswith("app.services")
        ]
        assert service_imports, (
            f"{rel_path} has no imports from services/ layer"
        )
