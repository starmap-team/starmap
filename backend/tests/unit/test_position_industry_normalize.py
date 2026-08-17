"""P0-B (2026-08-17): get_position 详情接口 industry 必须是非空字面量。

契约 (app/core/extraction/industry.py):
- DB industry 列在 040 迁移后永远是非空字符串（CHECK 约束 + literal backfill）。
- 即便如此，get_position 必须做 `r.industry or UNCLASSIFIED_INDUSTRY_LITERAL` 兜底——
  Neo4j fallback 路径可能绕过 PG CHECK，且未来若有写入绕过 normalize_industry()，
  详情接口不能输出空串（前端 PositionDetail.vue 的 chip 渲染会失败）。

锁定契约：industry 永远是非空字面量，要么是「未分类」要么是真实行业。
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL
from app.dependencies import get_current_user, get_db_session, get_neo4j_driver
from app.main import app


def _make_pos_row(industry, *, review_status: str = "approved"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=f"Test Position {uuid.uuid4()}",
        name_cn="",
        industry=industry,
        description="",
        created_at=None,
        review_status=review_status,
    )


class _FakeSession:
    """Minimal fake session — supports position query (scalar_one_or_none)
    and skills join query (.all()).

    The route's first call hits scalar_one_or_none (PositionRecord lookup),
    the second hit is the skill join query which expects rows that have
    .skill_id etc. — we return empty list so skills_required is empty."""

    def __init__(self, row) -> None:
        self._row = row
        self._call_count = 0

    async def execute(self, stmt, *args, **kwargs):
        self._call_count += 1
        if self._call_count == 1:
            # PositionRecord lookup
            return SimpleNamespace(scalar_one_or_none=lambda: self._row)
        # Subsequent queries (skills join) — return empty rows
        return SimpleNamespace(all=lambda: [])


def _install_overrides(row):
    async def _override_session():
        yield _FakeSession(row)
    async def _override_user():
        return {"sub": str(uuid.uuid4()), "role": "admin", "username": "admin"}
    def _override_driver():
        return None

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_neo4j_driver] = _override_driver


def _cleanup_overrides():
    app.dependency_overrides.clear()


def _get_position_response(industry_value):
    row = _make_pos_row(industry_value)
    _install_overrides(row)
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/positions/{row.id}")
        return response
    finally:
        _cleanup_overrides()


class TestGetPositionIndustryFallback:
    """get_position 必须保证 industry 字段永远是非空字面量。"""

    def test_empty_string_fallback_to_unclassified(self):
        """industry='' → 「未分类」字面量。"""
        response = _get_position_response("")
        assert response.status_code == 200, response.text
        assert response.json()["industry"] == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_none_fallback_to_unclassified(self):
        """industry=None (DB legacy) → 「未分类」字面量。"""
        response = _get_position_response(None)
        assert response.status_code == 200, response.text
        assert response.json()["industry"] == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_whitespace_fallback_to_unclassified(self):
        """industry='   ' (历史空白数据) → 「未分类」字面量。"""
        response = _get_position_response("   ")
        assert response.status_code == 200, response.text
        assert response.json()["industry"] == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_real_industry_preserved(self):
        """真实行业（如「互联网/IT」）原样保留。"""
        response = _get_position_response("互联网/IT")
        assert response.status_code == 200
        assert response.json()["industry"] == "互联网/IT"

    def test_unclassified_literal_preserved(self):
        """已经是「未分类」字面量的 industry 不被二次转换。"""
        response = _get_position_response(UNCLASSIFIED_INDUSTRY_LITERAL)
        assert response.status_code == 200
        assert response.json()["industry"] == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_industry_never_empty_in_response(self):
        """响应里 industry 字段永远不是空字符串（前端 chip 兜底依赖）。"""
        for bad in ("", None, "   "):
            response = _get_position_response(bad)
            data = response.json()
            assert data["industry"], f"empty industry for bad input {bad!r}"
            assert data["industry"] == UNCLASSIFIED_INDUSTRY_LITERAL
