"""execute_dedup 回归测试（NEW-05）。

Bug：exact/fuzzy 计数器从不递增 → duplicates_found 恒 0、
_update_source_after_dedup 收到 0 → 数据源 duplicate_rate 失真（权威分失真）。
本测试锁定：去重结果必须真实传播到返回值与数据源更新。

Phase 03 Plan 03 拆分：execute_dedup 迁至 stages/dedup.py（executor.py 仅兼容重导出），
本测试改为直接 patch stages.dedup 模块。
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.pipeline import stages as pipeline_stages
from app.core.pipeline.stages import dedup as dedup_mod


class _FakeJD:
    def __init__(self, text: str):
        self.clean_text = text
        self.status = "raw"


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.committed = False

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)

    def commit(self):
        self.committed = True


def test_dedup_count_propagates(monkeypatch):
    rows = [_FakeJD("a"), _FakeJD("a"), _FakeJD("b")]

    # crawler 会话与模型（dedup 函数内 import，patch 模块属性）
    session = _FakeSession(rows)

    def _fake_get_session():
        class _Ctx:
            def __enter__(self):
                return session

            def __exit__(self, *a):
                return False

        return _Ctx()

    import crawler.persistence.database as crawler_db
    import crawler.persistence.models as crawler_models

    monkeypatch.setattr(crawler_db, "get_jd_raw_session", _fake_get_session)
    monkeypatch.setattr(crawler_models, "JdRaw", SimpleNamespace(status="status"))
    monkeypatch.setattr(crawler_models, "JdStatus", SimpleNamespace(raw="raw", duplicate="duplicate"))

    # dedup 服务：3 条中判 1 条重复
    async def _fake_dedup(records, *, text_getter, redis_client, threshold):
        unique = [records[0], records[2]]
        dups = [records[1]]
        return unique, dups

    import app.services.dedup_service as dedup_svc

    monkeypatch.setattr(dedup_svc, "dedup_jd_records", _fake_dedup)

    # 运行时依赖（patch stages.dedup 模块，而非 executor 兼容壳）
    async def _noop_progress(*args, **kwargs):
        return None

    monkeypatch.setattr(dedup_mod, "publish_stage_progress", _noop_progress)

    captured = {}

    def _fake_update(run_id, dup_count, processed):
        captured["dup_count"] = dup_count
        captured["processed"] = processed

    monkeypatch.setattr(dedup_mod, "_update_source_after_dedup", _fake_update)

    result = dedup_mod.execute_dedup("run-test")

    assert result["records_processed"] == 3
    assert result["duplicates_found"] == 1, "duplicates_found 必须反映真实去重数（NEW-05 回归）"
    assert captured == {"dup_count": 1, "processed": 3}, "数据源 duplicate_rate 依赖此计数"
    assert session.committed
    # 兼容壳仍暴露 execute_dedup（存量调用方零改动）
    assert pipeline_stages.execute_dedup is not None

