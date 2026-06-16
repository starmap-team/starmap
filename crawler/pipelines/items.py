"""Scrapy Item 统一格式（R1 ↔ R3 协议）。"""
import scrapy


class JdItem(scrapy.Item):
    source_site = scrapy.Field()      # 'lagou' | '51job' | 'bosszhipin'
    source_url = scrapy.Field()       # 详情页 URL
    raw_html = scrapy.Field()         # 原始 HTML
    clean_text = scrapy.Field()       # 清洗后正文
    job_title = scrapy.Field()
    company = scrapy.Field()
    salary_min = scrapy.Field()
    salary_max = scrapy.Field()
    location = scrapy.Field()
    publish_date = scrapy.Field()
    content_hash = scrapy.Field()     # 16 位 hex（SimHash），暂用简化版
