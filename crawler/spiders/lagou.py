"""拉勾网爬虫（PoC：列表 + 详情，关键词过滤）。"""
from __future__ import annotations

import logging
import random
from datetime import date
from urllib.parse import urljoin

import scrapy

from .. import config
from ..compliance import RateLimiter, fetch
from ..pipelines.clean import clean_html, extract_job_title
from ..pipelines.items import JdItem

log = logging.getLogger(__name__)

# 拉勾搜索 URL（公开列表）
SEARCH_URL = "https://www.lagou.com/wn/jobs?kd={kw}&pn={pn}"


class LagouSpider(scrapy.Spider):
    """拉勾列表 + 详情双阶段抓取。

    注意：拉勾主站反爬较重，此 PoC 用直接 HTTP 方式（不走 Scrapy 调度），
    仅保留 scrapy.Spider 命名以便日后切换到 Scrapy 框架调度。
    """

    name = "lagou"
    allowed_domains = ["lagou.com"]

    def __init__(self, max_per_site: int = 100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max = int(max_per_site)
        self.limiter = RateLimiter(min_interval=config.DEFAULT_SLEEP)
        self.collected = 0

    def start_requests(self):
        # 用关键词做种子
        for kw in ("python", "java", "算法", "前端", "大模型"):
            if self.collected >= self.max:
                break
            yield scrapy.Request(
                url=SEARCH_URL.format(kw=kw, pn=1),
                callback=self.parse_list,
                meta={"kw": kw, "pn": 1},
            )

    def parse_list(self, response):
        kw = response.meta["kw"]
        pn = response.meta["pn"]
        # 拉勾列表项选择器（2026 版结构可能变化，留 TODO）
        links = response.css("a.position-link::attr(href)").getall() or response.css("div.item__10RTO a::attr(href)").getall()
        log.info("[lagou][%s] 第 %d 页拿到 %d 个链接", kw, pn, len(links))

        for href in links:
            if self.collected >= self.max:
                break
            url = urljoin(response.url, href)
            yield scrapy.Request(
                url=url,
                callback=self.parse_detail,
                meta={"kw": kw},
            )

        # 翻页（最多 5 页）
        if self.collected < self.max and pn < 5:
            yield scrapy.Request(
                url=SEARCH_URL.format(kw=kw, pn=pn + 1),
                callback=self.parse_list,
                meta={"kw": kw, "pn": pn + 1},
            )

    def parse_detail(self, response):
        # 走合规 fetch（写 compliance_log）
        result = fetch(response.url, source_site="lagou", rate_limiter=self.limiter)
        if result.status_code != 200 or not result.text:
            log.warning("拉勾详情失败 %s status=%d", response.url, result.status_code)
            return

        clean = clean_html(result.text)
        if not clean or len(clean) < 200:
            log.info("拉勾详情正文过短 %s 跳过", response.url)
            return

        from ..dedup import simhash, hex64

        item = JdItem()
        item["source_site"] = "lagou"
        item["source_url"] = response.url
        item["raw_html"] = result.text
        item["clean_text"] = clean
        item["job_title"] = extract_job_title(result.text, fallback=response.css("h1::text").get("").strip())
        item["company"] = response.css("div.company__name h2::text").get("").strip() or None
        item["salary_min"] = None
        item["salary_max"] = None
        item["location"] = response.css("div.work_addr::text").get("").strip() or None
        item["publish_date"] = date.today()
        item["content_hash"] = hex64(simhash(clean))
        self.collected += 1
        yield item
