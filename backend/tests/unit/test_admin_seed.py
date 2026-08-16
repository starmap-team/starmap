"""Unit tests for admin seed/reset — service layer (设计文档 §2.3.3.2)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.schemas.admin import SeedResetResponse
from app.services.admin_seed_service import run_demo_seed


def _settings_mock(app_env: str) -> MagicMock:
    s = MagicMock()
    s.app_env = app_env
    return s


# ── 生产守卫 ──


async def test_refuses_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=production 时拒绝执行，不做任何写入。"""
    monkeypatch.setattr(
        "app.services.admin_seed_service.get_settings",
        lambda: _settings_mock("production"),
    )
    res = await run_demo_seed()
    assert res.refused is True
    assert res.seeded == []
    assert res.skipped == []
    assert "生产环境" in res.message


# ── 开发/评审环境正常路径 ──


async def test_seed_runs_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """开发环境顺序执行种子；成功项进 seeded，失败项进 skipped。"""

    async def fake_run_one(script: str) -> tuple[bool, str]:
        ok = script != "seed_skill_timeseries.py"
        return ok, f"[{script}] {'done' if ok else 'boom'}"

    monkeypatch.setattr(
        "app.services.admin_seed_service.get_settings",
        lambda: _settings_mock("development"),
    )
    monkeypatch.setattr("app.services.admin_seed_service._run_one", fake_run_one)

    res = await run_demo_seed()

    assert res.refused is False
    assert "seed_pipeline_data.py" in res.seeded
    assert "seed_evolution_snapshots.py" in res.seeded
    assert "seed_skill_timeseries.py" in res.skipped
    assert res.message


async def test_timeout_goes_to_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """种子脚本超时视为跳过而非崩溃。"""

    async def slow_run_one(script: str) -> tuple[bool, str]:
        return False, f"[{script}] timeout after 120s"

    monkeypatch.setattr(
        "app.services.admin_seed_service.get_settings",
        lambda: _settings_mock("development"),
    )
    monkeypatch.setattr("app.services.admin_seed_service._run_one", slow_run_one)

    res = await run_demo_seed()
    assert res.refused is False
    assert res.seeded == []
    assert set(res.skipped) == set(res.seeded) | set(res.skipped)  # 全部跳过
    assert len(res.skipped) == 3


# ── Schema 契约 ──


def test_schema_roundtrip() -> None:
    """SeedResetResponse 字段与契约一致（seeded/skipped/refused/message）。"""
    r = SeedResetResponse(
        seeded=["seed_pipeline_data.py"],
        skipped=[],
        refused=False,
        message="done",
    )
    assert r.refused is False
    assert r.seeded == ["seed_pipeline_data.py"]
    assert SeedResetResponse(refused=True, message="x").refused is True


def test_seed_reset_route_registered() -> None:
    """POST /admin/seed/reset 已注册在 admin 路由上。"""
    from fastapi.routing import APIRoute

    from app.api.v1.admin import router

    paths = [r.path for r in router.routes if isinstance(r, APIRoute)]
    assert "/admin/seed/reset" in paths
