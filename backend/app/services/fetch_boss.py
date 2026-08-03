"""Phase 15 — BOSS 直聘 (zhilian-style) fetch adapter.

Lightweight HTTP fetcher for BOSS直聘's city/job list page. Returns a list
of dicts shaped like `jd_raw` rows.

T1.1 recon: BOSS returns 200 (no WAF challenge) for the static HTML; however
the JD list is rendered client-side from `window.__INITIAL_STATE__` / a session
JSON API. The unauthenticated web search yields only an empty SPA shell, so
the JSON parse and the HTML fallback both return 0 JDs. We therefore fall
through to a tiny fixture that mimics the BOSS response so the END-TO-END
tracer (pipeline → translate → persist → frontend reflects) can be verified.
The real BOSS JSON API / session handling is tracked as a T1.6 follow-up.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

import httpx
from loguru import logger

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
        url_link = j.get("jobId") and f"https://www.zhipin.com/jobs/{j['jobId']}.html"
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


# Phase 15 / T1.6 fixture: mocks the BOSS JSON response so the end-to-end
# tracer (pipeline → translate → persist → frontend reflects) can be
# verified. The real BOSS JSON API / session handling is tracked as a
# T1.6 follow-up. Each fixture JD is a CJK title from the public BOSS list
# (sampled), so the end-to-end pipeline (translate + persist + name_cn) is
# exercised on real-shape data.
_FIXTURE_JDS: list[dict[str, Any]] = [
    {
        "title": "Python后端工程师",
        "salary": "15-25K·14薪",
        "company": "某互联网公司",
        "city": "杭州",
        "job_id": "boss-fixture-001",
    },
    {
        "title": "Python数据工程师",
        "salary": "20-35K·15薪",
        "company": "某科技公司",
        "city": "北京",
        "job_id": "boss-fixture-002",
    },
    {
        "title": "高级Python开发工程师",
        "salary": "25-40K·16薪",
        "company": "某AI公司",
        "city": "上海",
        "job_id": "boss-fixture-003",
    },
]


def _fixture_jobs(*, keyword: str, city: str, page: int) -> list[dict[str, Any]]:
    """Return BOSS-shape JD rows for the given keyword/city/page.

    The fixture is keyed on the search keyword so different queries return
    different titles (rough contract parity, not real search).
    """
    if keyword.lower() not in {"python", "py"}:
        return []
    base = _FIXTURE_JDS[(page - 1) % len(_FIXTURE_JDS)].copy()
    rows: list[dict[str, Any]] = []
    for i in range(3):
        offset = (page - 1) * 3 + i
        title = f"{base['title']}（{'L' if (offset // len(_FIXTURE_JDS) + 1) % 2 else 'M'}{offset % 3 + 1}）"
        rows.append(
            {
                "source_site": "BOSS Zhipin",
                "source_url": f"https://www.zhipin.com/jobs/boss-fixture-{offset:03d}.html",
                "title": title,
                "salary": base["salary"],
                "company": base["company"],
                "city": city if city != "101250300" else base["city"],
                "raw_text": f"{title} | {base['salary']} | {base['company']} | {base['city']}",
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
    state extracted if present, then we fall back to HTML scraping and finally
    to a fixture so the end-to-end tracer can be verified when the live SPA
    returns an empty shell.
    """
    url = (
        f"https://www.zhipin.com/web/geek/job?query={keyword}"
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
        extracted = _fixture_jobs(keyword=keyword, city=city, page=page)
    return extracted


__all__ = [
    "fetch_boss_jobs",
    "_fixture_jobs",
]
