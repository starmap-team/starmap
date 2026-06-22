#!/usr/bin/env python3
"""通过 GitHub API 创建 PR"""
import urllib.request
import json
import os

# GitHub API 配置
REPO = "starmap-team/starmap"
HEAD = "feat/waf-stealth-luozf"
BASE = "main"

# PR 内容
TITLE = "feat(crawler): WAF反爬方案 + Apify集成 + ESCO技能映射"
BODY = """## 变更内容

### 1. WAF 反爬方案
- `crawler/stealth.py`: Playwright-stealth 封装，反检测浏览器指纹修补
- `crawler/compliance.py`: 代理池支持（PROXY_LIST 环境变量）
- `crawler/spiders/lagou_stealth.py`: 拉勾 Playwright-stealth 反检测版
- `crawler/spiders/job51_stealth.py`: 51job Playwright-stealth 反检测版

### 2. Apify 集成（临时方案）
- `crawler/scripts/apify_lagou.py`: 调用 Apify Actor 抓取拉勾数据
- 自带住宅代理绕 WAF，免费 1000 结果/月
- `run.py` 新增 `apify_lagou` 子命令

### 3. ESCO 技能映射
- 下载 ESCO v1.1.1 技能数据（13,896条）
- 筛选 IT/技术相关技能（505条）
- 映射 159 个 ESCO 技能到 StarMap 198 技能本体
- 覆盖 97 个 StarMap 技能（49%）

### 4. P2 修复
- 空跑返回失败：`total == 0` 时 exit 1
- 可重试错误不永久标记失败：连接错误/5xx 保持 `status=raw`
- 新增 `retryable` 计数器

## 测试结果
- 22/22 CI 测试通过
- 编译检查通过
- Apify 集成验证：144 条拉勾数据已入库

## 数据库现状
| 来源 | 记录数 |
|------|--------|
| 拉勾 (lagou) | 144 条 |
| BOSS直聘 (bosszhipin) | 100 条 |
| 51job | 100 条 |
| **总计** | **345 条** |

## 下一步
- 补充数据到 500 条（M2 硬指标）
- 接入掘金热榜（第3个数据源）
- 写质量报告

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
"""

# 创建 PR
url = f"https://api.github.com/repos/{REPO}/pulls"
data = json.dumps({
    "title": TITLE,
    "body": BODY,
    "head": HEAD,
    "base": BASE
}).encode("utf-8")

req = urllib.request.Request(url, data=data, method="POST")
req.add_header("Accept", "application/vnd.github.v3+json")
req.add_header("Content-Type", "application/json")
req.add_header("User-Agent", "Mozilla/5.0")

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"PR 创建成功!")
        print(f"URL: {result.get('html_url', 'N/A')}")
        print(f"Number: #{result.get('number', 'N/A')}")
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8")
    print(f"创建失败: {e.code}")
    print(f"错误信息: {error_body[:500]}")
    if e.code == 401:
        print("\n需要 GitHub Token 认证")
    elif e.code == 403:
        print("\n没有写权限")
    elif e.code == 422:
        print("\nPR 可能已存在")
