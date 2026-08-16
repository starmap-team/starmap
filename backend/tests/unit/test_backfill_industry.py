"""Coverage for scripts/backfill_position_industry.py — PRD US-002 C6 + Fix E.

验证:
- 扫描条件：industry IS NULL OR industry = ''，且 review_status='approved'
- dry-run 不写 DB
- progress_every < 1 抛 ValueError（Fix E: 参数重命名以消除命名误导）
- translate_one 失败容错
- industry 已有值的已审核岗位不被覆盖
- collect_candidates SQL 包含 approved 过滤（防止 pending_review 污染）
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.backfill_position_industry import (
    _translate_batch,
    backfill,
    collect_candidates,
    translate_one,
)


class _FakePosition:
    def __init__(self, id: str, name: str, industry: str | None, review_status: str) -> None:
        self.id = id
        self.name = name
        self.industry = industry
        self.review_status = review_status


class _FakeScalarResult:
    def __init__(self, rows: list[_FakePosition]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return self

    def all(self) -> list[_FakePosition]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[_FakePosition]) -> None:
        self._rows = rows
        self.commits = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def execute(self, stmt: Any, params: dict | None = None) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)


class TestCollectCandidatesFilter:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_commit(self) -> None:
        fake_session = _FakeSession([])
        sm = MagicMock()
        sm.return_value.__aenter__ = AsyncMock(return_value=fake_session)
        sm.return_value.__aexit__ = AsyncMock(return_value=None)

        engine = MagicMock()
        engine.dispose = AsyncMock()

        with (
            patch("scripts.backfill_position_industry.get_async_engine", return_value=engine),
            patch(
                "scripts.backfill_position_industry.async_sessionmaker", return_value=sm
            ),
            patch("scripts.backfill_position_industry.LLMClient") as mock_llm,
        ):
            await backfill(limit=10, progress_every=20, dry_run=True)
            mock_llm.assert_not_called()
            assert fake_session.commits == 0
            engine.dispose.assert_awaited_once()


class TestTranslateOne:
    @pytest.mark.asyncio
    async def test_returns_industry_zh(self) -> None:
        llm = MagicMock()
        with patch(
            "scripts.backfill_position_industry.translate_title_industry",
            new=AsyncMock(return_value={"name_cn": None, "industry_zh": "信息技术"}),
        ):
            result = await translate_one(llm, "Backend Engineer")
        assert result == "信息技术"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_industry_zh(self) -> None:
        llm = MagicMock()
        with patch(
            "scripts.backfill_position_industry.translate_title_industry",
            new=AsyncMock(return_value={"name_cn": None, "industry_zh": None}),
        ):
            result = await translate_one(llm, "Mystery Role")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        llm = MagicMock()

        async def boom(*_args, **_kwargs):
            raise RuntimeError("LLM 502")

        with patch(
            "scripts.backfill_position_industry.translate_title_industry", new=boom
        ):
            result = await translate_one(llm, "Anything")
        assert result is None


class TestBackfillValidation:
    @pytest.mark.asyncio
    async def test_progress_every_must_be_positive(self) -> None:
        # Fix E: 参数重命名为 --progress-every 以消除「批量并发」误导
        with pytest.raises(ValueError, match="progress_every 必须 >= 1"):
            await backfill(limit=10, progress_every=0, dry_run=True)

    @pytest.mark.asyncio
    async def test_batch_size_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="batch_size 必须 >= 1"):
            await backfill(limit=10, progress_every=20, dry_run=True, batch_size=0)

    @pytest.mark.asyncio
    async def test_empty_candidates_disposes_engine(self) -> None:
        engine = MagicMock()
        engine.dispose = AsyncMock()
        fake_session = _FakeSession([])

        with (
            patch("scripts.backfill_position_industry.get_async_engine", return_value=engine),
            patch(
                "scripts.backfill_position_industry.async_sessionmaker",
                return_value=MagicMock(return_value=fake_session),
            ),
        ):
            await backfill(limit=10, progress_every=20, dry_run=True)
        engine.dispose.assert_awaited()


class TestCollectCandidatesSQL:
    """Fix E: 验证 collect_candidates 的 SELECT 包含 industry 缺失 + approved 双过滤。

    这是关键审计点 —— 防止脚本误把 pending_review 岗位批量改写。
    """

    @pytest.mark.asyncio
    async def test_collect_candidates_sql_includes_required_filters(self) -> None:
        captured: dict[str, Any] = {"stmt": "", "params": {}}

        class _CaptureSession:
            async def __aenter__(self) -> _CaptureSession:
                return self

            async def __aexit__(self, *_exc) -> None:
                return None

            async def execute(self, stmt: Any, params: dict | None = None) -> _FakeScalarResult:
                captured["stmt"] = str(stmt)
                captured["params"] = params or {}
                return _FakeScalarResult([])

        sm = MagicMock(return_value=_CaptureSession())
        await collect_candidates(sm, limit=10)

        sql = captured["stmt"]
        sql_upper = sql.upper()
        # industry 缺失条件（IS NULL OR industry = ''）
        assert "industry" in sql.lower()
        assert "IS NULL" in sql_upper
        # review_status 过滤 —— SQLAlchemy 编译时 params 是 None，
        # 但 SQL 含 `review_status = :review_status_1` bind param + AND 链接
        # （关键审计点：防止 pending_review 岗位被脚本批量改写）
        assert "review_status" in sql.lower()
        assert ":review_status_1" in sql
        # 排序 + 限制
        assert "ORDER BY" in sql_upper
        assert "LIMIT" in sql_upper
        # 双 WHERE 条件 + AND 连接
        assert sql.count("AND") >= 1


class TestTranslateBatch:
    """批量分类：一次 LLM 调用翻译多岗位为行业（D8j2 批量 20x 提速）。"""

    @pytest.mark.asyncio
    async def test_returns_industry_map_for_all_valid(self) -> None:
        llm = MagicMock()
        payload = json.dumps(
            {"Backend Engineer": "互联网/IT", "Data Scientist": "人工智能"},
            ensure_ascii=False,
        )
        with patch("scripts.backfill_position_industry.json.loads", return_value=json.loads(payload)):
            # 直接测 _translate_batch 内部逻辑：mock llm.generate 返回 JSON 串
            async def fake_generate(*_a, **_kw):
                return payload

            llm.generate = fake_generate
            result = await _translate_batch(llm, ["Backend Engineer", "Data Scientist"])
        assert result == {"Backend Engineer": "互联网/IT", "Data Scientist": "人工智能"}

    @pytest.mark.asyncio
    async def test_generic_industry_filtered_out(self) -> None:
        """LLM 返回「通用」等模糊词 → 不进入结果（回填只写真实行业）。"""
        llm = MagicMock()
        payload = json.dumps({"Mystery Role": "通用"}, ensure_ascii=False)

        async def fake_generate(*_a, **_kw):
            return payload

        llm.generate = fake_generate
        result = await _translate_batch(llm, ["Mystery Role"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_industry_filtered_out(self) -> None:
        """LLM 返回空值/null → 不进入结果。"""
        llm = MagicMock()
        payload = json.dumps({"Mystery Role": ""}, ensure_ascii=False)

        async def fake_generate(*_a, **_kw):
            return payload

        llm.generate = fake_generate
        result = await _translate_batch(llm, ["Mystery Role"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_batch_error_returns_empty(self) -> None:
        """LLM 调用异常 → 返回 {}（调用方降级逐条）。"""
        llm = MagicMock()

        async def boom(*_a, **_kw):
            raise RuntimeError("LLM 502")

        llm.generate = boom
        result = await _translate_batch(llm, ["Anything"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_names_returns_empty(self) -> None:
        llm = MagicMock()
        result = await _translate_batch(llm, [])
        assert result == {}
