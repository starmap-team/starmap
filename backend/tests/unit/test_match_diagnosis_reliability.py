"""匹配诊断模块可靠性回归测试。

本文件锁定历史上确认的 5 个真实缺陷，作为回归防护网。每条用例对应一个 Bug ID，
确保修复后不再复发。新增缺陷修复时应在此补充对应回归用例。

覆盖 Bug：
  - B16: gap_level 阈值数学缺陷（精确匹配+低熟练度被误判为缺口）
  - B23: Neo4j 技能 importance 字段读取错误（加分项恒归必备）
  - BATCH-PAYLOAD: 批量匹配 payload 字段不匹配（position vs position_name）
  - BATCH-DRIVER: 批量匹配端点缺少 driver 依赖
  - B05-RELATED: 空岗位画像的容错行为
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.matching import service as matching_service
from app.services import match_service
from app.services.match_service import (
    _match_service,
    run_match,
    score_skill_match,
)

# Shorthand for the migrated _load_target_profile (now a MatchService method)
_load_target_profile = _match_service._load_target_profile


# ---------------------------------------------------------------------------
# B16: gap_level 阈值数学缺陷回归
# ---------------------------------------------------------------------------
class TestB16GapLevelThresholds:
    """锁定 score_skill_match 中 gap_level 的分级判定逻辑。"""

    def test_exact_match_high_proficiency_mastered(self):
        """精确匹配 + 同等熟练度 → 已掌握（基线）。"""
        target = [{"skill": "Python", "importance": "required", "proficiency": "熟悉"}]
        person = [{"name": "Python", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert result["evaluated"][0]["gap_level"] == "已掌握"
        assert result["evaluated"][0]["score"] >= 0.85

    def test_exact_match_lower_proficiency_still_mastered(self):
        """B16 核心：精确匹配但熟练度低于岗位要求，仍判为"已掌握"。

        旧逻辑下 final_score≈0.838<0.85 → 错判"部分掌握"。
        """
        target = [{"skill": "Python", "importance": "required", "proficiency": "精通"}]
        person = [{"name": "Python", "proficiency": "了解"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert result["evaluated"][0]["gap_level"] == "已掌握"

    def test_completely_missing_skill(self):
        """用户完全不具备的技能 → 完全缺失。"""
        target = [{"skill": "Rust", "importance": "required", "proficiency": "熟悉"}]
        person = [{"name": "Python", "proficiency": "精通"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert result["evaluated"][0]["gap_level"] == "完全缺失"
        assert result["evaluated"][0]["score"] < 0.45

    def test_full_mastery_scenario_high_score(self):
        """B16 场景：用户提供岗位全部技能，应获得高分且大部分"已掌握"。

        复现 BUG_REPORT B16 "12项只匹配6项"的场景。
        """
        target_skills = [
            {"skill": "Python", "importance": "required", "proficiency": "熟悉"},
            {"skill": "Java", "importance": "required", "proficiency": "熟悉"},
            {"skill": "Spring Boot", "importance": "required", "proficiency": "熟悉"},
            {"skill": "SQL", "importance": "required", "proficiency": "熟悉"},
            {"skill": "Redis", "importance": "required", "proficiency": "熟悉"},
            {"skill": "Docker", "importance": "required", "proficiency": "熟悉"},
            {"skill": "Kafka", "importance": "bonus", "proficiency": "了解"},
            {"skill": "Kubernetes", "importance": "bonus", "proficiency": "了解"},
        ]
        person_skills = [
            {"name": "Python", "proficiency": "精通"},
            {"name": "Java", "proficiency": "精通"},
            {"name": "Spring Boot", "proficiency": "精通"},
            {"name": "MySQL", "proficiency": "精通"},  # SQL 别名
            {"name": "Redis", "proficiency": "精通"},
            {"name": "Docker", "proficiency": "精通"},
            {"name": "Kafka", "proficiency": "熟悉"},
            {"name": "Kubernetes", "proficiency": "熟悉"},
        ]
        result = score_skill_match(target_skills=target_skills, person_skills=person_skills)
        mastered = [e for e in result["evaluated"] if e["gap_level"] == "已掌握"]
        # 至少 7/8 应判为已掌握（允许 1 个边缘情况）
        assert len(mastered) >= 7, (
            f"全掌握场景应得高分，实际仅 {len(mastered)}/8 判为已掌握: "
            f"{[(e['skill'], e['gap_level'], e['score']) for e in result['evaluated']]}"
        )


# ---------------------------------------------------------------------------
# B23: Neo4j 技能 importance 字段读取回归
# ---------------------------------------------------------------------------
class TestB23ImportanceFromFlatDict:
    """锁定 _load_target_profile 从扁平 SkillNode dict 正确读取 importance。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        _match_service._cache.clear()
        yield
        _match_service._cache.clear()

    @pytest.mark.asyncio
    async def test_bonus_skills_preserved_from_flat_dict(self):
        """B23 核心：fetch_position_graph 返回扁平 dict 时，bonus 应正确分流。

        旧逻辑从 item["properties"] 读取，importance 恒为默认"required"，
        导致 bonus 列表永远为空。
        """
        mock_graph = {
            "position": {"name": "后端工程师"},
            "skills": [
                {"name": "Python", "proficiency": "熟悉", "importance": "required"},
                {"name": "Java", "proficiency": "熟悉", "importance": "required"},
                {"name": "Kafka", "proficiency": "了解", "importance": "bonus"},
                {"name": "Kubernetes", "proficiency": "了解", "importance": "bonus"},
            ],
            "edges": [],
        }
        driver = MagicMock()
        with patch.object(matching_service, "fetch_position_graph", new=AsyncMock(return_value=mock_graph)):
            profile = await _load_target_profile(driver, "后端工程师")

        assert profile is not None
        required_names = {s["skill"] for s in profile["required"]}
        bonus_names = {s["skill"] for s in profile["bonus"]}
        assert "Python" in required_names
        assert "Java" in required_names
        # 关键断言：bonus 技能必须出现在 bonus 列表，而非被错误归入 required
        assert "Kafka" in bonus_names, "B23 回归：bonus 技能被错误归入 required"
        assert "Kubernetes" in bonus_names, "B23 回归：bonus 技能被错误归入 required"
        assert "Kafka" not in required_names

    @pytest.mark.asyncio
    async def test_backward_compat_nested_properties(self):
        """兼容历史嵌套 properties 结构仍可读取。"""
        mock_graph = {
            "position": {"name": "前端工程师"},
            "skills": [
                {"properties": {"name": "Vue.js", "proficiency": "熟悉", "importance": "required"}},
                {"properties": {"name": "Three.js", "proficiency": "了解", "importance": "bonus"}},
            ],
            "edges": [],
        }
        driver = MagicMock()
        with patch.object(matching_service, "fetch_position_graph", new=AsyncMock(return_value=mock_graph)):
            profile = await _load_target_profile(driver, "前端工程师")

        assert profile is not None
        assert any(s["skill"] == "Vue.js" for s in profile["required"])
        assert any(s["skill"] == "Three.js" for s in profile["bonus"])


# ---------------------------------------------------------------------------
# BATCH-PAYLOAD & BATCH-DRIVER: 批量匹配端点回归
# ---------------------------------------------------------------------------
class TestBatchMatchEndpoint:
    """锁定 POST /match/batch 的字段兼容性与 driver 注入。"""

    @pytest.mark.asyncio
    async def test_batch_accepts_position_field(self):
        """前端发送 {position} 字段时应被正确识别（BATCH-PAYLOAD）。"""
        import app.api.v1.match as match_api

        captured_calls: list[dict] = []

        async def fake_run_match(**kwargs):
            captured_calls.append(kwargs)
            return {
                "match_id": "test-id",
                "target_position": kwargs["target_position"],
                "match_score": 0.8,
                "matched_skills": ["Python"],
                "gap_skills": [],
                "recommendations": [],
                "missing_required": [],
                "missing_bonus": [],
                "skill_gap_detail": [],
            }

        driver = MagicMock()
        session = AsyncMock()
        body = match_api.BatchMatchRequest(items=[
            match_api.BatchMatchItem(skills=[match_api.PersonSkillInput(name="Python")], position="后端工程师"),
            match_api.BatchMatchItem(skills=[match_api.PersonSkillInput(name="Java")], position_name="Java工程师"),
        ])
        # 注意：run_match 被 from-import 到 match_api 命名空间，需 patch 模块属性
        with patch.object(match_api, "run_match", side_effect=fake_run_match):
            result = await match_api.batch_match(body, driver=driver, session=session)

        assert result["total"] == 2
        # 第一个 item 使用 position 字段
        assert captured_calls[0]["target_position"] == "后端工程师"
        assert captured_calls[0]["driver"] is driver  # driver 已注入
        # 第二个 item 使用 position_name 字段（向后兼容）
        assert captured_calls[1]["target_position"] == "Java工程师"
        # 响应统一使用 position_name 字段
        assert result["results"][0]["position_name"] == "后端工程师"

    @pytest.mark.asyncio
    async def test_batch_partial_failure_isolation(self):
        """单条失败不应影响其他条目（容错）。"""
        import app.api.v1.match as match_api

        call_count = {"n": 0}

        async def fake_run_match(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                from app.exceptions import PositionNotFoundError
                raise PositionNotFoundError(kwargs.get("target_position", "unknown"))
            return {
                "match_id": "ok",
                "target_position": kwargs["target_position"],
                "match_score": 0.5,
                "matched_skills": [],
                "gap_skills": [],
                "recommendations": [],
                "missing_required": [],
                "missing_bonus": [],
                "skill_gap_detail": [],
            }

        driver = MagicMock()
        session = AsyncMock()
        body = match_api.BatchMatchRequest(items=[
            match_api.BatchMatchItem(skills=[], position="不存在的岗位"),
            match_api.BatchMatchItem(skills=[match_api.PersonSkillInput(name="Python")], position="后端工程师"),
        ])
        with patch.object(match_api, "run_match", side_effect=fake_run_match):
            result = await match_api.batch_match(body, driver=driver, session=session)

        assert result["total"] == 2
        assert "error" in result["results"][0]
        assert "result" in result["results"][1]


# ---------------------------------------------------------------------------
# run_match 端到端集成（mock 图源）
# ---------------------------------------------------------------------------
class TestRunMatchIntegration:
    """验证 run_match 在 bonus/required 正确分流后的整体行为。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        _match_service._cache.clear()
        match_service.PREREQUISITE_MAP.clear()
        yield
        _match_service._cache.clear()

    @pytest.mark.asyncio
    async def test_bonus_skills_do_not_inflate_missing_required(self):
        """B23+B16 联合回归：bonus 技能缺失不应计入 missing_required。"""
        mock_graph = {
            "position": {"name": "后端工程师"},
            "skills": [
                {"name": "Python", "proficiency": "熟悉", "importance": "required"},
                {"name": "Kafka", "proficiency": "了解", "importance": "bonus"},
            ],
            "edges": [],
        }
        driver = MagicMock()
        with patch.object(matching_service, "fetch_position_graph", new=AsyncMock(return_value=mock_graph)), \
             patch.object(_match_service, "_save_match_result", new=AsyncMock()):
            result = await run_match(
                target_position="后端工程师",
                person_skills=[{"name": "Python", "proficiency": "精通"}],
                driver=driver,
                db_session=None,
            )

        # Python 已掌握，Kafka 是 bonus 且缺失
        assert "Python" in result["matched_skills"]
        assert "Kafka" in result["missing_bonus"]
        assert "Kafka" not in result["missing_required"], "bonus 缺失不应计入 missing_required"

    @pytest.mark.asyncio
    async def test_position_not_found_raises_404(self):
        """岗位画像不存在时应抛 PositionNotFoundError（B05 相关：明确错误而非静默）。"""
        from app.exceptions import PositionNotFoundError

        # 模拟 Neo4j 查询成功但查无此岗位:_position_exists 内 `.single()` 返回 None → 判定不存在。
        # 裸 MagicMock 会让 `.single()` 返回非 None 的假对象,误判岗位存在,故显式置 None。
        neo_session = AsyncMock()
        neo_session.run.return_value.single.return_value = None
        neo_cm = AsyncMock()
        neo_cm.__aenter__.return_value = neo_session
        driver = MagicMock()
        driver.session.return_value = neo_cm
        with patch.object(matching_service, "fetch_position_graph", new=AsyncMock(return_value={"position": None, "skills": [], "edges": []})):
            with pytest.raises(PositionNotFoundError):
                await run_match(
                    target_position="不存在的岗位",
                    person_skills=[{"name": "Python"}],
                    driver=driver,
                    db_session=None,
                )


# ---------------------------------------------------------------------------
# CHROMA-PERF: ChromaDB 不可用时的性能与负缓存回归
# ---------------------------------------------------------------------------
class TestChromaUnavailablePerformance:
    """锁定 ChromaDB collection 缺失/不可用时匹配引擎的快速失败行为。

    背景：原实现在 _score_one 中对每个候选技能单独调用 _chroma_similarity，
    单次匹配触发 O(目标×候选) 次 ChromaDB 连接尝试。当 collection 不存在时，
    每次尝试都会记录 warning + 重建 HttpClient，导致 /match/position 接口
    长时间无响应（前端表现为"点击开始诊断无反馈"）。
    修复：normalize_by_vector 引入 60s 负缓存；调用点改为每目标技能查询一次。
    """

    def test_chroma_unavailable_does_not_block_matching(self):
        """ChromaDB 不可用时，score_skill_match 应快速完成（负缓存生效）。"""
        import time

        from app.core.extraction import normalize as normalize_mod

        # 重置负缓存确保干净起点
        normalize_mod.reset_chroma_cache()

        # 8 目标技能 × 8 候选技能，全部不精确匹配以触发 chroma 回退路径
        target_skills = [
            {"skill": f"目标技能_{i}", "importance": "required", "proficiency": "熟悉"}
            for i in range(8)
        ]
        person_skills = [
            {"name": f"候选技能_{i}", "proficiency": "熟悉"}
            for i in range(8)
        ]

        start = time.monotonic()
        result = score_skill_match(target_skills=target_skills, person_skills=person_skills)
        elapsed = time.monotonic() - start

        assert len(result["evaluated"]) == 8
        # 关键断言：即使 8×8=64 次 chroma 调用，负缓存应使总耗时远低于 5s
        # （原实现因每次重建 HttpClient 可达数十秒甚至超时）。
        assert elapsed < 5.0, f"ChromaDB 不可用时匹配耗时 {elapsed:.2f}s 过长，负缓存可能失效"

        # 负缓存应已标记 ChromaDB 不可用
        assert normalize_mod._is_chroma_marked_unavailable()

        # 清理：重置以免影响后续测试
        normalize_mod.reset_chroma_cache()

    def test_chroma_negative_cache_skips_repeated_calls(self):
        """负缓存窗口内，第二次 normalize_by_vector 调用不应再尝试连接。"""
        from app.core.extraction import normalize as normalize_mod

        normalize_mod.reset_chroma_cache()

        call_count = {"n": 0}

        # 模拟 chromadb.HttpClient 抛异常，使 get_collection 失败
        class _FailingClient:
            def get_collection(self, name):
                call_count["n"] += 1
                raise RuntimeError("collection missing")

        # 第一次调用：显式传入失败的 client，触发 get_collection 异常并标记不可用
        r1 = normalize_mod.normalize_by_vector("Python", chroma_client=_FailingClient())
        assert r1 is None
        assert call_count["n"] == 1
        assert normalize_mod._is_chroma_marked_unavailable()

        # 第二次调用（chroma_client=None，命中负缓存）：不应再调用 get_collection
        r2 = normalize_mod.normalize_by_vector("Python", chroma_client=None)
        assert r2 is None
        assert call_count["n"] == 1, "负缓存窗口内不应重复连接 ChromaDB"

        normalize_mod.reset_chroma_cache()

    def test_explicit_chroma_client_bypasses_negative_cache(self):
        """显式传入 chroma_client 时跳过负缓存（供管理脚本即时验证）。"""
        from app.core.extraction import normalize as normalize_mod

        normalize_mod.reset_chroma_cache()
        # 先标记不可用
        normalize_mod._mark_chroma_unavailable("test")

        call_count = {"n": 0}

        class _FailingClient:
            def get_collection(self, name):
                call_count["n"] += 1
                raise RuntimeError("still missing")

        # 显式传入 client → 应跳过负缓存，实际尝试连接
        r = normalize_mod.normalize_by_vector("Python", chroma_client=_FailingClient())
        assert r is None
        assert call_count["n"] == 1, "显式 client 应绕过负缓存实际查询"

        normalize_mod.reset_chroma_cache()

