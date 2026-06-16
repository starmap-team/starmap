"""HTML 清洗：去 script/style/广告/HTML 标签。"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup

_JS_RE = re.compile(r"script|style|noscript|iframe", re.IGNORECASE)
_AD_KEYWORDS = (
    "广告", "推广", "扫码", "微信", "关注", "立即下载",
    "分享到", "扫一扫", "点击咨询", "HR 私聊", "hr私聊",
)


def clean_html(html: str) -> str:
    """返回纯文本（保留段落分隔）。"""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_JS_RE):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return _normalize_text(text)


def _normalize_text(text: str) -> str:
    # 合并多余空白
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    # 去除整行广告关键词
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned = [ln for ln in lines if not any(kw in ln for kw in _AD_KEYWORDS)]
    return "\n".join(cleaned).strip()


def extract_job_title(html: str, fallback: str = "") -> str:
    """尝试从 <h1> 或 og:title 抓 job_title。"""
    soup = BeautifulSoup(html or "", "lxml")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)[:200]
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"][:200]
    return fallback


__all__ = ["clean_html", "extract_job_title"]
