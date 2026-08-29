"""A3 岗位定义五要素生成 单元测试（issue #87/#99）。

覆盖：
- prompt 注册与渲染（position_definition v1）
- generate_position_definitions 成功路径（stub call_llm_with_fallback）
- LLM 失败 / 坏 JSON 的 fail-soft 行为
- top_n 截断
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


def _fake_llm_response(content: str) -> dict:
    return {"role": "assistant", "content": content, "model": "stub", "finish_reason": "stop"}


_VALID_PAYLOAD = {
    "industry_scenario": "服务智能制造与车路协同场景，负责自动驾驶系统的感知与规控链路落地。",
    "core_responsibilities": ["设计自动驾驶系统架构", "主导感知与规控联调", "建设仿真测试体系"],
    "bonus_skills": ["ROS 2", "CARLA", "CUDA"],
    "summary": "首席自主卡车工程师是负责自动驾驶重卡系统研发与量产落地的技术负责人岗位。",
}


def _candidates(n: int = 3) -> list[dict]:
    return [
        {
            "position": f"岗位{i}",
            "industry_scenario": None,
            "emerging_skills": ["System Design"],
            "emerging_ratio": 1.0 - i * 0.1,
            "definition": {
                "position_name": f"岗位{i}",
                "required_skills": ["System Design"],
                "emerging_required": ["System Design"],
            },
        }
        for i in range(n)
    ]


class TestPromptRegistered:
    def test_position_definition_prompt_registered_and_renders(self):
        from app.core.extraction.prompt import get_prompt, list_prompt_names

        assert "position_definition" in list_prompt_names()
        prompt = get_prompt(
            "position_definition",
            position_name="首席自主卡车工程师",
            required_skills='["System Design"]',
            emerging_skills='["System Design"]',
        )
        assert "首席自主卡车工程师" in prompt
        assert "$" not in prompt  # 占位符全部被替换
        assert '{"industry_scenario"' in prompt  # JSON 结构示例保留


class TestGeneratePositionDefinitions:
    @pytest.mark.asyncio
    async def test_success_fills_five_elements(self):
        from app.services.evolution_service import generate_position_definitions

        cands = _candidates(1)
        with patch(
            "app.core.extraction.llm_client.call_llm_with_fallback",
            new=__import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
                return_value=_fake_llm_response(json.dumps(_VALID_PAYLOAD, ensure_ascii=False))
            ),
        ):
            result = await generate_position_definitions(cands, top_n=5)

        assert result["generated"] == 1
        assert result["failed"] == 0
        cand = result["candidates"][0]
        assert cand["industry_scenario"] == _VALID_PAYLOAD["industry_scenario"]
        assert cand["definition"]["core_responsibilities"] == _VALID_PAYLOAD["core_responsibilities"]
        assert cand["definition"]["bonus_skills"] == _VALID_PAYLOAD["bonus_skills"]
        assert cand["definition"]["summary"] == _VALID_PAYLOAD["summary"]

    @pytest.mark.asyncio
    async def test_llm_failure_is_fail_soft(self):
        from app.services.evolution_service import generate_position_definitions

        cands = _candidates(2)
        with patch(
            "app.core.extraction.llm_client.call_llm_with_fallback",
            new=__import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
                side_effect=RuntimeError("LLM unavailable")
            ),
        ):
            result = await generate_position_definitions(cands, top_n=5)

        assert result["generated"] == 0
        assert result["failed"] == 2
        assert len(result["warnings"]) == 2
        # fail-soft：候选保留、字段不回填
        assert result["candidates"][0]["industry_scenario"] is None

    @pytest.mark.asyncio
    async def test_bad_json_counts_as_failure(self):
        from app.services.evolution_service import generate_position_definitions

        cands = _candidates(1)
        with patch(
            "app.core.extraction.llm_client.call_llm_with_fallback",
            new=__import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
                return_value=_fake_llm_response("这不是 JSON")
            ),
        ):
            result = await generate_position_definitions(cands, top_n=5)

        assert result["generated"] == 0
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_top_n_truncates_targets(self):
        from app.services.evolution_service import generate_position_definitions

        cands = _candidates(3)
        calls: list[str] = []

        async def _spy(prompt: str, **kwargs):
            calls.append(prompt)
            return _fake_llm_response(json.dumps(_VALID_PAYLOAD, ensure_ascii=False))

        with patch("app.core.extraction.llm_client.call_llm_with_fallback", new=_spy):
            result = await generate_position_definitions(cands, top_n=2)

        assert len(calls) == 2
        assert result["generated"] == 2
        # 第 3 个候选未被处理，字段保持 None
        assert result["candidates"][2]["industry_scenario"] is None
