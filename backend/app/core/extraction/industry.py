"""Industry 字段统一常量（PRD US-003 C2）。

约束：
- DB 写入 industry 为空时统一写「未分类」字面量，让前端 chip 文案 = DB 列值，
  消除「列是空串 vs 显示是「未分类」」的二义性。
- 所有 `industry IS NOT NULL` 过滤必须同步排除「未分类」，避免污染真实统计指标
  （dashboard total_domains / domain_distribution）。
- 列表筛选 /evolution 报告等口径务必用 `industry IS NOT NULL AND industry !=
  UNCLASSIFIED_INDUSTRY_LITERAL`（见 dashboards / evolution_report）。
"""
from __future__ import annotations

UNCLASSIFIED_INDUSTRY_LITERAL = "未分类"


def is_unclassified(value: str | None) -> bool:
    """判断 DB 字段值是否为「未分类」字面量。"""
    if value is None:
        return True
    return value == "" or value == UNCLASSIFIED_INDUSTRY_LITERAL
