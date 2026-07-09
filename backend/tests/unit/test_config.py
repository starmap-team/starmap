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
    base: dict[str, object] = dict(
        secret_key="x" * 40,
        neo4j_password="real-neo4j-pw",
        postgres_password="real-pg-pw",
        redis_uri="redis://:pw@localhost:6379/0",
    )
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
