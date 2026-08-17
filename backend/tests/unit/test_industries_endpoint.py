"""P1-D (2026-08-17): list_industries 必须返回「未分类」字面量当 DB 存在该桶。

历史 bug: list_industries SQL 写死 `industry != UNCLASSIFIED_INDUSTRY_LITERAL`，
87% 的「未分类」岗位无法被筛选 — 用户在「全部」视图翻 24 页才能找到。

修复: API 在「真实行业」列表后追加「未分类」字面量（仅在 DB 存在该桶时），
前端 chip 数组自然包含「未分类」，可点击触发 ?industry=未分类 过滤。

锁定契约: list_industries 返回值中「未分类」要么不存在（DB 真无未分类），
要么排在最后（特殊位置让用户清楚它是兜底桶）。
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL
from app.dependencies import get_current_user, get_db_session
from app.main import app


class _IndustriesFakeSession:
    """Mock session that returns configured industries + has_unclassified count."""

    def __init__(self, real_industries: list[str], has_unclassified: int) -> None:
        self._real = real_industries
        self._has_unclassified = has_unclassified
        self._call_count = 0

    async def execute(self, stmt, *args, **kwargs):
        self._call_count += 1
        # First call: real industries DISTINCT
        if self._call_count == 1:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self._real))
        # Second call: COUNT for has_unclassified check
        if self._call_count == 2:
            return SimpleNamespace(scalar=lambda: self._has_unclassified)
        # Fallback
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []),
                               scalar=lambda: 0)


def _run_list_industries(real_industries: list[str], has_unclassified: int):
    session = _IndustriesFakeSession(real_industries, has_unclassified)

    async def _override_session():
        yield session
    async def _override_user():
        return {"sub": str(uuid.uuid4()), "role": "admin", "username": "admin"}

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user] = _override_user
    try:
        client = TestClient(app)
        return client.get("/api/v1/positions/industries")
    finally:
        app.dependency_overrides.clear()


class TestListIndustriesIncludesUnclassified:
    """list_industries 必须把「未分类」字面量作为可筛选项暴露给前端。"""

    def test_real_industries_only_when_no_unclassified(self):
        """DB 无「未分类」桶时，API 不返回「未分类」（避免空 chip）。"""
        response = _run_list_industries(
            real_industries=["互联网/IT", "金融科技"],
            has_unclassified=0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "互联网/IT" in data["industries"]
        assert "金融科技" in data["industries"]
        assert UNCLASSIFIED_INDUSTRY_LITERAL not in data["industries"]

    def test_real_industries_plus_unclassified_appended(self):
        """DB 有「未分类」桶时，API 在真实行业列表后追加「未分类」字面量。"""
        response = _run_list_industries(
            real_industries=["互联网/IT", "金融科技"],
            has_unclassified=495,  # 真实环境：495 行「未分类」
        )
        assert response.status_code == 200
        data = response.json()
        assert "互联网/IT" in data["industries"]
        assert "金融科技" in data["industries"]
        assert UNCLASSIFIED_INDUSTRY_LITERAL in data["industries"]

    def test_unclassified_positioned_last(self):
        """「未分类」字面量必须排在真实行业之后（特殊位置语义）。"""
        response = _run_list_industries(
            real_industries=["互联网/IT", "金融科技", "智能制造"],
            has_unclassified=10,
        )
        assert response.status_code == 200
        data = response.json()
        # 真实行业按字母顺序排
        assert data["industries"][:3] == ["互联网/IT", "金融科技", "智能制造"]
        # 「未分类」始终在末尾
        assert data["industries"][-1] == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_real_industries_no_duplicates(self):
        """真实行业去重 — 这是 SQL DISTINCT 的责任，此测试验证 API 调用方传入的是 unique list。

        DB 层 SQL 已用 sa.distinct()，fake session 在这里只测 API 响应链路。
        """
        unique_industries = ["互联网/IT", "金融科技"]
        response = _run_list_industries(
            real_industries=unique_industries,
            has_unclassified=0,
        )
        data = response.json()
        # 验证 API 不会在「未分类」桶追加（无未分类数据时）
        assert UNCLASSIFIED_INDUSTRY_LITERAL not in data["industries"]
        assert data["industries"] == unique_industries
