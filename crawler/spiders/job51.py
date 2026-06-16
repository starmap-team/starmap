"""前程无忧爬虫（结构稳定，PoC）。"""
from __future__ import annotations

import logging
from datetime import date
from urllib.parse import urljoin

import scrapy

from .. import config
from ..compliance import RateLimiter, fetch
from ..pipelines.clean import clean_html, extract_job_title
from ..pipelines.items import JdItem

log = logging.getLogger(__name__)

SEARCH_URL = "https://search.51job.com/list/000000,000000,0000,00,9,99,{kw},2,{pn}.html"


class Job51Spider(scrapy.Spider):
    name = "51job"
    allowed_domains = ["51job.com"]

    def __init__(self, max_per_site: int = 100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max = int(max_per_site)
        self.limiter = RateLimiter(min_interval=config.DEFAULT_SLEEP)
        self.collected = 0

    def start_requests(self):
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
        links = response.css("div.j_joblist div.e a::attr(href)").getall() or response.css("a.jname::attr(href)").getall()
        log.info("[51job][%s] 第 %d 页拿到 %d 个链接", kw, pn, len(links))

        for href in links:
            if self.collected >= self.max:
                break
            url = urljoin(response.url, href)
            yield scrapy.Request(
                url=url,
                callback=self.parse_detail,
                meta={"kw": kw},
            )

        if self.collected < self.max and pn < 5:
            yield scrapy.Request(
                url=SEARCH_URL.format(kw=kw, pn=pn + 1),
                callback=self.parse_list,
                meta={"kw": kw, "pn": pn + 1},
            )

    def parse_detail(self, response):
        result = fetch(response.url, source_site="51job", rate_limiter=self.limiter)
        if result.status_code != 200 or not result.text:
            log.warning("51job 详情失败 %s status=%d", response.url, result.status_code)
            return

        clean = clean_html(result.text)
        if not clean or len(clean) < 200:
            log.info("51job 详情正文过短 %s 跳过", response.url)
            return

        from ..dedup import simhash, hex64

        item = JdItem()
        item["source_site"] = "51job"
        item["source_url"] = response.url
        item["raw_html"] = result.text
        item["clean_text"] = clean
        item["job_title"] = extract_job_title(result.text, fallback=response.css("h1::text").get("").strip())
        item["company"] = response.css("p.cname a::text").get("").strip() or None
        item["salary_min"] = None
        item["salary_max"] = None
        item["location"] = response.css("div.tHeader div.msg::text").re_first(r"工作地点[：:]\s*(\S+)") or None
        item["publish_date"] = date.today()
        item["content_hash"] = hex64(simhash(clean))
        self.collected += 1
        yield item
