"""Tests for CORS allow_origins contract.

W1-T4 fix (AUTH-04 + NEW-P2): the legacy default list included Docker
internal service names (`http://starmap-frontend:5173`, `…-prod:80`,
`http://frontend:5173`). Browsers never send those as Origin headers,
so listing them added no real-world value but signaled "internal-only
isolation is sufficient" — which is a CORS smell. After this fix:

  - defaults drop all container hostnames;
  - production can override via CORS_ALLOWED_ORIGINS env (comma list);
  - tests pin the contract so a regression re-introducing internal
    hostnames fails CI.
"""
from __future__ import annotations

import pytest

from app.config import Settings


def _make_settings(**overrides) -> Settings:
    base: dict[str, object] = {
        "secret_key": "x" * 40,
        "neo4j_password": "real-neo4j-pw",
        "postgres_password": "real-pg-pw",
        "redis_uri": "redis://:pw@localhost:6379/0",
        "mimo_api_key": "configured",
    }
    base.update(overrides)
    return Settings(**base)


class TestCorsOriginsDefaults:
    def test_defaults_exclude_docker_internal_hostnames(self):
        """Container service names must NOT be in the default CORS allowlist."""
        s = _make_settings()
        for forbidden in (
            "http://frontend:5173",
            "http://starmap-frontend:5173",
            "http://starmap-frontend-prod:80",
        ):
            assert forbidden not in s.cors_origins, (
                f"Internal service name {forbidden!r} must not be in "
                f"default CORS allowlist (browsers never send these as "
                f"Origin headers; listing them is a code smell)."
            )

    def test_defaults_keep_dev_localhost_ports(self):
        """Local dev ports remain allowed for development convenience."""
        s = _make_settings()
        for expected in ("http://localhost:5173", "http://127.0.0.1:5173"):
            assert expected in s.cors_origins


class TestCorsOriginsEnvOverride:
    def test_string_env_parses_to_list(self):
        """`CORS_ALLOWED_ORIGINS=a.com,b.com` parses to ['a.com', 'b.com']."""
        s = _make_settings(cors_origins="https://starmap.example.com,https://api.example.com")
        assert s.cors_origins == [
            "https://starmap.example.com",
            "https://api.example.com",
        ]

    def test_string_env_strips_whitespace(self):
        s = _make_settings(cors_origins="  a.com , b.com  ")
        assert s.cors_origins == ["a.com", "b.com"]

    def test_string_env_empty_items_ignored(self):
        s = _make_settings(cors_origins="a.com,,b.com,")
        # 双逗号、空尾 → 留 2 项
        assert "a.com" in s.cors_origins
        assert "b.com" in s.cors_origins
        assert "" not in s.cors_origins

    def test_list_env_passes_through(self):
        """直接传 list 时不应被解析为单字符串（pydantic 行为）。"""
        s = _make_settings(cors_origins=["https://x.com"])
        assert s.cors_origins == ["https://x.com"]


# ═══════════════════════════════════════════════════════════════════════
# HTTP-level smoke: confirm CORSMiddleware rejects internal-hostname Origin.
# This is the test the audit originally implied (AUTH-04 CORS smell):
# a browser claiming `Origin: http://starmap-frontend-prod:80` should
# be refused by Starlette's CORSMiddleware since the Origin is not in
# `allow_origins`. We exercise this with a real FastAPI request.
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def isolated_settings(monkeypatch):
    """Force a clean CORS allowlist for the CORS middleware test."""
    from app.config import settings as app_settings

    monkeypatch.setattr(
        app_settings, "cors_origins",
        ["http://localhost:5173"],
    )


def test_cors_middleware_rejects_internal_hostname_origin(
    client, isolated_settings
):
    """A request with an internal-hostname Origin must not echo it back.

    Starlette's CORSMiddleware echoes Access-Control-Allow-Origin ONLY
    when the request Origin is in allow_origins. For unlisted origins
    it returns no ACAO header (or omits CORS entirely).
    """
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Origin": "http://starmap-frontend-prod:80"},
    )
    # 401 (no auth) is fine; what we care about is no CORS allow.
    acao = resp.headers.get("access-control-allow-origin")
    assert acao != "http://starmap-frontend-prod:80", (
        "CORS middleware must not allow an unlisted internal-hostname Origin"
    )


def test_cors_middleware_allows_listed_localhost(client, isolated_settings):
    """Localhost:5173 IS in the test allowlist → ACAO echoed."""
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
