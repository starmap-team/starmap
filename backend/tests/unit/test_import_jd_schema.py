"""契约: import_jd 路由零内联 + 3 模型可达 (PLAN-014 批次8)。

backend/app/schemas/import_jd.py 3 个模型 (ImportItem/ImportRequest/
ImportResult) 已写入 schemas 包, 路由文件 api/v1/import_jd.py 已 zero
inline. 契约回归锁定两侧.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from app.api.v1 import import_jd as import_jd_router
from app.schemas.import_jd import ImportRequest, ImportResult


def _inline_models(module: Any) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    ]


class TestImportJdRouteModelCentralization:
    def test_import_jd_route_has_no_inline_models(self) -> None:
        assert _inline_models(import_jd_router) == []


class TestImportJdSchemasExported:
    def test_all_three_models_reachable(self) -> None:
        from app.schemas import (  # noqa: F401
            ImportItem as I,
        )
        from app.schemas import (
            ImportRequest as R,
        )
        from app.schemas import (
            ImportResult as T,
        )
        assert all((I, R, T))

    def test_import_request_with_items(self) -> None:
        """ImportRequest 必填 items + source_name; ImportItem 必填 job_title/clean_text."""
        req = ImportRequest(
            items=[{"job_title": "后端", "clean_text": "JD 文本"}],
            source_name="test.csv",
        )
        assert len(req.items) == 1
        assert req.items[0].job_title == "后端"
        assert req.source_name == "test.csv"

    def test_import_result_required_keys(self) -> None:
        """total/inserted/duplicate 必填; errors/pii_warnings 有默认值."""
        # 缺必填 → 报错
        import pytest
        with pytest.raises(ValueError):
            ImportResult()
        # 完整构造 + 字段 roundtrip
        res = ImportResult(total=10, inserted=5, duplicate=3, errors=[{"row": 1, "field": "x", "message": "err"}], pii_warnings=1)
        assert res.total == 10
        assert res.inserted == 5
        assert res.duplicate == 3
        assert len(res.errors) == 1
        assert res.pii_warnings == 1
