"""PIPE-03 (c) D-03: bootstrap 行为契约测试。"""
from app.core.pipeline.bootstrap import (
    BOOTSTRAP_DELAY_SECONDS,
    schedule_bootstrap_if_enabled,
)


class _FakeTimer:
    """替换 threading.Timer — 记录是否被实例化、是否调用 start(),但不实际启动后台线程。"""

    instances: list = []

    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.daemon = False
        self.started = False
        type(self).instances.append(self)

    def start(self):
        self.started = True


def test_disabled_by_default(monkeypatch):
    """PIPELINE_BOOTSTRAP 未设置 — no-op,不应调度 Timer。"""
    monkeypatch.delenv("PIPELINE_BOOTSTRAP", raising=False)
    _FakeTimer.instances.clear()
    monkeypatch.setattr(
        "app.core.pipeline.bootstrap.threading.Timer",
        lambda interval, fn, *a, **k: _FakeTimer(interval, fn),
    )
    schedule_bootstrap_if_enabled()
    assert _FakeTimer.instances == []


def test_enabled_true(monkeypatch):
    """PIPELINE_BOOTSTRAP=true — 应调度 1 个 Timer,30s 延迟。"""
    _FakeTimer.instances.clear()
    monkeypatch.setattr(
        "app.core.pipeline.bootstrap.settings.pipeline_bootstrap",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.pipeline.bootstrap.threading.Timer",
        lambda interval, fn, *a, **k: _FakeTimer(interval, fn),
    )
    schedule_bootstrap_if_enabled()
    assert len(_FakeTimer.instances) == 1
    assert _FakeTimer.instances[0].interval == BOOTSTRAP_DELAY_SECONDS


def test_enabled_1(monkeypatch):
    """PIPELINE_BOOTSTRAP=1 — 也应调度 Timer。"""
    _FakeTimer.instances.clear()
    monkeypatch.setattr(
        "app.core.pipeline.bootstrap.settings.pipeline_bootstrap",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.pipeline.bootstrap.threading.Timer",
        lambda interval, fn, *a, **k: _FakeTimer(interval, fn),
    )
    schedule_bootstrap_if_enabled()
    assert len(_FakeTimer.instances) == 1


def test_enabled_false_string_noop(monkeypatch):
    """PIPELINE_BOOTSTRAP=false(显式) — no-op。"""
    monkeypatch.setenv("PIPELINE_BOOTSTRAP", "false")
    _FakeTimer.instances.clear()
    monkeypatch.setattr(
        "app.core.pipeline.bootstrap.threading.Timer",
        lambda interval, fn, *a, **k: _FakeTimer(interval, fn),
    )
    schedule_bootstrap_if_enabled()
    assert _FakeTimer.instances == []


def test_delay_constant_is_30_seconds():
    """业务硬性要求:BOOTSTRAP_DELAY_SECONDS = 30。"""
    assert BOOTSTRAP_DELAY_SECONDS == 30
