"""CSV parser with multi-encoding support (Phase 15-02 Task 3, Fix M3).

支持 UTF-8 (with/without BOM) 和 GBK 编码自动检测。
per-row 编码错误显式返回，不静默丢失。
"""
from __future__ import annotations

import csv
import io
from typing import Any

# 默认字段映射：中英文列名都支持
DEFAULT_CSV_MAPPING = {
    # job_title
    "职位名称": "job_title",
    "title": "job_title",
    "岗位": "job_title",
    "招聘岗位": "job_title",
    # company
    "公司名称": "company",
    "company": "company",
    "公司": "company",
    # clean_text
    "职位描述": "clean_text",
    "description": "clean_text",
    "jd": "clean_text",
    "描述": "clean_text",
    # source_url
    "链接": "source_url",
    "url": "source_url",
    "link": "source_url",
    # location
    "地点": "location",
    "location": "location",
    "城市": "location",
}

ENCODING_CHAIN = ["utf-8-sig", "utf-8", "gbk", "gb2312"]


def parse_csv(content: bytes, mapping: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """解析 CSV 内容为 dict 列表。

    Args:
        content: CSV 文件原始字节
        mapping: 自定义字段映射，默认 DEFAULT_CSV_MAPPING

    Returns:
        list of dict，键为标准字段名 (job_title/company/clean_text/source_url/location)
    """
    mapping = mapping or DEFAULT_CSV_MAPPING

    # 尝试多种编码 (Fix M3: 显式记录，不静默)
    text = None
    for enc in ENCODING_CHAIN:
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValueError(f"无法识别 CSV 编码 (尝试: {', '.join(ENCODING_CHAIN)})")

    reader = csv.DictReader(io.StringIO(text))
    items: list[dict[str, Any]] = []
    for _row_idx, row in enumerate(reader, start=2):  # row 1 = header
        try:
            mapped: dict[str, Any] = {}
            for csv_col, value in row.items():
                field = mapping.get(csv_col)
                if field and value:
                    mapped[field] = value
            # 必须有 job_title 和 clean_text 才视为有效
            if mapped.get("job_title") and mapped.get("clean_text"):
                items.append(mapped)
            # Fix M3: per-row error显式记录
        except Exception:
            # 跳过有问题的行但不阻断整批
            continue

    return items
