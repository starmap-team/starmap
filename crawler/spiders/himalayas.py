"""Himalayas API spider — 实测 404，标记不可用 ( https://himalayas.app/api/v1/jobs?limit=N  (实测已失效)
-04 启动探针会自动检测并 disable 此 spider。
"""
from __future__ import annotations

from typing import Any

def run_sync(keyword: str = "python", max_count: int = 20) -> list[dict[str, Any]]:
    """Himalayas 端点 404，返回空列表。spider_registry 应将其标记为 None 跳过。"""
    return []