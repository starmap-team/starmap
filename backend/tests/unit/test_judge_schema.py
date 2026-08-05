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
    BatchJudgeResponse,
    JudgeRequest,
    JudgeSampleResponse,
    PairwiseRequest,
    PairwiseResponse,
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
        from app.schemas import (  # noqa: F401
            JudgeRequest as JR,
            PairwiseRequest as PR,
            BatchJudgeRequest as BJR,
            JudgeSampleResponse as JSR,
            PairwiseResponse as PWR,
            BatchJudgeResponse as BWR,
        )
        assert all((JR, PR, BJR, JSR, PWR, BWR))

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
