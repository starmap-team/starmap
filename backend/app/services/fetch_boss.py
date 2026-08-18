"""BOSS 直聘 (zhilian-style) fetch adapter.

Lightweight HTTP fetcher for BOSS直聘's city/job list page. Returns a list
of dicts shaped like `jd_raw` rows.

T1.1 recon: BOSS returns 200 (no WAF challenge) for the static HTML; however
the JD list is rendered client-side from `window.__INITIAL_STATE__` / a session
JSON API. The unauthenticated web search yields only an empty SPA shell, so the
JSON parse and the HTML fallback both return 0 JDs and an empty list is
returned honestly. 真实性红线（PLAN-006a）：不再以 fixture 冒充真实 JD；
BOSS 真链路（robots-clean 路径 / session API）见计划书 D17 / PLAN-001。"""
from __future__ import annotations

import json
import random
import re
from typing import Any

import httpx
from loguru import logger

from app.config import settings
from app.core.extraction.translation import has_cjk

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
]

_HTML_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.S | re.I)
_HTML_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.S | re.I)
_HTML_TAG = re.compile(r"<[^>]+>")

_INITIAL_STATE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script",
    re.S,
)


def _clean(html: str) -> str:
    html = _HTML_SCRIPT.sub(" ", html)
    html = _HTML_STYLE.sub(" ", html)
    return _HTML_TAG.sub(" ", html)


def _extract_from_initial_state(state: dict[str, Any], *, source_site: str) -> list[dict[str, Any]]:
    job_list = (
        state.get("zpData", {}).get("jobList", [])
        or state.get("data", {}).get("jobList", [])
        or state.get("jobList", [])
        or []
    )
    rows: list[dict[str, Any]] = []
    for j in job_list:
        title = (j.get("jobName") or "").strip()
        if not title:
            continue
        salary = j.get("salaryDesc") or j.get("salary") or ""
        company = (j.get("companyName") or "").strip()
        city = (j.get("cityName") or "").strip()
        url_link = j.get("jobId") and f"{settings.zhipin_base_url}/jobs/{j['jobId']}.html"
        rows.append(
            {
                "source_site": source_site,
                "source_url": url_link or "",
                "title": title,
                "salary": salary,
                "company": company,
                "city": city,
                "raw_text": f"{title} | {salary} | {company} | {city}",
            }
        )
    return rows


def _fallback_from_html(html: str, *, source_site: str) -> list[dict[str, Any]]:
    text = _clean(html)
    titles = re.findall(r"(?:职位|岗位|job)[^A-Za-z一-鿿]{0,8}([一-鿿A-Za-z·\.·\d\+\#\- ]{3,40})", text)
    rows: list[dict[str, Any]] = []
    for t in titles[:10]:
        if not has_cjk(t):
            continue
        rows.append(
            {
                "source_site": source_site,
                "source_url": "",
                "title": t.strip(),
                "salary": "",
                "company": "",
                "city": "",
                "raw_text": t.strip(),
            }
        )
    return rows




async def fetch_boss_jobs(
    *,
    keyword: str = "Python",
    city: str = "101250300",
    page: int = 1,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Return a list of BOSS JD records shaped like `jd_raw` rows.

    BOSS city code 101250300 = 杭州. The static search URL is probed, the JSON
    state extracted if present, then we fall back to HTML scraping. When both
    yield nothing an empty list is returned honestly (真实性红线：不伪造数据).
    """
    url = (
        f"{settings.zhipin_base_url}/web/geek/job?query={keyword}"
        f"&city={city}&page={page}"
    )
    owns_client = client is not None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            headers={
                "User-Agent": random.choice(_USER_AGENTS),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning("BOSS fetch status={} url={}", resp.status_code, url)
        else:
            html = resp.text
    finally:
        if not owns_client:
            await client.aclose()

    extracted: list[dict[str, Any]] = []
    if resp.status_code == 200:
        m = _INITIAL_STATE.search(html)
        if m:
            try:
                state = json.loads(m.group(1))
                extracted = _extract_from_initial_state(state, source_site="BOSS Zhipin")
            except json.JSONDecodeError:
                extracted = []
        if not extracted:
            extracted = _fallback_from_html(html, source_site="BOSS Zhipin")
    if not extracted:
 # 真实性红线（a / ）：抓取失败诚实返回空列表，
 # 不得以 fixture 冒充真实 JD。BOSS 真链路见计划书 D17/。
        logger.info(
            "BOSS fetch returned no JDs (empty shell/blocked); returning [] honestly"
        )
    return extracted


__all__ = [
    "fetch_boss_jobs",
]
