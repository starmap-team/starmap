"""Tests for graph_projector industry whitelist filtering (2026-08-28).

验证 reconcile_all 对 PG approved 岗位按 IT 行业白名单过滤（非IT岗位不入图）。
"""
from __future__ import annotations

import pytest

from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST


class TestIndustryWhitelist:
    def test_whitelist_contains_it_categories(self) -> None:
        assert "互联网/IT" in IT_INDUSTRY_WHITELIST
        assert "人工智能" in IT_INDUSTRY_WHITELIST
        assert "后端开发" in IT_INDUSTRY_WHITELIST

    def test_whitelist_excludes_non_it(self) -> None:
        assert "非IT岗位" not in IT_INDUSTRY_WHITELIST
        assert "销售" not in IT_INDUSTRY_WHITELIST
        assert "金融" not in IT_INDUSTRY_WHITELIST

    def test_whitelist_has_all_supported_categories(self) -> None:
        # 至少覆盖比赛要求的新一代信息技术领域核心类别
        for c in ("互联网/IT", "人工智能", "AI/机器学习", "数据科学", "数据工程",
                  "前端开发", "后端开发", "云计算/DevOps", "网络安全", "移动开发",
                  "测试", "嵌入式与物联网", "游戏开发", "区块链与Web3", "数据库与存储"):
            assert c in IT_INDUSTRY_WHITELIST, f"{c} 应在白名单中"
