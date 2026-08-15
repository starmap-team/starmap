"""Phase 22 爬虫多源数据完整性回归测试（P0-1/P0-2/P0-4/P1-7）。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.pipeline.engine import _derive_run_record_counts
from app.core.pipeline.source_quality_sync import sync_source_quality
from app.core.pipeline.stages.crawl import build_spider_registry
from app.models.pipeline_models import DataSourceRecord


# ── P0-1 / P0-3 辅助：适配器能力与注册表 ──


def test_spider_registry_has_no_chinese_placeholder_platforms() -> None:
    """注册表只含真实 spider —— bosszhipin/lagou/zhaopin 等不得在采集路径上被当作可用源。"""
    registry = build_spider_registry()
    for fake in ("bosszhipin", "lagou", "liepin", "zhaopin", "51job", "linkedin"):
        assert fake not in registry, f"{fake} 无 spider 却出现在注册表（P0-1）"


def test_adapter_capability() -> None:
    """_adapter_capability：无 platform → 无适配器；已注册 platform → 有适配器（P0-3）。"""
    from app.api.v1.datasource import _adapter_capability

    class _DS:
        def __init__(self, config: dict) -> None:
            self.config = config

    assert _adapter_capability(_DS({"crawl_type": "playwright"})) == (False, None)
    assert _adapter_capability(_DS({"platform": "bosszhipin"})) == (False, "bosszhipin")
    assert _adapter_capability(_DS({"platform": "arbeitnow"})) == (True, "arbeitnow")
    assert _adapter_capability(_DS({"platform": "v2ex", "keyword": "python"})) == (True, "v2ex")


def test_crawl_config_builder_skips_platformless(monkeypatch) -> None:
    """P0-1 核心：无 platform/source_site 的源在 _get_crawl_configs 被跳过而非回退 v2ex。"""
    import app.core.pipeline.stages.crawl as crawl_mod
    from app.core.pipeline.stages.crawl import _get_crawl_configs

    class _DS:
        def __init__(self, name: str, config: dict) -> None:
            self.name = name
            self.config = config

    fake_sources = [
        _DS("bosszhipin", {"crawl_type": "playwright"}),   # 无 platform → P0-1 跳过
        _DS("Arbeitnow (远程)", {"platform": "arbeitnow"}),  # 有 platform → 保留
    ]

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def execute(self, stmt, *a, **kw):
            text = str(stmt)
            if "FROM pipeline_runs" in text or "from pipeline_runs" in text.lower():
                class _R:
                    def first(self):
                        return None
                return _R()
            class _S:
                def scalars(self):
                    class _All:
                        def all(self):
                            return fake_sources
                    return _All()
            return _S()

    class _FakeFactory:
        def __call__(self):
            return _FakeSession()

    monkeypatch.setattr(crawl_mod, "get_session_factory", lambda: _FakeFactory())

    async def run():
        return await _get_crawl_configs("run_id")

    import asyncio

    configs = asyncio.run(run())
    names = [c["source_name"] for c in configs]
    assert "bosszhipin" not in names, "无 platform 源必须被跳过，不得回退 v2ex（P0-1）"
    assert "Arbeitnow (远程)" in names
    assert configs[0]["platform"] == "arbeitnow"


# ── P0-2 归零 ──


@pytest.mark.asyncio
async def test_sync_source_quality_zeroes_ghost_source(db_session) -> None:
    """jd_raw 无行的 crawler 活动源记录数归零（P0-2）；有行源保持聚合值。"""
    ghost_name = f"zz_test_ghost_{uuid.uuid4().hex[:6]}"
    ghost = DataSourceRecord(
        id=uuid.uuid4(),
        name=ghost_name,
        source_type="crawler",
        authority_score=0.7,
        status="active",
        total_records=235,
        valid_records=223,
        duplicate_rate=0.1,
        avg_quality_score=0.9,
        config={"crawl_type": "playwright"},
    )
    db_session.add(ghost)
    await db_session.commit()

    try:
        result = await sync_source_quality(db_session)
        # 刷新后断言归零
        await db_session.refresh(ghost)
        assert ghost.total_records == 0, "无 jd_raw 行的 crawler 源必须归零（P0-2）"
        assert ghost.valid_records == 0
        assert ghost.avg_quality_score == pytest.approx(0.9), "权威度/质量分保留（配置值）"
        entry = result.get(ghost_name)
        assert entry and entry.get("zeroed") is True
    finally:
        await db_session.delete(ghost)
        await db_session.commit()


# ── P1-7 run 字段语义 ──


def test_derive_run_record_counts_zero_new_kept() -> None:
    """records_new=0（全部重复）不得回退为 crawl_records（P1-7 回归锁）。"""
    new_r, updated_r = _derive_run_record_counts(
        {"records_new": 0, "records_duplicate": 85}, crawl_records=85
    )
    assert new_r == 0, "records_new=0 必须保留 0，不得回退为 85"
    assert updated_r == 85


def test_derive_run_record_counts_missing_fallback() -> None:
    """字段缺省（None）时回退 crawl_records（向后兼容）。"""
    new_r, updated_r = _derive_run_record_counts({"records_duplicate": 5}, crawl_records=30)
    assert new_r == 30
    assert updated_r == 5
