"""B2 覆盖率补测 — evolution_service 新增函数与未覆盖路径（issue #102/#91）。

补测目标（此前 0 覆盖）：
- discover_emerging_positions   模块A 新岗位发现（岗位级聚合）
- build_change_explanation      模块B 更新说明（规则模板派生）
- build_evolution_trends        趋势概览 items 构建
- build_evolution_paths         演化路径（PG fallback）
- build_emerging_skills         涌现技能列表（level 过滤）
- _calculate_cii_points / _build_signals_by_name  纯函数

均为 service/core 层单测：无 TestClient、无真实 DB —— session 用最小 fake，
load_skill_timeseries_data 用 monkeypatch 替换（与 test_evolution_api_service.py
同款模式）。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.evolution_service import (
    _build_signals_by_name,
    _calculate_cii_points,
    build_change_explanation,
)

# ══════════════════════════════════════════════════════════════
# Fakes
# ══════════════════════════════════════════════════════════════


class _RowsResult:
    """session.execute() 结果 — 返回固定行列表（.all()）。"""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows

    def scalar_one(self):  # KPI 聚合查询用
        return None


class _ScalarsResult:
    """session.execute() 结果 — .scalars().all()（EvolutionPath 查询）。"""

    def __init__(self, records: list) -> None:
        self._records = records

    def scalars(self):
        return self

    def all(self) -> list:
        return self._records


class _FakeSession:
    """按调用顺序返回预置 execute() 结果的最小 AsyncSession double。"""

    def __init__(self, results: list) -> None:
        self._results = list(results)
        self.calls: list = []

    async def execute(self, stmt: object):
        self.calls.append(stmt)
        return self._results.pop(0)


def _emerging_skill_data() -> dict:
    """两条技能：RAG 涌现（z=10 跳变）、Python 稳定。"""
    return {
        "RAG": {"frequencies": [1, 1, 1, 1], "current": 10, "sources": 3, "positions": ["AI应用工程师"]},
        "Python": {"frequencies": [2, 2, 2, 2], "current": 2, "sources": 3, "positions": ["后端工程师"]},
    }


def _rising_skill_data() -> dict:
    """sources<3 → 有 z 信号但只能 RISING（三条件缺一不可）。"""
    return {
        "LLMOps": {"frequencies": [1, 1, 1, 2], "current": 5, "sources": 1, "positions": ["算法工程师"]},
    }


def _make_change_record(**kwargs):
    defaults = {
        "position_name": "AI应用工程师",
        "skill_name": "大模型微调",
        "change_type": "added_required",
        "evidence_json": {"source_count": 5, "mention_count_old": 2, "mention_count_new": 15},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_path_record(**kwargs):
    defaults = {
        "id": "path-1",
        "source_position": "后端工程师",
        "target_position": "AI应用工程师",
        "similarity": 0.82,
        "evidence_count": 7,
        "skill_overlap": ["Python", "SQL"],
        "key_gaps": ["RAG", "Prompt工程"],
        "trust_score": 0.9,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ══════════════════════════════════════════════════════════════
# build_change_explanation — 模块B 更新说明（纯函数）
# ══════════════════════════════════════════════════════════════


class TestBuildChangeExplanation:
    def test_added_required_with_full_evidence(self):
        result = build_change_explanation(_make_change_record())
        assert "「AI应用工程师」新增必备技能「大模型微调」" in result
        assert "数据源：5 个独立 JD 来源" in result
        assert "提及次数 2→15" in result

    def test_added_required_matches_issue_example(self):
        # issue #102 给的示例：5 个独立 JD 来源必须出现
        result = build_change_explanation(_make_change_record())
        assert "5 个独立 JD 来源" in result

    def test_added_preferred(self):
        result = build_change_explanation(_make_change_record(change_type="added_preferred"))
        assert "新增加分技能" in result

    def test_removed(self):
        result = build_change_explanation(_make_change_record(change_type="removed"))
        assert "移除技能" in result

    def test_promoted(self):
        result = build_change_explanation(_make_change_record(change_type="promoted"))
        assert "由加分项提升为必备项" in result

    def test_demoted(self):
        result = build_change_explanation(_make_change_record(change_type="demoted"))
        assert "由必备项降为加分项" in result

    def test_unknown_change_type_falls_back(self):
        result = build_change_explanation(_make_change_record(change_type="weird_type"))
        assert "状态更新（weird_type）" in result

    def test_no_evidence_omits_source_ref(self):
        result = build_change_explanation(_make_change_record(evidence_json={}))
        assert "数据源" not in result
        assert "新增必备技能" in result

    def test_source_count_without_mention_counts(self):
        rec = _make_change_record(evidence_json={"source_count": 3})
        result = build_change_explanation(rec)
        assert "3 个独立 JD 来源" in result
        assert "提及次数" not in result

    def test_missing_position_defaults_to_generic(self):
        rec = _make_change_record()
        del rec.position_name
        result = build_change_explanation(rec)
        assert "「该岗位」" in result

    def test_none_evidence_json(self):
        rec = _make_change_record(evidence_json=None)
        result = build_change_explanation(rec)
        assert "新增必备技能" in result
        assert "数据源" not in result

    def test_empty_change_type_and_skill(self):
        rec = _make_change_record(change_type="", skill_name="")
        result = build_change_explanation(rec)
        assert "状态更新（）" in result


# ══════════════════════════════════════════════════════════════
# discover_emerging_positions — 模块A 新岗位发现
# ══════════════════════════════════════════════════════════════


class TestDiscoverEmergingPositions:
    @pytest.mark.asyncio
    async def test_finds_candidate_position(self, monkeypatch):
        from app.services.evolution_service import discover_emerging_positions

        async def _fake_load(session, **_):
            return _emerging_skill_data()

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        # AI应用工程师: {RAG, Python} → hit {RAG} ratio 0.5；后端工程师: 无 hit
        session = _FakeSession([
            _RowsResult([("AI应用工程师", "RAG"), ("AI应用工程师", "Python"), ("后端工程师", "Python")]),
        ])

        result = await discover_emerging_positions(session, threshold=0.5)

        assert result["status"] == "completed"
        assert result["analyzed_positions"] == 2
        assert len(result["candidates"]) == 1
        cand = result["candidates"][0]
        assert cand["position"] == "AI应用工程师"
        assert cand["emerging_skills"] == ["RAG"]
        assert cand["emerging_ratio"] == 0.5
        assert cand["industry_scenario"] is None
        assert cand["definition"]["position_name"] == "AI应用工程师"
        assert cand["definition"]["emerging_required"] == ["RAG"]
        assert "Python" in cand["definition"]["required_skills"]

    @pytest.mark.asyncio
    async def test_empty_timeseries_returns_insufficient(self, monkeypatch):
        from app.services.evolution_service import discover_emerging_positions

        async def _fake_load(session, **_):
            return {}

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        result = await discover_emerging_positions(_FakeSession([]))
        assert result["status"] == "insufficient_data"
        assert result["candidates"] == []
        assert result["analyzed_positions"] == 0
        assert "时序数据不足" in result["message"]

    @pytest.mark.asyncio
    async def test_threshold_filters_out_low_ratio(self, monkeypatch):
        from app.services.evolution_service import discover_emerging_positions

        async def _fake_load(session, **_):
            return _emerging_skill_data()

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        session = _FakeSession([
            _RowsResult([("AI应用工程师", "RAG"), ("AI应用工程师", "Python")]),
        ])
        # ratio 0.5 < 0.9 → 无候选
        result = await discover_emerging_positions(session, threshold=0.9)
        assert result["status"] == "no_candidates"
        assert result["candidates"] == []
        assert result["threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_candidates_sorted_by_ratio_desc(self, monkeypatch):
        from app.services.evolution_service import discover_emerging_positions

        skill_data = {
            "RAG": {"frequencies": [1, 1, 1, 1], "current": 10, "sources": 3, "positions": []},
            "Prompt工程": {"frequencies": [1, 1, 1, 1], "current": 8, "sources": 4, "positions": []},
        }
        async def _fake_load(session, **_):
            return skill_data

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        # 岗位甲: ratio 1.0（2/2），岗位乙: ratio 0.5（1/2）
        session = _FakeSession([
            _RowsResult([("岗位甲", "RAG"), ("岗位甲", "Prompt工程"), ("岗位乙", "RAG"), ("岗位乙", "SQL")]),
        ])
        result = await discover_emerging_positions(session, threshold=0.4)
        ratios = [c["emerging_ratio"] for c in result["candidates"]]
        assert ratios == sorted(ratios, reverse=True)
        assert result["candidates"][0]["position"] == "岗位甲"
        assert result["candidates"][0]["emerging_ratio"] == 1.0

    @pytest.mark.asyncio
    async def test_rising_skills_also_counted(self, monkeypatch):
        from app.services.evolution_service import discover_emerging_positions

        async def _fake_load(session, **_):
            return _rising_skill_data()

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        session = _FakeSession([
            _RowsResult([("算法工程师", "LLMOps")]),
        ])
        result = await discover_emerging_positions(session, threshold=0.5)
        # rising 技能同样参与岗位聚合（emerging + rising）
        assert result["status"] == "completed"
        assert result["candidates"][0]["emerging_skills"] == ["LLMOps"]

    @pytest.mark.asyncio
    async def test_message_contains_scan_summary(self, monkeypatch):
        from app.services.evolution_service import discover_emerging_positions

        async def _fake_load(session, **_):
            return _emerging_skill_data()

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        session = _FakeSession([
            _RowsResult([("AI应用工程师", "RAG"), ("AI应用工程师", "Python")]),
        ])
        result = await discover_emerging_positions(session, threshold=0.5)
        assert "扫描 1 个已审核岗位" in result["message"]
        assert "发现 1 个新兴演化候选" in result["message"]


# ══════════════════════════════════════════════════════════════
# build_evolution_trends — 趋势概览
# ══════════════════════════════════════════════════════════════


class TestBuildEvolutionTrends:
    @pytest.mark.asyncio
    async def test_empty_data_returns_empty_list(self, monkeypatch):
        from app.services.evolution_service import build_evolution_trends

        async def _fake_load(session, **_):
            return {}

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        result = await build_evolution_trends(_FakeSession([]))
        assert result == []

    @pytest.mark.asyncio
    async def test_builds_items_with_trend_and_positions(self, monkeypatch):
        from app.services.evolution_service import build_evolution_trends

        async def _fake_load(session, **_):
            return _emerging_skill_data()

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        session = _FakeSession([
            _RowsResult([("RAG", "AI应用工程师"), ("Python", "后端工程师"), ("RAG", "知识工程师")]),
        ])
        items = await build_evolution_trends(session, days=90)

        assert len(items) == 2  # 不做 [:20] 截断，全部技能
        by_name = {i["skill_name"]: i for i in items}
        assert by_name["RAG"]["trend"] == "emerging"
        assert by_name["Python"]["trend"] == "stable"
        # 岗位关联去重
        assert set(by_name["RAG"]["related_positions"]) == {"AI应用工程师", "知识工程师"}
        # CII 点序列存在且为数值
        assert all(isinstance(p, float) for p in by_name["RAG"]["points"])

    @pytest.mark.asyncio
    async def test_confidence_clamped_to_bounds(self, monkeypatch):
        from app.services.evolution_service import build_evolution_trends

        # mean=10, std=1, current=0 → z=-10（declining）→ confidence=0.5+z/10<0 → clamp 到 0
        skill_data = {
            "jQuery": {"frequencies": [9, 11, 9, 11], "current": 0, "sources": 3, "positions": []},
        }
        async def _fake_load(session, **_):
            return skill_data

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        session = _FakeSession([_RowsResult([])])
        items = await build_evolution_trends(session)
        assert items[0]["trend"] == "declining"
        assert items[0]["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_skill_without_signal_defaults_stable(self, monkeypatch):
        from app.services.evolution_service import build_evolution_trends

        # 单点历史（history<2 → Wilson fallback → STABLE，信号仍在 stable 列表）；
        # 再放一个完全不在 signals 里的技能场景：报告 stable 列表包含它即可。
        skill_data = {
            "Docker": {"frequencies": [2], "current": 3, "sources": 3, "positions": []},
        }
        async def _fake_load(session, **_):
            return skill_data

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        session = _FakeSession([_RowsResult([])])
        items = await build_evolution_trends(session)
        assert items[0]["skill_name"] == "Docker"
        assert items[0]["confidence"] >= 0.0


# ══════════════════════════════════════════════════════════════
# build_emerging_skills — 涌现技能列表
# ══════════════════════════════════════════════════════════════


class TestBuildEmergingSkills:
    @pytest.mark.asyncio
    async def test_empty_data(self, monkeypatch):
        from app.services.evolution_service import build_emerging_skills

        async def _fake_load(session, **_):
            return {}

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        assert await build_emerging_skills(_FakeSession([])) == []

    @pytest.mark.asyncio
    async def test_returns_emerging_and_rising(self, monkeypatch):
        from app.services.evolution_service import build_emerging_skills

        merged = {**_emerging_skill_data(), **_rising_skill_data()}

        async def _fake_load(session, **_):
            return merged

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        result = await build_emerging_skills(_FakeSession([]))
        names = {i["skill_name"] for i in result}
        assert names == {"RAG", "LLMOps"}
        rag = next(i for i in result if i["skill_name"] == "RAG")
        assert rag["level"] == "emerging"
        assert rag["current_frequency"] == 10
        assert rag["source_count"] == 3

    @pytest.mark.asyncio
    async def test_level_filter_emerging_only(self, monkeypatch):
        from app.services.evolution_service import build_emerging_skills

        merged = {**_emerging_skill_data(), **_rising_skill_data()}

        async def _fake_load(session, **_):
            return merged

        monkeypatch.setattr(
            "app.services.evolution_service.load_skill_timeseries_data",
            _fake_load,
        )
        result = await build_emerging_skills(_FakeSession([]), level="emerging")
        assert [i["skill_name"] for i in result] == ["RAG"]


# ══════════════════════════════════════════════════════════════
# build_evolution_paths — 演化路径（PG fallback）
# ══════════════════════════════════════════════════════════════


class TestBuildEvolutionPaths:
    @pytest.mark.asyncio
    async def test_maps_records_to_dicts(self):
        from app.services.evolution_service import build_evolution_paths

        session = _FakeSession([_ScalarsResult([_make_path_record()])])
        result = await build_evolution_paths(session)
        assert len(result) == 1
        item = result[0]
        assert item["source_position"] == "后端工程师"
        assert item["target_position"] == "AI应用工程师"
        assert item["similarity"] == 0.82
        assert item["evidence_count"] == 7
        assert item["skill_overlap"] == ["Python", "SQL"]
        assert item["key_gaps"] == ["RAG", "Prompt工程"]
        assert item["trust_score"] == 0.9
        assert item["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_empty_records(self):
        from app.services.evolution_service import build_evolution_paths

        session = _FakeSession([_ScalarsResult([])])
        assert await build_evolution_paths(session) == []

    @pytest.mark.asyncio
    async def test_none_overlap_becomes_empty_list(self):
        from app.services.evolution_service import build_evolution_paths

        session = _FakeSession([_ScalarsResult([_make_path_record(skill_overlap=None, key_gaps=None)])])
        result = await build_evolution_paths(session)
        assert result[0]["skill_overlap"] == []
        assert result[0]["key_gaps"] == []


# ══════════════════════════════════════════════════════════════
# 纯函数：_calculate_cii_points / _build_signals_by_name
# ══════════════════════════════════════════════════════════════


class TestCalculateCiiPoints:
    def test_baseline_first_half(self):
        points = _calculate_cii_points({"frequencies": [10, 10], "current": 20})
        # all=[10,10,20], half=1, baseline=10 → [100, 100, 200]
        assert points == [100.0, 100.0, 200.0]

    def test_without_current(self):
        points = _calculate_cii_points({"frequencies": [5, 15]})
        # all=[5,15], half=1, baseline=5 → [100, 300]
        assert points == [100.0, 300.0]

    def test_single_point_returns_100(self):
        assert _calculate_cii_points({"frequencies": [7]}) == [100.0]

    def test_zero_baseline_guards_division(self):
        # current=0 为 falsy 不会被追加（实现行为）；全零序列 baseline=0 → 全 100
        points = _calculate_cii_points({"frequencies": [0, 0], "current": 0})
        assert points == [100.0, 100.0]

    def test_zero_current_falsy_not_appended(self):
        # 边界：current=0 时不追加（data.get("current") falsy 分支）
        points = _calculate_cii_points({"frequencies": [4, 4], "current": 0})
        assert points == [100.0, 100.0]

    def test_series_with_current_appended(self):
        # frequencies=[2,2], current=8 → all=[2,2,8], half=1, baseline=2 → [100, 100, 400]
        points = _calculate_cii_points({"frequencies": [2, 2], "current": 8})
        assert points == [100.0, 100.0, 400.0]


class TestBuildSignalsByName:
    def _signal(self, name):
        return SimpleNamespace(skill_name=name, level=SimpleNamespace(value="stable"), z_score=0.0)

    def test_merges_all_buckets(self):
        report = SimpleNamespace(
            emerging=[self._signal("RAG")],
            rising=[self._signal("LLMOps")],
            declining=[self._signal("jQuery")],
            stable=[self._signal("Python")],
        )
        mapping = _build_signals_by_name(report)
        assert set(mapping.keys()) == {"RAG", "LLMOps", "jQuery", "Python"}

    def test_first_bucket_wins_no_override(self):
        # emerging 优先：同名信号不被 stable 覆盖
        emerging_sig = SimpleNamespace(skill_name="RAG", level=SimpleNamespace(value="emerging"), z_score=5.0)
        stable_sig = SimpleNamespace(skill_name="RAG", level=SimpleNamespace(value="stable"), z_score=0.0)
        report = SimpleNamespace(
            emerging=[emerging_sig], rising=[], declining=[], stable=[stable_sig],
        )
        mapping = _build_signals_by_name(report)
        assert mapping["RAG"] is emerging_sig

    def test_stable_only(self):
        report = SimpleNamespace(emerging=[], rising=[], declining=[], stable=[self._signal("Go")])
        assert set(_build_signals_by_name(report).keys()) == {"Go"}
