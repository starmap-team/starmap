"""Phase 1 多层防御 (2026-08-17): stage3_services 主写入路径 industry 归一化测试。

锁定 backend/app/tasks/stage3_services.py 的 _upsert_position 行为：
1. 新岗位创建时 industry 必须经 normalize_industry() 落库
   （None/空/模糊词 → 「未分类」字面量；alias → canonical 桶）
2. 已存在岗位 industry 缺失时也回填 normalize 后的值
3. 主抽取路径 run_batch_extract_jd 的 data.industry 能传到 _upsert_position

背景：实测 96 行 system:pipeline 空 industry 是 _upsert_position 创建
PositionRecord 时漏传 industry 字段（ORM 默认 None）导致 —— 4 层防御
中 graph_writer/extract_repo/admin_audit 都改了，唯独漏了这条主写入路径。
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL
from app.tasks.stage3_services import _upsert_position


class _FakeSession:
    """最小化 session fake：覆盖 position 查询 + add + flush。"""

    def __init__(self, existing: object | None = None) -> None:
        self._existing = existing
        self.added: list[object] = []
        self.flushed = 0

    async def execute(self, stmt, *args, **kwargs):
        return SimpleNamespace(scalar_one_or_none=lambda: self._existing)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1


def _make_existing(industry: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="已有岗位",
        name_cn=None,
        industry=industry,
        source_run_id=None,
        created_by="system:pipeline",
    )


class TestUpsertPositionNewIndustry:
    """新岗位创建时 industry 必须经 normalize_industry() 落库。"""

    @pytest.mark.asyncio
    async def test_new_position_with_real_industry_normalized(self):
        """真实 canonical 行业原样落库。"""
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "Python 后端工程师", industry="互联网/IT")
        assert pos.industry == "互联网/IT"
        assert session.added == [pos]

    @pytest.mark.asyncio
    async def test_new_position_with_alias_normalized_to_canonical(self):
        """alias「信息技术/互联网」→ canonical「互联网/IT」落库。"""
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "高级工程师", industry="信息技术/互联网")
        assert pos.industry == "互联网/IT", (
            f"alias must normalize to canonical, got {pos.industry!r}"
        )

    @pytest.mark.asyncio
    async def test_new_position_with_none_becomes_unclassified(self):
        """industry=None → 「未分类」字面量（此前 ORM 默认 None 是根因）。"""
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "No Industry Job", industry=None)
        assert pos.industry == UNCLASSIFIED_INDUSTRY_LITERAL

    @pytest.mark.asyncio
    async def test_new_position_with_empty_becomes_unclassified(self):
        """industry='' → 「未分类」字面量。"""
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "Empty Industry Job", industry="")
        assert pos.industry == UNCLASSIFIED_INDUSTRY_LITERAL

    @pytest.mark.asyncio
    async def test_new_position_with_generic_becomes_unclassified(self):
        """industry='通用' → 「未分类」字面量。"""
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "Generic Job", industry="通用")
        assert pos.industry == UNCLASSIFIED_INDUSTRY_LITERAL


class TestUpsertPositionExistingBackfill:
    """已存在岗位 industry 缺失时回填 normalize 后的值。"""

    @pytest.mark.asyncio
    async def test_existing_empty_industry_backfilled(self):
        """已存在岗位 industry='' 时，新抽取的 industry 回填 canonical。"""
        existing = _make_existing(industry="")
        session = _FakeSession(existing=existing)
        pos = await _upsert_position(session, "已有岗位", industry="互联网/IT")
        assert pos is existing  # 复用已有行
        assert existing.industry == "互联网/IT", "empty industry should be backfilled"

    @pytest.mark.asyncio
    async def test_existing_none_industry_backfilled(self):
        """已存在岗位 industry=None 时回填。"""
        existing = _make_existing(industry=None)
        session = _FakeSession(existing=existing)
        pos = await _upsert_position(session, "已有岗位", industry="金融科技")
        assert pos is existing
        assert existing.industry == "金融科技"

    @pytest.mark.asyncio
    async def test_existing_real_industry_not_overwritten(self):
        """已存在岗位已有真实行业时不覆盖（保留审核过的值）。"""
        existing = _make_existing(industry="互联网/IT")
        session = _FakeSession(existing=existing)
        pos = await _upsert_position(session, "已有岗位", industry="金融科技")
        assert pos is existing
        assert existing.industry == "互联网/IT", "existing real industry must be preserved"

    @pytest.mark.asyncio
    async def test_existing_unclassified_not_overwritten(self):
        """已存在「未分类」岗位：新抽取到真实行业时**不覆盖**。

        设计决策 (2026-08-17): 「未分类」是 040 迁移 / admin 审核后显式写入的
        字面量，不是「缺失值」。_upsert_position 只回填 None / ''（真正缺失），
        不覆盖「未分类」—— 避免 pipeline 重复抽取时用 LLM 的一次性结果
        覆盖掉 admin 已审定的行业。存量「未分类」由 backfill 脚本 / admin
        手动 reclassify 治理。
        """
        existing = _make_existing(industry=UNCLASSIFIED_INDUSTRY_LITERAL)
        session = _FakeSession(existing=existing)
        pos = await _upsert_position(session, "已有岗位", industry="销售/营销")
        assert pos is existing
        assert existing.industry == UNCLASSIFIED_INDUSTRY_LITERAL

    @pytest.mark.asyncio
    async def test_existing_with_no_new_industry_keeps_value(self):
        """已存在岗位无新 industry 输入时保留原值。"""
        existing = _make_existing(industry=UNCLASSIFIED_INDUSTRY_LITERAL)
        session = _FakeSession(existing=existing)
        pos = await _upsert_position(session, "已有岗位", industry=None)
        assert pos is existing
        assert existing.industry == UNCLASSIFIED_INDUSTRY_LITERAL


class TestUpsertPositionReturnsCreatedRecord:
    """新岗位返回创建记录，且其他字段正确。"""

    @pytest.mark.asyncio
    async def test_created_by_system_pipeline(self):
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "新岗位", industry="智能制造")
        assert pos.created_by == "system:pipeline"

    @pytest.mark.asyncio
    async def test_name_and_name_cn_set(self):
        session = _FakeSession(existing=None)
        pos = await _upsert_position(session, "新岗位", name_cn="新岗位中文", industry="医疗健康")
        assert pos.name == "新岗位"
        assert pos.name_cn == "新岗位中文"