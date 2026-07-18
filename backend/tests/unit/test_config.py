"""Settings model_validator 校验逻辑测试。

覆盖：
- LLM key 启动校验 (D-04: 仅 WARNING 不阻止启动, D-08: 可观测)
- DB 密码校验 (CFG-02: secret_key/neo4j_password/postgres_password 覆盖确认)
"""
from __future__ import annotations

import pytest
from loguru import logger

from app.config import Settings


def _capture_warnings() -> tuple[list[str], int]:
    """注册一个 WARNING 级别 loguru sink，返回 (messages 列表, handler_id)。"""
    messages: list[str] = []

    def sink(message):
        messages.append(str(message))

    handler_id = logger.add(sink, level="WARNING", format="{message}")
    return messages, handler_id


def _make_settings(**overrides) -> Settings:
    """构造一个密码已配置（非占位值）的 Settings，避免 DB WARNING 噪音。"""
    base: dict[str, object] = {
        "secret_key": "x" * 40,
        "neo4j_password": "real-neo4j-pw",
        "postgres_password": "real-pg-pw",
        "redis_uri": "redis://:pw@localhost:6379/0",
    }
    base.update(overrides)
    return Settings(**base)


def test_llm_keys_all_empty_warns():
    """D-04/D-08: 所有 LLM key 为空时输出 WARNING，含 MIMO_API_KEY 和 DEEPSEEK_API_KEY。"""
    messages, handler_id = _capture_warnings()
    try:
        _make_settings(
            mimo_api_key="",
            deepseek_api_key="",
            xunfei_api_key="",
        )
    finally:
        logger.remove(handler_id)

    joined = "\n".join(messages)
    assert "MIMO_API_KEY" in joined
    assert "DEEPSEEK_API_KEY" in joined
    assert "Ollama" in joined


def test_llm_keys_partial_config_no_llm_warning():
    """配置了 mimo_api_key 时不应输出 LLM WARNING（DB 密码已配置不触发 DB WARNING）。"""
    messages, handler_id = _capture_warnings()
    try:
        _make_settings(
            mimo_api_key="some-key",
            deepseek_api_key="",
            xunfei_api_key="",
        )
    finally:
        logger.remove(handler_id)

    joined = "\n".join(messages)
    assert "LLM" not in joined
    assert "MIMO_API_KEY" not in joined


def test_db_password_placeholder_dev_warns():
    """CFG-02: 开发环境 DB 密码为占位值时输出 WARNING（含字段名）。"""
    messages, handler_id = _capture_warnings()
    try:
        Settings(
            app_env="development",
            secret_key="CHANGE_ME_IN_ENV",
            neo4j_password="CHANGE_ME_IN_ENV",
            postgres_password="CHANGE_ME_IN_ENV",
            redis_uri="redis://localhost:6379/0",
            mimo_api_key="configured",
        )
    finally:
        logger.remove(handler_id)

    joined = "\n".join(messages)
    assert "secret_key" in joined
    assert "neo4j_password" in joined
    assert "postgres_password" in joined


def test_db_password_placeholder_prod_raises():
    """CFG-02: 生产环境 DB 密码为占位值时 raise RuntimeError。"""
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            secret_key="CHANGE_ME_IN_ENV",
            neo4j_password="CHANGE_ME_IN_ENV",
            postgres_password="CHANGE_ME_IN_ENV",
            redis_uri="redis://:pw@localhost:6379/0",
            mimo_api_key="configured",
        )
    msg = str(exc.value)
    assert "secret_key" in msg
    assert "neo4j_password" in msg
    assert "postgres_password" in msg


# ═══════════════════════════════════════════════════════════════════════
# NEW-P0 (AUDIT_VERIFICATION §1.4 C2–C4) regression coverage.
# Without these assertions, a misconfigured prod deployment would
# silently fall back to defaults and every `if app_env == "production"`
# guard would be dormant. The 4 tests below pin the startup contract.
# ═══════════════════════════════════════════════════════════════════════


def test_prod_weak_secret_key_raises():
    """C3: SECRET_KEY < 32 chars in production must RuntimeError (SEC-02 fix)."""
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            app_debug=False,  # disable so the SECRET_KEY check is reached
            secret_key="too_short",
            neo4j_password="real-neo4j-pw",
            postgres_password="real-pg-pw",
            redis_uri="redis://:pw@localhost:6379/0",
            mimo_api_key="configured",
        )
    assert "SECRET_KEY" in str(exc.value)
    assert "32" in str(exc.value)


def test_prod_debug_true_raises():
    """C2: APP_DEBUG=true in production must RuntimeError (SEC-04 fix)."""
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            app_debug=True,
            secret_key="x" * 40,
            neo4j_password="real-neo4j-pw",
            postgres_password="real-pg-pw",
            redis_uri="redis://:pw@localhost:6379/0",
            mimo_api_key="configured",
        )
    assert "Debug mode" in str(exc.value)


def test_prod_redis_no_password_raises():
    """C4: REDIS_URI without `:password@` in production must RuntimeError (DATA-04 fix).

    Previously the prod compose container forced `--requirepass`, but the app
    still tried to connect with the passwordless REDIS_URI from `.env`,
    causing silent NOAUTH failures (NEW-P1b in AUDIT_VERIFICATION §1.2).
    """
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            app_debug=False,
            secret_key="x" * 40,
            neo4j_password="real-neo4j-pw",
            postgres_password="real-pg-pw",
            redis_uri="redis://redis:6379/0",  # no auth segment
            mimo_api_key="configured",
        )
    assert "Redis URI" in str(exc.value)
    assert "password" in str(exc.value)


def test_prod_bootstrap_seed_admin_blocked():
    """C5: BOOTSTRAP_SEED_ADMIN=true in production must RuntimeError (NEW-P1a).

    Even though config.py defaults BOOTSTRAP_SEED_ADMIN=False, a misconfigured
    `.env.production` re-enabling it would seed `admin:starmap2024` into a
    public deployment. Pin the contract so dev/pytest can't accidentally
    reach prod behaviour.
    """
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            app_debug=False,
            bootstrap_seed_admin=True,
            secret_key="x" * 40,
            neo4j_password="real-neo4j-pw",
            postgres_password="real-pg-pw",
            redis_uri="redis://:pw@localhost:6379/0",
            mimo_api_key="configured",
        )
    assert "BOOTSTRAP_SEED_ADMIN" in str(exc.value) or "seed" in str(exc.value).lower()


def test_prod_all_valid_passes():
    """Happy path: a properly-configured prod Settings instantiates cleanly.

    This test also serves as a smoke test for the model_validator:
    if any future assertion is added that breaks prod startup, this
    test will catch it before deploy.
    """
    s = Settings(
        app_env="production",
        app_debug=False,
        bootstrap_seed_admin=False,
        secret_key="x" * 40,
        neo4j_password="real-neo4j-pw",
        postgres_password="real-pg-pw",
        redis_uri="redis://:pw@localhost:6379/0",
        # W1-T7: SSL 必传
        neo4j_uri="bolt+s://neo4j:7687",
        postgres_sslmode="require",
        mimo_api_key="configured",
        # AUTH-04: 生产 CORS 必须覆盖默认值
        cors_origins=["https://starmap.example.com"],
    )
    assert s.app_env == "production"
    assert s.app_debug is False
    assert "@" in s.redis_uri
    assert s.postgres_uri.endswith("?ssl=require")


# ═══════════════════════════════════════════════════════════════════════
# W1-T7 regression (DATA-02/03): prod must enforce transport encryption
# for both Postgres (SSL) and Neo4j (bolt+s). Pinning the contract here
# so a future regression re-enabling plaintext doesn't slip through CI.
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("sslmode", ["disable", "prefer", "allow"])
def test_prod_postgres_plaintext_sslmode_rejected(sslmode):
    """DATA-03: prod rejects Postgres sslmode < require (allow/prefer/disable)."""
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            app_debug=False,
            secret_key="x" * 40,
            neo4j_password="real-neo4j-pw",
            postgres_password="real-pg-pw",
            redis_uri="redis://:pw@localhost:6379/0",
            neo4j_uri="bolt+s://neo4j:7687",
            postgres_sslmode=sslmode,
            mimo_api_key="configured",
            # AUTH-04: 提供 CORS 避免提前被 CORS 断言拦截
            cors_origins=["https://starmap.example.com"],
        )
    assert "POSTGRES_SSLMODE" in str(exc.value)


@pytest.mark.parametrize("sslmode", ["require", "verify-ca", "verify-full"])
def test_prod_postgres_strong_sslmode_accepted(sslmode):
    """DATA-03: prod accepts require/verify-ca/verify-full."""
    s = Settings(
        app_env="production",
        app_debug=False,
        secret_key="x" * 40,
        neo4j_password="real-neo4j-pw",
        postgres_password="real-pg-pw",
        redis_uri="redis://:pw@localhost:6379/0",
        neo4j_uri="bolt+s://neo4j:7687",
        postgres_sslmode=sslmode,
        mimo_api_key="configured",
        # AUTH-04: 生产 CORS 必须覆盖默认值
        cors_origins=["https://starmap.example.com"],
    )
    asyncpg_mode = sslmode.replace("-", "_")
    assert f"ssl={asyncpg_mode}" in s.postgres_uri


@pytest.mark.parametrize(
    "uri",
    ["bolt://neo4j:7687", "neo4j://neo4j:7687", "http://neo4j:7474"],
)
def test_prod_neo4j_plaintext_uri_rejected(uri):
    """DATA-02: prod rejects Neo4j URIs without TLS scheme."""
    with pytest.raises(RuntimeError) as exc:
        Settings(
            app_env="production",
            app_debug=False,
            secret_key="x" * 40,
            neo4j_password="real-neo4j-pw",
            postgres_password="real-pg-pw",
            redis_uri="redis://:pw@localhost:6379/0",
            neo4j_uri=uri,
            postgres_sslmode="require",
            mimo_api_key="configured",
            # AUTH-04: 提供 CORS 避免提前被 CORS 断言拦截
            cors_origins=["https://starmap.example.com"],
        )
    assert "NEO4J_URI" in str(exc.value)


@pytest.mark.parametrize(
    "uri",
    ["bolt+s://neo4j:7687", "neo4j+s://neo4j:7687", "bolt+ssc://neo4j:7687"],
)
def test_prod_neo4j_tls_uri_accepted(uri):
    """DATA-02: prod accepts any bolt+s / neo4j+s / bolt+ssc scheme."""
    s = Settings(
        app_env="production",
        app_debug=False,
        secret_key="x" * 40,
        neo4j_password="real-neo4j-pw",
        postgres_password="real-pg-pw",
        redis_uri="redis://:pw@localhost:6379/0",
        neo4j_uri=uri,
        postgres_sslmode="require",
        mimo_api_key="configured",
        # AUTH-04: 生产 CORS 必须覆盖默认值
        cors_origins=["https://starmap.example.com"],
    )
    assert s.neo4j_uri == uri
