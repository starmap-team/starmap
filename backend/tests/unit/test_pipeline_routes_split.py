"""Phase 03 Plan 03 Task 7: APIRouter 子路由分片验证。

锁定 D-02 + 外部 import 兼容性 + 端点可达性契约。
"""
from __future__ import annotations

from pathlib import Path


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

        paths = {r.path for r in events_routes.router.routes}
        assert "/events" in paths, "missing /events endpoint"
        assert "/events-poll" in paths, "missing /events-poll endpoint"

    def test_parent_router_includes_events_router(self):
        """routes.py 父 router 必须 include_router events_routes。"""

        routes_src = Path("app/api/v1/pipeline/routes.py").read_text(encoding="utf-8")
        assert "from app.api.v1.pipeline.events_routes import" in routes_src, (
            "routes.py must import events_routes"
        )
        assert "router.include_router(_events_router)" in routes_src, (
            "routes.py must include_router events_router"
        )

    def test_external_router_import_path_unchanged(self):
        """外部 import 路径必须保持：from app.api.v1.pipeline import router。"""
        from app.api.v1.pipeline import router

        assert router is not None
        # 至少含 /events + /events-poll + 父 routes.py 中的 status 等
        paths = {r.path for r in router.routes}
        assert "/pipeline/events" in paths, "events endpoint missing from final router"
        assert "/pipeline/events-poll" in paths, "events-poll endpoint missing"
        assert "/pipeline/status" in paths, "status endpoint missing (parent routes.py)"


class TestRouterSurface:
    """router 端点总数契约。"""

    def test_total_routes_at_least_24(self):
        """至少 24 端点（22 from routes.py + 2 from events_routes）。"""
        from app.api.v1.pipeline import router

        assert len(router.routes) >= 24, (
            f"expected ≥24 routes, got {len(router.routes)}"
        )
