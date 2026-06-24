"""集中配置管理（基于 pydantic-settings，从环境变量/.env 读取）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。所有字段对应 .env 中的环境变量。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用
    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"
    secret_key: str = "dev_secret"

    # 数据库
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "starmap123456"
    postgres_uri: str = "postgresql+asyncpg://starmap:starmap123456@localhost:5432/starmap"
    redis_uri: str = "redis://localhost:6379/0"
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # LLM
    xunfei_api_key: str = ""
    xunfei_api_secret: str = ""
    xunfei_app_id: str = ""
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    qwen_model_path: str = ""
    llm_timeout: int = 60
    llm_max_retries: int = 3

    # 小米 MiMo（实际使用的 OpenAI 兼容端点，推理模型）
    mimo_api_base: str = "https://token-plan-cn.xiaomimimo.com/v1"
    mimo_api_key: str = ""
    mimo_model: str = "mimo-v2.5"


@lru_cache
def get_settings() -> Settings:
    """单例配置（lru_cache 避免每次读取环境变量）。"""
    return Settings()


settings = get_settings()
