"""Industry 字段统一常量（PRD US-003 C2）+ 多层防御字典 (2026-08-17 Phase 1)。

约束：
- DB 写入 industry 为空时统一写「未分类」字面量，让前端 chip 文案 = DB 列值，
  消除「列是空串 vs 显示是「未分类」」的二义性。
- 所有 `industry IS NOT NULL` 过滤必须同步排除「未分类」，避免污染真实统计指标
  （dashboard total_domains / domain_distribution）。
- 列表筛选 /evolution 报告等口径务必用 `industry IS NOT NULL AND industry !=
  UNCLASSIFIED_INDUSTRY_LITERAL`（见 dashboards / evolution_report）。
- LLM 在不确定时可能返回「通用」/「综合」/「其他」等模糊行业。normalize_industry()
  将这些归一化为「未分类」字面量，避免新污染桶（Per Fix C / Architect review）。

多层防御 (Phase 1):
- 加载 backend/app/config/industry_taxonomy.yaml 字典 (30 个 canonical 行业 +
  alias 近义词映射 + 扩展 generic_tokens)。
- normalize_industry 末段调用 _alias_to_canonical 把 LLM 输出的近义词
  （"信息技术/互联网" "Tech" "SaaS" 等）归一化到 canonical 桶（"互联网/IT"），
  防止 PG / Neo4j 出现「同义不同桶」的分裂。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

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

# ───────────────────────────────────────────────────────────────────
# 多层防御 字典加载 (canonical_industries + alias 映射)
# ───────────────────────────────────────────────────────────────────

_TAXONOMY_PATH_CANDIDATES = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "app"
    / "config"
    / "industry_taxonomy.yaml",
    Path("/app/config/industry_taxonomy.yaml"),
)


def _find_taxonomy_path() -> Path | None:
    """定位 industry_taxonomy.yaml（开发 / 容器 / 测试 三种布局兜底）"""
    for p in _TAXONOMY_PATH_CANDIDATES:
        if p.exists():
            return p
    return None


# 模块级缓存（启动时一次性加载；进程内只读）。
_CANONICAL_INDUSTRIES: tuple[str, ...] = ()
_ALIAS_TO_CANONICAL: dict[str, str] = {}
_EXTRA_GENERIC_TOKENS: frozenset[str] = frozenset()
_TAXONOMY_LOADED: bool = False


def _load_industry_taxonomy() -> None:
    """从 YAML 加载 canonical / alias / extra_generic 字典到模块缓存。

    失败时记 warning，进程继续（hardcoded GENERIC_INDUSTRY_TOKENS 仍生效），
    不阻断 ETL。
    """
    global _CANONICAL_INDUSTRIES, _ALIAS_TO_CANONICAL, _EXTRA_GENERIC_TOKENS, _TAXONOMY_LOADED
    if _TAXONOMY_LOADED:
        return

    path = _find_taxonomy_path()
    if path is None:
        logger.warning("industry_taxonomy.yaml not found — alias normalization disabled")
        _TAXONOMY_LOADED = True
        return

    try:
        import yaml  # noqa: PLC0415 — 延迟加载避免冷启动成本
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:  # noqa: BLE001 — 字典失败不能阻断 ETL
        logger.warning("Failed to load industry_taxonomy.yaml: {}", exc)
        _TAXONOMY_LOADED = True
        return

    canonical_list: list[str] = []
    alias_map: dict[str, str] = {}

    for entry in data.get("canonical_industries", []):
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        canonical_list.append(name)
 # 自指映射（大小写归一化）— 与 normalize_by_alias 行为对齐
        alias_map[name.lower()] = name
        for alias in entry.get("aliases", []):
            alias_str = str(alias).strip()
            if alias_str:
                alias_map[alias_str.lower()] = name

    extra_generic: set[str] = set()
    for tok in data.get("additional_generic_tokens", []):
        tok_str = str(tok).strip()
        if tok_str:
            extra_generic.add(tok_str.lower())

    _CANONICAL_INDUSTRIES = tuple(canonical_list)
    _ALIAS_TO_CANONICAL = alias_map
    _EXTRA_GENERIC_TOKENS = frozenset(extra_generic)
    _TAXONOMY_LOADED = True
    logger.info(
        "Loaded industry_taxonomy: {} canonical + {} aliases + {} extra generic",
        len(canonical_list), len(alias_map), len(extra_generic),
    )


def _alias_to_canonical(value: str) -> str:
    """LLM 输出的近义词 → canonical 桶（大小写不敏感、忽略首尾空白）。

    不在字典中 → 原样返回（让 DB 保留具体值，方便后续 admin 手动归类）。
    """
    if not _ALIAS_TO_CANONICAL:
        return value
    return _ALIAS_TO_CANONICAL.get(value.strip().lower(), value)


# ───────────────────────────────────────────────────────────────────
# 公共 API（保持向后兼容）
# ───────────────────────────────────────────────────────────────────


def is_unclassified(value: str | None) -> bool:
    """判断 DB 字段值是否为「未分类」字面量（含空串）。"""
    if value is None:
        return True
    return value == "" or value == UNCLASSIFIED_INDUSTRY_LITERAL


def is_generic_industry(value: str | None) -> bool:
    """判断 LLM 返回的 industry 是否为「通用」/「综合」等模糊词（含字典扩展词）。"""
    if not value:
        return False
    norm = value.strip().lower()
    return norm in GENERIC_INDUSTRY_TOKENS or norm in _EXTRA_GENERIC_TOKENS


def normalize_industry(value: str | None) -> str:
    """归一化 industry 字段：None / 空串 / 通用词 → 「未分类」字面量。

    多层防御 (Phase 1):
      1. None / 空串 / 模糊词 → 「未分类」字面量
      2. alias 字典映射 → canonical 桶（防「同义不同桶」）

    extract_repo.upsert_position_record 与 loop/steps/extract 在落库前调用，
    确保 DB 列值要么是「未分类」字面量，要么是 taxonomy 中的 canonical 行业。
    """
    _load_industry_taxonomy()
    if value is None or value.strip() == "" or is_generic_industry(value):
        return UNCLASSIFIED_INDUSTRY_LITERAL
    return _alias_to_canonical(value)


def get_canonical_industries() -> tuple[str, ...]:
    """返回 taxonomy 中的 canonical 行业清单（用于 prompt 注入 + admin 下拉）。"""
    _load_industry_taxonomy()
    return _CANONICAL_INDUSTRIES


def get_alias_map() -> dict[str, str]:
    """返回 alias → canonical 的完整映射（调试 / admin 面板用）。"""
    _load_industry_taxonomy()
    return dict(_ALIAS_TO_CANONICAL)
