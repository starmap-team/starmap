"""契约: judge 路由零内联 + 6 模型可达 (PLAN-014 批次10)。

api/v1/judge.py 6 个 BaseModel (JudgeRequest/PairwiseRequest/
BatchJudgeRequest/JudgeSampleResponse/PairwiseResponse/BatchJudgeResponse)
已迁入 schemas/judge.py.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from app.api.v1 import judge as judge_router
from app.schemas.judge import (
    BatchJudgeRequest,
    JudgeSampleResponse,
)


def _inline_models(module: Any) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    ]


class TestJudgeRouteModelCentralization:
    def test_judge_route_has_no_inline_models(self) -> None:
        assert _inline_models(judge_router) == []


class TestJudgeSchemasExported:
    def test_all_six_models_reachable(self) -> None:
        from app.schemas import (
            BatchJudgeRequest as JudgeReq,
        )
        from app.schemas import (
            BatchJudgeResponse as JudgeResp,
        )
        from app.schemas import (  # noqa: F401
            JudgeRequest as JudgeIn,
        )
        from app.schemas import (
            JudgeSampleResponse as SampleResp,
        )
        from app.schemas import (
            PairwiseRequest as PairwiseIn,
        )
        from app.schemas import (
            PairwiseResponse as PairwiseResp,
        )
        assert all((JudgeIn, PairwiseIn, JudgeReq, SampleResp, PairwiseResp, JudgeResp))

    def test_batch_judge_threshold_bounds(self) -> None:
        """threshold 0.0-1.0, 越界报错."""
        import pytest
        with pytest.raises(ValueError):
            BatchJudgeRequest(
                golden_file="g.jsonl",
                system_file="s.jsonl",
                threshold=1.5,
            )
        req = BatchJudgeRequest(golden_file="g.jsonl", system_file="s.jsonl", threshold=0.85)
        assert req.threshold == 0.85
        assert req.use_llm_judge is False

    def test_judge_sample_defaults(self) -> None:
        """默认值: f1=0, errors=[], evaluated_at 自动填."""
        from datetime import datetime
        s = JudgeSampleResponse()
        assert s.f1 == 0.0
        assert s.errors == []
        # evaluated_at 是 ISO 字符串
        datetime.fromisoformat(s.evaluated_at.replace("Z", "+00:00"))  # 不可解析即报错


class TestF1GateSingleSource:
    """NEW-11: F1 质量门禁唯一常量 — settings.eval_f1_gate，全链引用."""

    def test_settings_defines_eval_f1_gate(self) -> None:
        from app.config import settings

        assert 0.0 < settings.eval_f1_gate <= 1.0
        assert settings.eval_f1_gate == 0.90  # §14 验收口径 F1 >= 90%

    def test_batch_judge_threshold_default_references_gate(self) -> None:
        from app.config import settings

        req = BatchJudgeRequest(golden_file="g.jsonl", system_file="s.jsonl")
        assert req.threshold == settings.eval_f1_gate
