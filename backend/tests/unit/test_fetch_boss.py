"""Coverage boost: services/fetch_boss.py — BOSS 适配器 (PLAN-013)。

覆盖 HTML 清理 / INITIAL_STATE 提取 / HTML 兜底 / 诚实空列表红线。
真实性红线回归：抓取失败必须返回 []，不得以 fixture 冒充。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.fetch_boss import (
    _clean,
    _extract_from_initial_state,
    _fallback_from_html,
    fetch_boss_jobs,
)


class TestClean:
    def test_strips_scripts_styles_and_tags(self) -> None:
        html = "<html><script>var x=1</script><style>body{}</style><div>职位名</div></html>"
        out = _clean(html)
        assert "var x" not in out
        assert "body{}" not in out
        assert "职位名" in out


class TestExtractFromInitialState:
    def test_zpdata_path(self) -> None:
        rows = _extract_from_initial_state(
            {"zpData": {"jobList": [{"jobName": " Python开发 ", "salaryDesc": "20-40K",
                                     "companyName": "ACME", "cityName": "杭州", "jobId": "abc123"}]}},
            source_site="BOSS Zhipin",
        )
        assert len(rows) == 1
        assert rows[0]["title"] == "Python开发"  # strip 后
        assert rows[0]["source_url"] == "https://www.zhipin.com/jobs/abc123.html"

    def test_alternate_data_path(self) -> None:
        rows = _extract_from_initial_state({"data": {"jobList": [{"jobName": "测试"}]}}, source_site="BOSS Zhipin")
        assert len(rows) == 1

    def test_empty_title_skipped(self) -> None:
        rows = _extract_from_initial_state(
            {"zpData": {"jobList": [{"jobName": "  "}, {"jobName": "有效"}]}},
            source_site="BOSS Zhipin",
        )
        assert len(rows) == 1
        assert rows[0]["title"] == "有效"

    def test_missing_all_paths_returns_empty(self) -> None:
        assert _extract_from_initial_state({"other": 1}, source_site="BOSS Zhipin") == []


class TestFallbackFromHtml:
    def test_extracts_cjk_titles_only(self) -> None:
        html = "<div>职位：数据分析师 职位：Developer 岗位：产品经理</div>"
        rows = _fallback_from_html(html, source_site="BOSS Zhipin")
        titles = [r["title"] for r in rows]
        assert any("数据分析师" in t for t in titles)
        assert any("产品经理" in t for t in titles)
        assert not any("Developer" in t for t in titles)  # 非 CJK 过滤

    def test_empty_html_returns_empty(self) -> None:
        assert _fallback_from_html("<html></html>", source_site="BOSS Zhipin") == []


class _FakeClient:
    def __init__(self, status: int = 200, text: str = "") -> None:
        self._status = status
        self._text = text

    async def get(self, url: str) -> SimpleNamespace:
        return SimpleNamespace(status_code=self._status, text=self._text)


class TestFetchBossJobs:
    @pytest.mark.asyncio
    async def test_success_via_initial_state(self) -> None:
        html = '<script>window.__INITIAL_STATE__={"zpData":{"jobList":[{"jobName":"后端"}]}}</script>'
        rows = await fetch_boss_jobs(client=_FakeClient(200, html))
        assert len(rows) == 1
        assert rows[0]["title"] == "后端"

    @pytest.mark.asyncio
    async def test_non_200_returns_empty_honestly(self) -> None:
        """红线回归：非 200 不得伪造数据。"""
        rows = await fetch_boss_jobs(client=_FakeClient(403, "<html>blocked</html>"))
        assert rows == []

    @pytest.mark.asyncio
    async def test_empty_shell_returns_empty_honestly(self) -> None:
        """红线回归：SPA 空壳（无 INITIAL_STATE 无标题）→ []。"""
        rows = await fetch_boss_jobs(client=_FakeClient(200, "<html><div>登录</div></html>"))
        assert rows == []

    @pytest.mark.asyncio
    async def test_invalid_json_in_state_falls_back_to_html(self) -> None:
        html = '<script>window.__INITIAL_STATE__={not json}</script><div>职位：算法工程师</div>'
        rows = await fetch_boss_jobs(client=_FakeClient(200, html))
        assert len(rows) == 1
        assert rows[0]["title"] == "算法工程师"
