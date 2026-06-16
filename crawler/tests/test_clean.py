"""HTML 清洗单元测试。"""
from crawler.pipelines.clean import clean_html, extract_job_title


def test_clean_html_strips_script():
    html = "<html><body><script>alert(1)</script><h1>标题</h1><p>正文</p></body></html>"
    out = clean_html(html)
    assert "alert" not in out
    assert "标题" in out
    assert "正文" in out


def test_clean_html_removes_ad_keywords():
    html = "<p>正经内容 Python</p><p>扫一扫关注公众号</p><p>岗位职责 xxx</p>"
    out = clean_html(html)
    assert "扫一扫" not in out
    assert "Python" in out


def test_extract_job_title_from_h1():
    html = "<html><body><h1>高级算法工程师</h1><p>...</p></body></html>"
    assert extract_job_title(html) == "高级算法工程师"


def test_extract_job_title_fallback():
    assert extract_job_title("<html></html>", fallback="兜底") == "兜底"
