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

    # ── 阈值配置 ──
    # 抽取管线
    extraction_vector_threshold: float = 0.85
    extraction_min_sources: int = 3

    # 反幻觉守卫
    hallucination_semantic_threshold: float = 0.85
    hallucination_min_sources: int = 3
    hallucination_min_span_weeks: int = 4
    hallucination_verified_threshold: float = 0.8
    hallucination_pending_threshold: float = 0.5

    # 路径推荐
    path_min_similarity: float = 0.6
    path_min_evidence: int = 3

    # 信任度评分 (trust_integration)
    trust_w_source: float = 0.35
    trust_w_temporal: float = 0.25
    trust_w_cross: float = 0.25
    trust_w_manual: float = 0.15
    trust_decay_rate: float = 0.15
    trust_max_sources: int = 10
    trust_verified_threshold: float = 0.8
    trust_pending_threshold: float = 0.5

    # 新兴技能检测 (emergence_finder)
    emergence_z_emerging: float = 2.0
    emergence_z_rising: float = 1.5
    emergence_z_declining: float = -1.5
    emergence_min_frequency: int = 3
    emergence_min_sources: int = 3

    # 匹配引擎
    match_threshold: float = 0.6

    # 质量门禁
    quality_f1_threshold: float = 0.90
    quality_hallucination_rate_threshold: float = 0.10
    quality_high_trust_confidence: float = 0.8


@lru_cache
def get_settings() -> Settings:
    """单例配置（lru_cache 避免每次读取环境变量）。"""
    return Settings()


settings = get_settings()
