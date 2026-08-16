"""Coverage boost: repositories/extract_repo.py — PG 抽取持久化 (PLAN-013)。

假 session 记录 execute 的 SQL 文本与参数，验证:
- upsert_position_record: ON CONFLICT 保留原行（review_status 不覆盖）
- upsert_skill_record: 冲突时 source_count+1
- write_extraction_to_pg: 空数据跳过 / 技能去重 / 异常回滚
"""

from __future__ import annotations

from typing import Any

import pytest

from app.repositories.extract_repo import (
    upsert_position_record,
    upsert_skill_record,
    write_extraction_to_pg,
)


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.committed = 0
        self.rolled_back = 0

    async def execute(self, stmt: Any, params: dict) -> None:
        self.executed.append((str(stmt), params))

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


class TestUpsertPositionRecord:
    @pytest.mark.asyncio
    async def test_sql_preserves_review_status_on_conflict(self) -> None:
        session = _FakeSession()
        await upsert_position_record(
            session, name="后端工程师", industry="IT",
            description="desc", review_status="pending_review", created_by="u1",
        )
        sql, params = session.executed[0]
        assert "ON CONFLICT (name)" in sql
        # 冲突分支只更新 industry（COALESCE），review_status 不被覆盖
        assert "review_status" not in sql.split("DO UPDATE")[1]
        assert params["name"] == "后端工程师"
        assert params["review_status"] == "pending_review"
        assert params["industry"] == "IT"

    @pytest.mark.asyncio
    async def test_unclassified_literal_written_when_industry_empty(self) -> None:
        """PRD US-003 C2: industry 为空时写入「未分类」字面量，chip 文案 = DB 列值."""
        session = _FakeSession()
        await upsert_position_record(
            session, name="Mystery Role", industry=None,
            description="desc", review_status="pending_review", created_by="u1",
        )
        params = session.executed[0][1]
        assert params["industry"] == "未分类"

    @pytest.mark.asyncio
    async def test_unclassified_literal_written_when_industry_empty_string(self) -> None:
        """空字符串 industry 也回写「未分类」字面量."""
        session = _FakeSession()
        await upsert_position_record(
            session, name="Empty Industry", industry="",
            description="desc", review_status="pending_review", created_by="u1",
        )
        params = session.executed[0][1]
        assert params["industry"] == "未分类"

    @pytest.mark.asyncio
    async def test_generic_industry_token_normalized_to_literal(self) -> None:
        """Fix C: LLM 返回「通用」/「综合」等模糊词 → 「未分类」字面量.

        避免 US-004 prompt 收紧后 LLM 给「通用」创建新污染桶。
        """
        for token in ("通用", "综合", "其他"):
            session = _FakeSession()
            await upsert_position_record(
                session, name=f"Role-{token}", industry=token,
                description="desc", review_status="pending_review", created_by="u1",
            )
            params = session.executed[0][1]
            assert params["industry"] == "未分类", f"{token!r} should normalize"


class TestUpsertSkillRecord:
    @pytest.mark.asyncio
    async def test_sql_increments_source_count_on_conflict(self) -> None:
        session = _FakeSession()
        await upsert_skill_record(session, name="Python", category="hard_skill")
        sql, params = session.executed[0]
        update_clause = sql.split("DO UPDATE")[1]
        assert "source_count = skill_records.source_count + 1" in update_clause
        assert "last_detected_at = NOW()" in update_clause
        assert params["name"] == "Python"


class TestWriteExtractionToPg:
    @pytest.mark.asyncio
    async def test_empty_data_skipped(self) -> None:
        session = _FakeSession()
        assert await write_extraction_to_pg(session, {}) is None
        assert await write_extraction_to_pg(session, {"position_name": ""}) is None
        assert session.executed == []
        assert session.committed == 0

    @pytest.mark.asyncio
    async def test_skills_deduped_and_committed(self) -> None:
        session = _FakeSession()
        ok = await write_extraction_to_pg(session, {
            "position_name": "后端工程师",
            "industry": "IT",
            "required_skills": [{"skill": "Python"}, {"skill": "Python"}, "SQL"],
            "preferred_skills": [{"skill": "Docker"}],
        })
        assert ok is True
        skill_names = [p["name"] for _, p in session.executed if "skill_records" in str(_) or p.get("name")]
        assert set(skill_names) == {"后端工程师", "Python", "SQL", "Docker"}
        assert session.committed == 1

    @pytest.mark.asyncio
    async def test_exception_rolls_back_and_returns_none(self) -> None:
        session = _FakeSession()
        session.execute = _raise  # type: ignore[method-assign]
        assert await write_extraction_to_pg(session, {"position_name": "X"}) is None
        assert session.rolled_back == 1


async def _raise(*_: Any) -> None:
    raise RuntimeError("pg down")
