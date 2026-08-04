"""SimHash 64-bit 去重工具。"""
# 业务说明：本模块是 StarMap 爬虫系统的去重引擎，负责检测和过滤重复或近似的职位描述。
# 使用 SimHash 算法计算文本指纹，通过汉明距离判断内容相似度。
# 技术说明：SimHash 是一种局部敏感哈希，相似文本的哈希值也相似，
# 适用于海量文本的近似去重场景。
from __future__ import annotations

import hashlib
import re

# 业务说明：正则表达式用于从文本中提取有效 token。
# 匹配中文字符和英文字母，过滤掉标点符号、空白和数字，
# 这些字符对文本相似度判断贡献较低。
# 技术说明：\u4e00-\u9fa5 为中文 Unicode 范围，A-Za-z 为英文范围。
_TOKEN_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]+")


def _tokens(text: str) -> list[str]:
    # 业务说明：将输入文本转换为小写后提取 token 列表。
    # 统一转换为小写可避免因大小写差异导致的误判。
    return _TOKEN_RE.findall((text or "").lower())


def _hash64(token: str) -> int:
    """对单个 token 取 64-bit 哈希。"""
    # 业务说明：对单个 token 计算 64 位哈希值，作为 SimHash 的输入。
    # 技术说明：使用 MD5 计算哈希，取前 8 字节（64 位）作为 uint64 值。
    h = hashlib.md5(token.encode("utf-8")).digest()
    # 取前 8 字节当 uint64
    return int.from_bytes(h[:8], "big", signed=False)


def simhash(text: str) -> int:
    """计算 64-bit SimHash。"""
    # 业务说明：计算文本的 SimHash 指纹值，用于后续近似重复检测。
    # 技术说明：SimHash 算法步骤：
    #   1. 提取文本 token
    #   2. 对每个 token 计算 64 位哈希
    #   3. 初始化 64 维向量 v，每个 token 的哈希位为 1 时对应位置 +1，为 0 时 -1
    #   4. 最终 fingerprint 的每一位：若 v[i] > 0 则置 1，否则置 0
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
    # 业务说明：计算两个 SimHash 指纹之间的汉明距离，
    # 距离越小表示文本越相似。
    # 技术说明：汉明距离 = 两个二进制数异或后 1 的个数。
    return bin(a ^ b).count("1")


def is_near_duplicate(a: int, b: int, threshold: int = 10) -> bool:
    """距离 ≤ 3 视为近似重复（D6 决策默认阈值）。"""
    # 业务说明：判断两个文本是否为近似重复。
    # threshold 为汉明距离阈值，D6 决策默认值为 3。
    # 距离 ≤ 3 表示两篇职位描述高度相似，可视为重复内容过滤掉。
    # 技术说明：threshold 越小判定越严格，越大越宽松。
    return hamming(a, b) <= threshold


def hex64(value: int) -> str:
    """格式化为零填充 16 位 hex，匹配 jd_raw.content_hash CHAR(64) 留作扩展位。"""
    # 业务说明：将 SimHash 指纹格式化为 64 位十六进制字符串，
    # 存储到数据库 jd_raw.content_hash 字段（CHAR(64)）。
    # 技术说明：先取低 64 位，格式化为 16 位十六进制，不足 64 位右侧补零。
    return format(value & 0xFFFFFFFFFFFFFFFF, "016x").ljust(64, "0")


__all__ = ["simhash", "hamming", "is_near_duplicate", "hex64"]
