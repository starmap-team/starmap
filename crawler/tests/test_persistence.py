"""入库层单元测试（需 Postgres 5433 跑着）。"""
import os
import pytest
from datetime import date

# 端口绕开
os.environ.setdefault("POSTGRES_PORT", "5433")

from crawler.persistence import dao  # noqa: E402
from crawler.persistence.models import JdStatus  # noqa: E402
from crawler.dedup import hex64, simhash  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_schema():
    dao.init_schema()
    yield


def test_upsert_and_count():
    text = "测试 Python 工程师 JD " + str(date.today())
    rec = {
        "source_site": "lagou",
        "source_url": "https://test.example.com/job/pytest-1",
        "clean_text": text,
        "job_title": "测试工程师",
        "company": "测试公司",
        "salary_min": 20000,
        "salary_max": 40000,
        "location": "北京",
        "publish_date": date.today(),
        "content_hash": hex64(simhash(text)),
        "status": JdStatus.raw,
    }
    r1 = dao.upsert_jd(rec)
    r2 = dao.upsert_jd(rec)  # 同 URL，第二次应 duplicate
    assert r1 in ("inserted", "duplicate")
    assert r2 == "duplicate"
