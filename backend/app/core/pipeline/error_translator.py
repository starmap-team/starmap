"""Pipeline error message translator (English psycopg/SA → 简体中文).

Each error class returns a short label + detailed Chinese translation,
including remediation hint. Front-end renders these in DAG stage cards.
"""
from __future__ import annotations

import re

# Psycopg 常见错误模式 → 中文翻译
_TRANSLATIONS: list[tuple[str, str]] = [
    # column 不存在
    (r"column\s+([\"']?)(\w+)\1\s+of\s+relation\s+([\"']?)(\w+)\3\s+does\s+not\s+exist",
     "数据库表「{4}」缺少「{2}」字段。请运行 `alembic upgrade head` 补全 schema 后重试。"),
    # relation 不存在
    (r"relation\s+([\"']?)(\w+)\1\s+does\s+not\s+exist",
     "数据库表「{2}」不存在。请运行 `alembic upgrade head` 创建缺失表后重试。"),
    # 重复键冲突
    (r"duplicate\s+key\s+value?\s+violates?\s+unique\s+constraint\s+([\"']?)([\w_]+)\1",
     "违反唯一约束「{2}」。记录已存在或字段值重复。"),
    # 类型不匹配
    (r"invalid\s+input\s+syntax\s+for\s+type\s+(\w+):\s+([\"']?)([^\"']+)\2",
     "数据类型错误: 字段期望 {1} 类型, 实际收到「{3}」"),
    # 连接失败
    (r"connection\s+to\s+server.*failed",
     "数据库连接失败。请检查 PostgreSQL 服务状态"),
    # 权限不足
    (r"permission\s+denied\s+for\s+(?:table|relation)\s+([\"']?)(\w+)\1",
     "权限不足: 无法访问表「{2}」。请联系管理员授权。"),
    # 唯一约束
    (r"violates?\s+foreign\s+key\s+constraint",
     "外键约束违反: 引用的数据不存在"),
]


def translate_error(raw: str) -> str:
    """Translate raw English psycopg/SQLAlchemy error to Chinese.

    Returns the translated message, or a best-effort summary if no pattern
    matches. Always appends the original error after `→` for debugging.
    """
    if not raw:
        return "未知错误"
    raw = str(raw).strip()
    for pattern, fmt in _TRANSLATIONS:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            try:
                translated = fmt.format(*m.groups(), **{f"g{i}": g for i, g in enumerate(m.groups(), 1)})
            except (KeyError, IndexError):
                translated = fmt
            return f"{translated}\n→ 原始错误: {raw[:200]}"
    # fallback: try to find key words
    raw_lower = raw.lower()
    if "does not exist" in raw_lower:
        return f"资源不存在。请检查数据库 schema 或运行迁移。\n→ 原始错误: {raw[:200]}"
    if "permission denied" in raw_lower:
        return f"权限不足。请联系管理员。\n→ 原始错误: {raw[:200]}"
    if "timeout" in raw_lower:
        return f"操作超时。请稍后重试或检查网络。\n→ 原始错误: {raw[:200]}"
    if "connection" in raw_lower:
        return f"连接失败。\n→ 原始错误: {raw[:200]}"
    return f"操作失败: {raw[:200]}"


def translate_psycopg_error(exc: Exception) -> dict:
    """Translate a psycopg/SQLAlchemy exception to structured error.

    Returns dict with `code`, `short`, `detail` for the front-end.
    """
    raw = str(exc)
    translated = translate_error(raw)
    return {
        "code": type(exc).__name__,
        "raw": raw[:500],
        "short": translated.split("\n")[0],
        "detail": translated,
    }
