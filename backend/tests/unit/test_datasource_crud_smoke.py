"""P1.3 smoke: datasource CRUD 路由契约锁定（C-5 覆盖缺口）。

锁定 ``app.api.v1.datasource`` 当前真实契约（2026-08-11 实测）：
- ``router`` (prefix=/datasources)：list / detail / update / stats / sync / health
- ``admin_router`` (prefix=/admin/datasources)：admin list / admin create

注意（与早期草稿的差异）：
- 创建端点是 ``POST /admin/datasources``（admin 鉴权），不是 ``POST /datasources``
- 后端**暂无** datasource DELETE 端点 —— 不在此断言，留给 M4 规划决策
- fixture builder（_build_fixture_records / _fixture_source_pairs）在 stages/crawl.py
  中不存在，原草稿测试无法收集，已移除
"""
from __future__ import annotations

from app.api.v1.datasource import admin_router, router

_METHODS = {"GET", "POST", "PUT", "DELETE"}


def _method_paths(routers) -> dict[str, set[str]]:
    by_method: dict[str, set[str]] = {}
    for r in routers:
        for route in r.routes:
            for m in (getattr(route, "methods", None) or set()) & _METHODS:
                by_method.setdefault(m, set()).add(route.path)
    return by_method


def test_datasource_public_router_contract():
    """/datasources 前缀路由：list / detail / update / delete(软) / stats / sync / health 齐全。"""
    by_method = _method_paths([router])
    assert "/datasources" in by_method["GET"]            # list
    assert "/datasources/{source_id}" in by_method["GET"]     # detail
    assert "/datasources/{source_id}" in by_method["PUT"]     # update
    assert "/datasources/{source_id}" in by_method["DELETE"]  # soft-delete (D5 补全 CRUD)
    assert "/datasources/{source_id}/stats" in by_method["GET"]
    assert "/datasources/{source_id}/sync" in by_method["POST"]
    assert "/datasources/health" in by_method["GET"]


def test_datasource_admin_router_contract():
    """/admin/datasources 前缀路由：admin list + admin create。"""
    by_method = _method_paths([admin_router])
    assert "/admin/datasources" in by_method["GET"]       # admin list
    assert "/admin/datasources" in by_method["POST"]      # admin create
