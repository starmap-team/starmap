"""PLAN-012: source_trust_config 幂等播种测试。"""

from __future__ import annotations

import pytest

from app.core.trust.jd_trust import authority_score
from app.services.trust_config_service import (
    _classify_source_type,
    ensure_source_trust_config,
)


class _FakeSession:
    def __init__(self, existing_names: list[str] | None = None) -> None:
        self._known = existing_names or []
        self.added: list = []
        self.committed = 0

    async def execute(self, _stmt) -> object:
        known = self._known

        class _R:
            def all(self):
                return [(n,) for n in known]
        return _R()

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed += 1


class TestClassifySourceType:
    def test_enterprise_sources(self) -> None:
        assert _classify_source_type("sap") == "enterprise"
        assert _classify_source_type("esco") == "enterprise"

    def test_platform_sources(self) -> None:
        assert _classify_source_type("lagou") == "platform"
        assert _classify_source_type("bosszhipin") == "platform"

    def test_unknown_defaults_aggregator(self) -> None:
        assert _classify_source_type("juejin") == "aggregator"
        assert _classify_source_type("remoteok") == "aggregator"


class TestEnsureSourceTrustConfig:
    @pytest.mark.asyncio
    async def test_seeds_all_from_config(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.trust_config_service.settings", type(
            "S", (), {"authority_scores": {"lagou": 0.75, "sap": 0.90, "juejin": 0.5}})())
        session = _FakeSession(existing_names=[])
        inserted = await ensure_source_trust_config(session)
        assert inserted == 3
        assert session.committed == 1
        by_name = {a.source_name: a for a in session.added}
        assert by_name["lagou"].source_type == "platform"
        assert by_name["sap"].source_type == "enterprise"
        assert by_name["juejin"].source_type == "aggregator"
        assert by_name["lagou"].authority_score == 0.75

    @pytest.mark.asyncio
    async def test_existing_skipped_idempotent(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.trust_config_service.settings", type(
            "S", (), {"authority_scores": {"lagou": 0.75, "sap": 0.90}})())
        session = _FakeSession(existing_names=["lagou"])
        inserted = await ensure_source_trust_config(session)
        assert inserted == 1  # 仅 sap 新增
        assert session.committed == 1
        assert all(a.source_name == "sap" for a in session.added)

    @pytest.mark.asyncio
    async def test_empty_config_no_write(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.trust_config_service.settings", type(
            "S", (), {"authority_scores": {}})())
        session = _FakeSession(existing_names=[])
        assert await ensure_source_trust_config(session) == 0
        assert session.committed == 0


class TestAuthorityAlignment:
    """§7.1 对齐: 播种的 source_type 与 jd_trust.authority_score 表一致。"""

    def test_platform_scores_match_authority_table(self) -> None:
        assert authority_score("platform") == 0.7
        assert authority_score("enterprise") == 0.9
        assert authority_score("aggregator") == 0.5
