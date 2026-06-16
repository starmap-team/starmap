"""SimHash 64-bit 去重工具。"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

# 中文标点 + 空白 + 数字 统一处理
_TOKEN_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _hash64(token: str) -> int:
    """对单个 token 取 64-bit 哈希。"""
    h = hashlib.md5(token.encode("utf-8")).digest()
    # 取前 8 字节当 uint64
    return int.from_bytes(h[:8], "big", signed=False)


def simhash(text: str) -> int:
    """计算 64-bit SimHash。"""
    tokens = _tokens(text)
    if not tokens:
        return 0
    v = [0] * 64
    for tok in tokens:
        h = _hash64(tok)
        for i in range(64):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1
    out = 0
    for i, weight in enumerate(v):
        if weight > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    """两个 64-bit 整数的 Hamming 距离。"""
    return bin(a ^ b).count("1")


def is_near_duplicate(a: int, b: int, threshold: int = 3) -> bool:
    """距离 ≤ 3 视为近似重复（D6 决策默认阈值）。"""
    return hamming(a, b) <= threshold


def hex64(value: int) -> str:
    """格式化为零填充 16 位 hex，匹配 jd_raw.content_hash CHAR(64) 留作扩展位。"""
    return format(value & 0xFFFFFFFFFFFFFFFF, "016x").ljust(64, "0")


__all__ = ["simhash", "hamming", "is_near_duplicate", "hex64"]
