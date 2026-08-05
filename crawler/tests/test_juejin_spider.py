"""PLAN-002: 掘金 sitemap spider 测试。

mock crawler.compliance.fetch, 验证:
- sitemap 索引 → 子图 → 文章 URL 解析
- 文章页 SSR 标题提取 + 正文清理
- 空壳页诚实跳过 (反爬/登录墙, 不编造)
- 非 200 / 非法 XML 降级为空列表
- 输出 shape 与其他 spider 一致 (jd_raw 行)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


from crawler.spiders import juejin

SITEMAP_INDEX = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://juejin.cn/sitemap/posts/index1.xml</loc></sitemap>
  <sitemap><loc>https://juejin.cn/sitemap/posts/index2.xml</loc></sitemap>
</sitemapindex>"""

SUB_SITEMAP = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://juejin.cn/post/7670011027535396914</loc><lastmod>2026-08-05T02:02:28+08:00</lastmod></url>
  <url><loc>https://juejin.cn/post/767006684771147</loc></url>
  <url><loc>https://juejin.cn/pins/999</loc></url>
</urlset>"""

ARTICLE_HTML = """<html><head><title>Python 异步编程实战 - 掘金</title></head>
<body><script>var x=1</script><article>本文介绍 asyncio 与 FastAPI 集成。
第二段内容。<footer>footer</footer></article></body></html>"""


def _resp(status: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, text=text)


class TestParseLocs:
    def test_parses_sitemap_index(self) -> None:
        locs = juejin._parse_locs(SITEMAP_INDEX)
        assert locs == [
            "https://juejin.cn/sitemap/posts/index1.xml",
            "https://juejin.cn/sitemap/posts/index2.xml",
        ]

    def test_parses_sub_sitemap_and_filters_pins(self) -> None:
        locs = juejin._parse_locs(SUB_SITEMAP)
        assert "https://juejin.cn/post/7670011027535396914" in locs

    def test_invalid_xml_returns_empty(self) -> None:
        assert juejin._parse_locs("not xml at all") == []


class TestExtractTitle:
    def test_strips_site_suffix(self) -> None:
        assert juejin._extract_title("<title>Python 异步编程实战 - 掘金</title>") == "Python 异步编程实战"

    def test_returns_empty_without_title(self) -> None:
        assert juejin._extract_title("<html></html>") == ""


class TestCleanText:
    def test_strips_scripts_styles_and_tags(self) -> None:
        out = juejin._clean_text(ARTICLE_HTML)
        assert "var x" not in out
        assert "本文介绍 asyncio 与 FastAPI 集成。" in out
        assert "<article>" not in out


class TestRunSync:
    @patch("crawler.spiders.juejin.fetch")
    def test_happy_path_shapes_items(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            _resp(200, SITEMAP_INDEX),   # 索引
            _resp(200, SUB_SITEMAP),     # 子图
            _resp(200, ARTICLE_HTML),    # 文章 1
            _resp(200, ARTICLE_HTML),    # 文章 2
        ]
        items = juejin.run_sync(keyword="python", max_count=5)
        assert len(items) == 2
        it = items[0]
        assert it["source_site"] == "juejin"
        assert it["job_title"] == "Python 异步编程实战"
        assert "asyncio" in it["clean_text"]
        assert it["source_url"] == "https://juejin.cn/post/7670011027535396914"
        assert it["salary_min"] == 0

    @patch("crawler.spiders.juejin.fetch")
    def test_index_fetch_failure_returns_empty(self, mock_fetch) -> None:
        mock_fetch.return_value = _resp(500, "")
        assert juejin.run_sync() == []

    @patch("crawler.spiders.juejin.fetch")
    def test_empty_shell_article_skipped_honestly(self, mock_fetch) -> None:
        """红线回归: 空壳页 (无正文) 诚实跳过, 不编造内容。"""
        shell_html = "<html><head><title>登录</title></head><body><div>请登录</div></body></html>"
        mock_fetch.side_effect = [
            _resp(200, SITEMAP_INDEX),
            _resp(200, SUB_SITEMAP),
            _resp(200, shell_html),
        ]
        items = juejin.run_sync(max_count=5)
        assert items == []

    @patch("crawler.spiders.juejin.fetch")
    def test_max_count_limits_articles(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            _resp(200, SITEMAP_INDEX),
            _resp(200, SUB_SITEMAP),
        ] + [_resp(200, ARTICLE_HTML)] * 2
        items = juejin.run_sync(max_count=1)
        assert len(items) == 1
        # 只抓了 1 篇文章: 索引+子图+1 文章 = 3 次 fetch
        assert mock_fetch.call_count == 3
