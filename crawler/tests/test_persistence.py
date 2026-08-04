"""入库层单元测试（需 Postgres 5433 跑着）。"""
import os
import pytest
from datetime import date

# 端口绕开
os.environ.setdefault("POSTGRES_PORT", "5433")

# NEW-22: 本文件是 live-DB 集成测试（需 5433 真 Postgres），但 crawler/tests/conftest.py
# 全局把 crawler.persistence.dao mock 成 MagicMock，二者结构性冲突——当前基建下无法运行。
# 诚实标记 skip 并留档，而非让它以 MagicMock 断言错误假装"可跑"。修复路径：将 live-DB
# 测试移出 mock conftest 作用域（或 conftest 按需 mock），跟踪见计划书附录E NEW-22。
pytestmark = pytest.mark.skip(
    reason="NEW-22: live-DB 测试与 conftest 全局 dao mock 冲突，需测试基建改造后启用"
)

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
