"""掘金 sitemap spider — D5 非结构化源 (PLAN-002)。

侦察 (board-recon 2026-08-05): juejin.cn 返回 200, robots.txt 允许
文章/tag 路径 (仅禁 /search /s/ /spost /editor 等), 提供 sitemap:
- 索引: https://juejin.cn/sitemap/posts/index.xml → index1..N.xml
- 子图: https://juejin.cn/sitemap/posts/indexN.xml → <url><loc>/post/{id}</loc></url>
- 文章页 SSR 渲染 (实测 97KB HTML 含 <title> 与正文)

用途: D5 第三类非结构化源 → 技术名词时序频率入 emergence。
shape 与其他 spider 一致 (jd_raw 行, source_site="juejin")。

合规: 全部走 crawler.compliance.fetch (robots 检查 + QPS≤1 + compliance_log)。
keyword 参数为兼容 executor 签名保留; sitemap 是全量文章, 不按关键词过滤
(诚实: 不假装实现了关键词筛选)。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

SITEMAP_INDEX_URL = "https://juejin.cn/sitemap/posts/index.xml"
_HTML_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_HTML_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_XML_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _clean_text(html: str) -> str:
    """去 script/style/标签后压缩空白 (与 fetch_boss._clean 同模式)。"""
    html = _HTML_SCRIPT.sub(" ", html)
    html = _HTML_STYLE.sub(" ", html)
    text = _HTML_TAG.sub(" ", html)
    return _WS.sub(" ", text).strip()


def _parse_locs(xml_body: str) -> list[str]:
    """解析 sitemap 索引/子图中的所有 <loc> URL (命名空间无关)。"""
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return []
    locs: list[str] = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "loc" and el.text:
            locs.append(el.text.strip())
    return locs


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    # 掘金 title 形如 "{文章标题} - 掘金"
    title = m.group(1).strip()
    return re.sub(r"\s*[-–—]\s*掘金\s*$", "", title).strip()


def run_sync(keyword: str = "python", max_count: int = 10) -> list[dict[str, Any]]:
    """同步爬取: sitemap 索引 → 子图 → 文章页 SSR 内容。

    注意: keyword 为兼容 executor 签名保留 (sitemap 为全量文章, 不做
    关键词过滤, 避免伪筛选)。max_count 控制文章数。
    """
    items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()

    # 1. sitemap 索引 → 子图 URL
    index_resp = fetch(SITEMAP_INDEX_URL, "juejin")
    if index_resp.status_code != 200 or not index_resp.text:
        return items
    sub_sitemaps = _parse_locs(index_resp.text)
    if not sub_sitemaps:
        return items

    # 2. 取前 1 个子图（索引按 lastmod 排序，index1 最新）
    sub_resp = fetch(sub_sitemaps[0], "juejin")
    if sub_resp.status_code != 200 or not sub_resp.text:
        return items
    post_urls = [u for u in _parse_locs(sub_resp.text) if "/post/" in u]

    # 3. 文章页 (受 compliance QPS≤1 控制)
    for url in post_urls[:max_count]:
        try:
            resp = fetch(url, "juejin")
            if resp.status_code != 200 or not resp.text:
                continue
            html = resp.text
            title = _extract_title(html)
            if not title:
                continue
            content = _clean_text(html)[:5000]
            if len(content) < 50:
                # 空壳页（反爬/登录墙）诚实跳过，不编造
                continue
            items.append({
                "source_site": "juejin",
                "job_title": title[:200],
                "company": "掘金",
                "clean_text": content,
                "source_url": url,
                "raw_html": html[:10000],
                "salary_min": 0,
                "salary_max": 0,
                "publish_date": now[:10],
                "content_hash": "",
            })
        except Exception:
            continue

    return items


__all__ = ["run_sync"]
