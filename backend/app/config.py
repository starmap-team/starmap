"""集中配置管理（基于 pydantic-settings，从环境变量/.env 读取）。"""
import logging
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 占位符：表示密码尚未在 .env 中配置，必须修改后才能用于生产环境
_UNCONFIGURED = "CHANGE_ME_IN_ENV"


class Settings(BaseSettings):
    """应用配置。所有字段对应 .env 中的环境变量。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用
    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"
    secret_key: str = _UNCONFIGURED

    # 数据库
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = _UNCONFIGURED
    # PostgreSQL 连接拆分为组件，避免在默认值中硬编码密码
    postgres_user: str = "starmap"
    postgres_password: str = _UNCONFIGURED
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "starmap"
    # 完整 URI：若通过环境变量 POSTGRES_URI 传入则优先使用，否则由组件拼接
    postgres_uri: str | None = None
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

    # ── 流水线配置 ──
    pipeline_stage_timeout: int = 1800  # 单阶段超时(秒), 默认30分钟
    pipeline_worker_concurrency: int = 2
    pipeline_crawl_concurrency: int = 5
    pipeline_retry_max: int = 3
    pipeline_retry_backoff: int = 10  # 秒, 指数递增基数

    # ------------------------------------------------------------------
    # 校验：合成 postgres_uri & 检测未配置密码
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _resolve_postgres_uri_and_warn(self) -> "Settings":
        # 若未通过 POSTGRES_URI 环境变量传入完整 URI，则由组件拼接
        if self.postgres_uri is None:
            object.__setattr__(self, "postgres_uri", (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            ))

        # 检测仍为占位值的密码字段
        sensitive_fields = {
            "secret_key": self.secret_key,
            "neo4j_password": self.neo4j_password,
            "postgres_password": self.postgres_password,
        }
        unconfigured = [
            name for name, value in sensitive_fields.items()
            if value == _UNCONFIGURED
        ]
        if unconfigured:
            msg = (
                f"⚠️  以下配置仍为默认占位值 {_UNCONFIGURED!r}，"
                f"请在 .env 中设置真实值：{', '.join(unconfigured)}"
            )
            if self.app_env == "production":
                logger.error(msg + "（生产环境必须修改！）")
            else:
                logger.warning(msg)

        return self


@lru_cache
def get_settings() -> Settings:
    """单例配置（lru_cache 避免每次读取环境变量）。"""
    return Settings()


settings = get_settings()
