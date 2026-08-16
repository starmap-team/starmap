"""Industry 字段统一常量（PRD US-003 C2）。

约束：
- DB 写入 industry 为空时统一写「未分类」字面量，让前端 chip 文案 = DB 列值，
  消除「列是空串 vs 显示是「未分类」」的二义性。
- 所有 `industry IS NOT NULL` 过滤必须同步排除「未分类」，避免污染真实统计指标
  （dashboard total_domains / domain_distribution）。
- 列表筛选 /evolution 报告等口径务必用 `industry IS NOT NULL AND industry !=
  UNCLASSIFIED_INDUSTRY_LITERAL`（见 dashboards / evolution_report）。
- LLM 在不确定时可能返回「通用」/「综合」/「其他」等模糊行业。normalize_industry()
  将这些归一化为「未分类」字面量，避免新污染桶（Per Fix C / Architect review）。
"""
from __future__ import annotations

UNCLASSIFIED_INDUSTRY_LITERAL = "未分类"

# LLM 在 industry 字段不确定时返回的模糊行业词 → 归一化为「未分类」
# 列表尽量收敛：与 D-04「诚实空态」语义一致
GENERIC_INDUSTRY_TOKENS = frozenset(
    {
        "通用",
        "综合",
        "其他",
        "其它",
        "general",
        "general purpose",
        "misc",
        "miscellaneous",
        "other",
        "n/a",
    }
)


def is_unclassified(value: str | None) -> bool:
    """判断 DB 字段值是否为「未分类」字面量（含空串）。"""
    if value is None:
        return True
    return value == "" or value == UNCLASSIFIED_INDUSTRY_LITERAL


def is_generic_industry(value: str | None) -> bool:
    """判断 LLM 返回的 industry 是否为「通用」/「综合」等模糊词。"""
    if not value:
        return False
    return value.strip().lower() in GENERIC_INDUSTRY_TOKENS


def normalize_industry(value: str | None) -> str:
    """归一化 industry 字段：None / 空串 / 通用词 → 「未分类」字面量。

    extract_repo.upsert_position_record 与 loop/steps/extract 在落库前调用，
    确保 DB 列值只可能是「未分类」或真实行业，不会产生「通用」假桶。
    """
    if value is None or value.strip() == "" or is_generic_industry(value):
        return UNCLASSIFIED_INDUSTRY_LITERAL
    return value
