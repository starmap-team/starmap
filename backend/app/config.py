"""集中配置管理（基于 pydantic-settings，从环境变量/.env 读取）。"""

from functools import lru_cache
from typing import Any, ClassVar

from loguru import logger
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # CORS
    # W1-T4 fix (AUTH-04 + NEW-P2): 浏览器跨域请求的 Origin 永远是人类可
    # 解析的 http(s)://host[:port] 形式；不会以 `http://starmap-frontend:5173`
    # 这种容器 hostname 形式出现。把容器内部名放进白名单等于把 CORS 当
    # "内部全开"——一旦网络隔离失守就立刻被利用。
    #
    # 生产通过环境变量 `CORS_ALLOWED_ORIGINS`（逗号分隔）覆盖默认值；
    # 默认仅含本地 dev 端口。
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5174",
        "http://localhost:5175",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins_env(cls, v: object) -> object:
        """允许通过 `CORS_ALLOWED_ORIGINS=a.com,b.com` 一次性覆盖。

        Pydantic BaseSettings 默认对 list[str] 字段不做逗号分隔解析
        （v2 Settings 行为）。这一层 validator 统一处理 env→list 的转换。
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # 认证（仅保留 token 寿命；用户表已迁移至 PostgreSQL）
    token_expire_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="JWT token 有效期（小时）",
    )
    jwt_audience: str = Field(
        default="starmap-api",
        description="JWT audience claim (aud)",
    )
    jwt_issuer: str = Field(
        default="starmap",
        description="JWT issuer claim (iss)",
    )
    jwt_leeway_seconds: int = Field(
        default=30,
        ge=0,
        description="JWT clock skew tolerance (seconds)",
    )

    # ── Bootstrap (DB seed) ──
    # Initial admin credentials seeded by scripts/bootstrap.py on first run.
    # Set BOOTSTRAP_SEED_ADMIN=true in dev/internal environments only.
    bootstrap_seed_admin: bool = Field(
        default=False,
        description="If true, ensure an admin user exists on startup (dev only)",
    )
    bootstrap_admin_username: str = Field(default="admin", min_length=1, max_length=64)
    bootstrap_admin_password: str = Field(default=_UNCONFIGURED, min_length=8, max_length=128)

    # ── Dev-mode anonymous admin bypass ──
    # W1-T2 fix (PLAN §W1-T2): dev convenience "no token = admin" must be
    # opt-in, not default. The previous behaviour — anonymous dev request
    # returning role=admin — was a real residual risk once prod guards were
    # dormant (NEW-P0). Defaulting this to False means fresh dev clones
    # behave like real users; CI / shared dev environments must explicitly
    # opt in via DEV_ANON_ADMIN=true in their .env.
    dev_anon_admin: bool = Field(
        default=False,
        description="If true (dev only), missing Bearer token returns role=admin",
    )

    # 数据来源权威度评分 (admin.py source management)
    authority_scores: dict[str, float] = {
        "lagou": 0.75,
        "zhaopin": 0.72,
        "indeed": 0.68,
        "linkedin": 0.85,
        "sap": 0.90,
        "talent": 0.70,
        "freelancer": 0.65,
        "bosszhipin": 0.73,
        "51job": 0.71,
        "liepin": 0.74,
        "test_real_crawl": 0.50,
        "boss": 0.70,
        "esco": 0.92,
    }
    authority_default_score: float = 0.60

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
    # W1-T7 fix (DATA-03): 生产强制 SSL。开发可设 POSTGRES_SSLMODE=disable
    # 跳过（asyncpg 默认会尝试 SSL）。生产应设 require / verify-full。
    postgres_sslmode: str = "prefer"
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

    # ── 资源探测超时 ──
    httpx_health_check_timeout: float = 3.0  # 健康探测（Ollama / Redis / Neo4j 等）

    # ── Pipeline match 并发（替代 pipeline/steps.py 内的 Semaphore(50)）──
    pipeline_match_concurrency: int = 50

    # ── Runtime-mutable config whitelist (SEC-06) ──
    _mutable_config_keys: ClassVar[set[str]] = {
        "pipeline_stage_timeout",
        "pipeline_worker_concurrency",
        "pipeline_crawl_concurrency",
        "pipeline_retry_max",
        "pipeline_retry_backoff",
    }

    def safe_update(self, updates: dict[str, Any], actor: str) -> dict[str, tuple[Any, Any]]:
        """Update mutable config fields with validation and audit logging.

        Args:
            updates: Dict of {field_name: new_value}. Only whitelisted fields are accepted.
            actor: Username of the user making the change (for audit log).

        Returns:
            Dict of {field_name: (old_value, new_value)} for changed fields.

        Raises:
            ValueError: If a field is not runtime-mutable or a value fails validation.
        """
        from app.utils.audit import AuditEntry, AuditEvent, audit_log

        changes: dict[str, tuple[Any, Any]] = {}
        for key, value in updates.items():
            if key not in self._mutable_config_keys:
                raise ValueError(
                    f"Field '{key}' is not runtime-mutable. Mutable fields: {sorted(self._mutable_config_keys)}"
                )
            if value is None:
                continue

            # Validate using the field's own constraints
            field_info = type(self).model_fields.get(key)
            if field_info is not None:
                try:
                    validated = type(self).model_validate({key: value, "app_env": self.app_env})
                    validated_value = getattr(validated, key)
                except Exception as e:
                    raise ValueError(f"Invalid value for '{key}': {e}") from e
            else:
                validated_value = value

            old_value = getattr(self, key)
            if old_value != validated_value:
                object.__setattr__(self, key, validated_value)
                changes[key] = (old_value, validated_value)

        if changes:
            change_summary = "; ".join(f"{k}: {v[0]} -> {v[1]}" for k, v in changes.items())
            audit_log(
                AuditEntry(
                    event=AuditEvent.SENSITIVE_WRITE,
                    actor=actor,
                    action="update_pipeline_config",
                    detail=change_summary,
                    ip="",
                )
            )

        return changes

    # ------------------------------------------------------------------
    # 校验：合成 postgres_uri & 检测未配置密码
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _resolve_postgres_uri_and_warn(self) -> "Settings":
        # 若未通过 POSTGRES_URI 环境变量传入完整 URI，则由组件拼接
        if self.postgres_uri is None:
            # W1-T7 fix (DATA-03): asyncpg 的 connect() 只接受 libpq 风格的 SSLMode
            # 字符串（disable/allow/prefer/require/verify_ca/verify_full），
            # 而不接受 libpq 旧的 `sslmode=` 或非布尔 `ssl=false/true`。
            # 直白塞 `?sslmode=...` 会让 asyncpg 抛 `unexpected keyword
            # argument 'sslmode'`（alembic 立即触发；FastAPI 的连接池懒加载
            # 偶尔能掩盖）。asyncpg 0.27+ 还会在 `ssl=` 接收到无效字符串时
            # 抛 `AttributeError: type object 'SSLMode' has no attribute ...`。
            #
            # 解决：对 prefer/allow/disable（dev 默认）直接 **省略 SSL 参数**
            # （asyncpg 默认 = 不加密，符合 localhost 开发场景）；对
            # require/verify-ca/verify-full 走 `ssl=<mode>` 把 libpq 同名
            # 字符串透传给 asyncpg 解析。verify-* 严格校验需要额外 SSLContext
            # 时再此分支注入 ctx，目前保持最小修复。
            sslmode = (self.postgres_sslmode or "prefer").lower()
            if sslmode in {"require", "verify-ca", "verify-full", "allow", "prefer", "disable"}:
                # asyncpg SSLMode 名称：用 underscore 形式（verify_ca / verify_full）
                asyncpg_ssl_mode = sslmode.replace("-", "_")
                ssl_query = f"?ssl={asyncpg_ssl_mode}"
            else:
                # 未知值：保守走 prefer（asyncpg 默认 = 不加密）
                ssl_query = "?ssl=prefer"
            object.__setattr__(
                self,
                "postgres_uri",
                (
                    f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                    f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
                    f"{ssl_query}"
                ),
            )

        # 检测仍为占位值的密码字段
        sensitive_fields = {
            "secret_key": self.secret_key,
            "neo4j_password": self.neo4j_password,
            "postgres_password": self.postgres_password,
        }
        # P0-2 fix: 若 bootstrap 开启，admin 密码也算敏感字段
        if self.bootstrap_seed_admin:
            sensitive_fields["bootstrap_admin_password"] = self.bootstrap_admin_password
        unconfigured = [name for name, value in sensitive_fields.items() if value == _UNCONFIGURED]
        if unconfigured:
            msg = f"⚠️  以下配置仍为默认占位值 {_UNCONFIGURED!r}，请在 .env 中设置真实值：{', '.join(unconfigured)}"
            if self.app_env == "production":
                # P1 修复 (SEC-02/SEC-03): 生产环境必须配置真实密钥/密码
                raise RuntimeError(msg + "（生产环境必须修改！）")
            else:
                logger.warning(msg)

        # P1 fix: production environment must have debug mode disabled
        if self.app_env == "production" and self.app_debug:
            raise RuntimeError("Debug mode (APP_DEBUG=True) must be disabled in production environment")

        # P1 修复 (DATA-04): 生产环境 Redis 必须有密码
        if self.app_env == "production" and "@" not in self.redis_uri:
            raise RuntimeError(
                "Redis URI 缺少密码认证（生产环境必须配置 REDIS_URL 含密码），格式：redis://:password@host:port/db"
            )

        # P1 修复 (SEC-02): 生产环境 SECRET_KEY 必须足够长
        if self.app_env == "production" and len(self.secret_key) < 32:
            raise RuntimeError(
                f"SECRET_KEY 长度不足（当前 {len(self.secret_key)} 字符），"
                f"生产环境至少需要 32 字符。"
                f'生成方式：python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        # P0-2 fix: 生产环境必须配置独立的 bootstrap_admin_password
        if self.app_env == "production" and self.bootstrap_admin_password == _UNCONFIGURED:
            raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD 未配置。生产环境必须在 .env.production 中设置强密码。")

        # NEW-P1a (AUDIT_VERIFICATION §1.4 C5): 生产严禁自动播种弱管理员。
        # 即便运维误把 .env.production 的 BOOTSTRAP_SEED_ADMIN 设回 true，
        # 启动期也必须 fail-fast，不允许 admin:starmap2024 进入生产库。
        if self.app_env == "production" and self.bootstrap_seed_admin:
            raise RuntimeError(
                "BOOTSTRAP_SEED_ADMIN=true 在生产环境被拒绝。"
                "生产部署严禁自动播种管理员账户；"
                "请通过 /api/v1/admin/users 显式创建。"
            )

        # W1-T2 (PLAN §W1-T2): dev 匿名 admin 旁路仅允许在 dev 且显式 opt-in。
        # 生产部署绝不允许启用——它会让匿名请求获得 admin 角色。
        if self.app_env == "production" and self.dev_anon_admin:
            raise RuntimeError("DEV_ANON_ADMIN=true 在生产环境被拒绝。生产部署必须强制 JWT 鉴权。")

        # W1-T7 fix (DATA-03): 生产 Postgres 必须强制 SSL。
        # 仅 `require`/`verify-ca`/`verify-full` 三档视为合规。
        # `disable`/`prefer`/`allow` 在生产等同裸奔——拒绝启动。
        if self.app_env == "production":
            sslmode = (self.postgres_sslmode or "").lower()
            if sslmode not in {"require", "verify-ca", "verify-full"}:
                raise RuntimeError(
                    f"POSTGRES_SSLMODE={self.postgres_sslmode!r} 在生产环境被拒绝。"
                    f"生产必须使用 require / verify-ca / verify-full 之一。"
                )

        # W1-T7 fix (DATA-02): 生产 Neo4j 必须走 bolt+s://。
        # 否则 Bolt 协议明文传输，节点凭据与查询内容均裸奔。
        if self.app_env == "production" and not self.neo4j_uri.startswith(("bolt+s://", "neo4j+s://", "bolt+ssc://")):
            raise RuntimeError(f"NEO4J_URI={self.neo4j_uri!r} 在生产环境被拒绝。生产必须使用 bolt+s:// 启用 TLS。")

        # AUTH-04 fix: 生产 CORS 白名单校验
        # 默认 cors_origins 仅含 localhost dev 端口，生产必须通过
        # CORS_ALLOWED_ORIGINS 环境变量显式覆盖为真实域名。
        if self.app_env == "production":
            _dev_only_origins = {
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5176",
                "http://127.0.0.1:5176",
                "http://localhost:5174",
                "http://localhost:5175",
            }
            if set(self.cors_origins).issubset(_dev_only_origins):
                raise RuntimeError(
                    "CORS_ALLOWED_ORIGINS 在生产环境仍为默认 dev localhost 值。"
                    "请通过 CORS_ALLOWED_ORIGINS 环境变量设置生产域名白名单。"
                )

        # Phase DB-AUTH: 密码策略由 PostgreSQL users 表的 bcrypt hash 保证
        # 这里不再做 AUTH_USERS plaintext 校验（该 env 已废弃）

        # D-04/D-08: LLM key 启动校验 — 仅 WARNING 不阻止启动
        # Ollama 本地模型始终可作降级（docker-compose 已含），无云端 key 不致命
        llm_keys = {
            "MIMO_API_KEY": self.mimo_api_key,
            "DEEPSEEK_API_KEY": self.deepseek_api_key,
            "XUNFEI_API_KEY": self.xunfei_api_key,
        }
        missing_llm = [name for name, value in llm_keys.items() if not value]
        if len(missing_llm) == len(llm_keys):
            logger.warning(
                "⚠️  以下 LLM 供应商未配置 API key：{}。"
                "将降级使用本地 Ollama（质量较低）。"
                "如需高质量抽取，请在 .env 中配置至少一个云端 LLM key。",
                ", ".join(missing_llm),
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """单例配置（lru_cache 避免每次读取环境变量）。"""
    return Settings()


settings = get_settings()
