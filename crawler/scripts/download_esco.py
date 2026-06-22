#!/usr/bin/env python3
"""下载并解析 ESCO 技能数据"""
import urllib.request
import csv
import io
import os

# ESCO skills CSV 下载地址
ESCO_URL = "https://raw.githubusercontent.com/tabiya-tech/tabiya-open-dataset/main/tabiya-esco-v1.1.1/csv/skills.csv"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ontology", "esco_skills.csv")


def download_esco():
    """下载 ESCO 技能数据"""
    print(f"下载 ESCO 数据: {ESCO_URL}")
    req = urllib.request.Request(ESCO_URL, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")

    # 解析 CSV
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    print(f"总技能数: {len(rows)}")
    if rows:
        print(f"列名: {list(rows[0].keys())}")
        print()
        # 显示前3条
        for i, row in enumerate(rows[:3]):
            print(f"技能 {i+1}:")
            for k, v in row.items():
                val = v[:80] if v else "(empty)"
                print(f"  {k}: {val}")
            print()

    # 保存到本地
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"已保存到: {OUTPUT_PATH}")
    return rows


if __name__ == "__main__":
    download_esco()
