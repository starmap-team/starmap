"""Phase 03 Plan 03 Task 7: APIRouter 子路由分片验证。

锁定 D-02 + 外部 import 兼容性 + 端点可达性契约。
"""
from __future__ import annotations

from pathlib import Path


def _flatten_routes(routes):
    """FastAPI 0.139 把 include_router 包装成 _IncludedRouter(无 .path) —
    递归展开其 subroutes, 返回所有叶子路由的 path 集合。"""
    paths: set[str] = set()
    for r in routes:
        sub = getattr(r, "routes", None)
        if sub:
            paths |= _flatten_routes(sub)
        elif getattr(r, "path", None):
            paths.add(r.path)
    return paths


class TestRouterStructure:
    """routes.py 与 events_routes.py 结构契约。"""

    def test_events_routes_module_exists(self):
        """events_routes 子模块必须存在（D-02 拆分起步）。"""
        from app.api.v1.pipeline import events_routes

        assert hasattr(events_routes, "router")
        assert hasattr(events_routes.router, "routes")

    def test_events_routes_has_no_pipeline_prefix(self):
        """events_routes 子 router 必须 prefix=''（避免 include_router 双前缀）。"""
        from app.api.v1.pipeline import events_routes

        # 父 router 已 prefix='/pipeline'，子 router 必须 prefix='' 防止 /pipeline/pipeline/...
        assert events_routes.router.prefix == "", (
            f"events_routes.router.prefix must be '' (was '{events_routes.router.prefix}') "
            "to avoid double-prefix when include_router'd into parent"
        )

    def test_events_routes_has_two_endpoints(self):
        """events_routes 必须含 /events 和 /events-poll 两个端点。"""
        from app.api.v1.pipeline import events_routes

        paths = _flatten_routes(events_routes.router.routes)
        assert "/events" in paths, "missing /events endpoint"
        assert "/events-poll" in paths, "missing /events-poll endpoint"

    def test_parent_router_excludes_events_router(self):
        """routes.py 父 router 不再 include events_routes(已移到独立 events_router,
        避免被 api_router 全局 get_current_user 拦截 — SSE 用 query token 鉴权)。"""

        routes_src = Path("app/api/v1/pipeline/routes.py").read_text(encoding="utf-8")
        assert "include_router(_events_router)" not in routes_src, (
            "routes.py must NOT include events_router (moved to events_router)"
        )

    def test_events_router_registered_separately(self):
        """events_routes 挂到独立的 events_router(无全局 get_current_user 依赖)。"""
        from app.api.v1.router import events_router

        paths = _flatten_routes(events_router.routes)
        assert "/pipeline/events" in paths, "events endpoint missing from events_router"
        assert "/pipeline/events-poll" in paths, "events-poll endpoint missing from events_router"

    def test_external_router_import_path_unchanged(self):
        """外部 import 路径必须保持：from app.api.v1.pipeline import router。"""
        from app.api.v1.pipeline import router

        assert router is not None
        # 父 router 含 status 等; events 已移到独立 events_router
        paths = _flatten_routes(router.routes)
        assert "/pipeline/status" in paths, "status endpoint missing (parent routes.py)"
        assert "/pipeline/events" not in paths, "events should be in events_router, not pipeline router"


class TestRouterSurface:
    """router 端点总数契约。"""

    def test_total_routes_at_least_21(self):
        """至少 21 端点（FastAPI 0.139 下 routes.py 实际 21 个, 2 个 events 独立）。"""
        from app.api.v1.pipeline import router

        flat = _flatten_routes(router.routes)
        assert len(flat) >= 21, (
            f"expected ≥21 routes, got {len(flat)}"
        )
