"""集中配置管理（基于 pydantic-settings，从环境变量/.env 读取）。"""

from functools import cached_property, lru_cache
from typing import Any, ClassVar

from loguru import logger
from pydantic import Field, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 占位符：表示密码尚未在 .env 中配置，必须修改后才能用于生产环境
_UNCONFIGURED = "CHANGE_ME_IN_ENV"


class Settings(BaseSettings):
    """应用配置。所有字段对应 .env 中的环境变量。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

 # 应用
    app_env: str = "development"
 # P1-AUDIT-FIX (2026-08-13): 原默认 True 反直觉——fresh clone 未配置
 # APP_DEBUG 时默认 debug 模式跑更危险；本字段唯一作用就是 config.py
 # 生产校验守卫（app_env=production 且 app_debug 时拒绝启动）。本项目
 # .env 已显式设 APP_DEBUG=true，改默认值对现有部署零影响。
    app_debug: bool = False
    app_log_level: str = "INFO"
    secret_key: str = _UNCONFIGURED

 # 限流 (): Redis 固定窗口计数（多 worker 共享），内存兜底（单进程）
    rate_limit_window: int = Field(
        default=60,
        description="速率限制窗口（秒）；每窗口每 IP 的最大请求数由 rate_limit_max 定义",
        ge=1,
    )
    rate_limit_max: int = Field(
        default=1800,
        description="每窗口每 IP 最大请求数（高频只读轮询路径已在 main.py 豁免列表排除）",
        ge=1,
    )

 # CORS
 # fix (+ NEW-P2): 浏览器跨域请求的 Origin 永远是人类可
 # 解析的 http(s)://host[:port] 形式；不会以 `http://starmap-frontend:5173`
 # 这种容器 hostname 形式出现。把容器内部名放进白名单等于把 CORS 当
 # "内部全开"——一旦网络隔离失守就立刻被利用。
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

 # ── public-deploy-preflight 2026-08-20 (P0): TrustedHostMiddleware allow list ──
 # 防止 Host header 注入。默认 ["*"] 仅在 dev 接受；生产必须 ALLOWED_HOSTS=starmap.example.com,api.example.com。
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["*"],
        description="TrustedHostMiddleware allow list; empty/wildcard OK in dev, must be explicit in prod",
    )

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _parse_allowed_hosts_env(cls, v: object) -> object:
        """ALLOWED_HOSTS=a.com,b.com 逗号分隔。"""
        if isinstance(v, str):
            return [h.strip() for h in v.split(",") if h.strip()]
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
 # : JWT rotation — `kid` header + multi-secret keyring.
 # `jwt_kid` is the active signing key id; new tokens carry this in the JOSE
 # header. `jwt_secret_keyring` maps kid -> secret and is consulted at
 # verification time so that legacy tokens remain valid during rotation.
 # Both default to {"v1": <current secret_key>} for backward compatibility.
    jwt_kid: str = Field(
        default="v1",
        min_length=1,
        max_length=32,
        description="Active JWT signing key id (JOSE `kid` header)",
    )
    jwt_secret_keyring: dict[str, str] = Field(
        default_factory=dict,
        description="Map of kid -> secret used for verification; empty means use {jwt_kid: secret_key}",
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
 # fix (PLAN §): dev convenience "no token = admin" must be
 # opt-in, not default. The previous behaviour — anonymous dev request
 # returning role=admin — was a real residual risk once prod guards were
 # dormant (NEW-P0). Defaulting this to False means fresh dev clones
 # behave like real users; CI / shared dev environments must explicitly
 # opt in via DEV_ANON_ADMIN=true in their .env.
    dev_anon_admin: bool = Field(
        default=False,
        description="If true (dev only), missing Bearer token returns role=admin",
    )

 # ── Pipeline bootstrap (one-shot full pipeline run 30s after worker start) ──
 # Reads PIPELINE_BOOTSTRAP env. Used by app/core/pipeline/bootstrap.py.
 # Production must be False — accidentally enabling this on a fresh prod
 # deployment would burn LLM tokens and seed dirty data before operators
 # can intervene.
    pipeline_bootstrap: bool = Field(
        default=False,
        description="If true, fire a one-shot full pipeline run 30s after startup (dev/empty-data only)",
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
 # fix (): 生产强制 SSL。开发可设 POSTGRES_SSLMODE=disable
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
    qwen_model_name: str = "qwen2.5:7b"
    llm_timeout: int = 60
    llm_max_retries: int = 3

 # 阿里云百炼 Qwen（2026-08-14 接入，降级链首选）——OpenAI 兼容端点
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://llm-nire844xse41iz9w.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"

 # 小米 MiMo（实际使用的 OpenAI 兼容端点，推理模型）
    mimo_api_base: str = "https://token-plan-cn.xiaomimimo.com/v1"
    mimo_api_key: str = ""
    mimo_model: str = "mimo-v2.5"

 # 备用 LLM HTTP 端点（Spark / DeepSeek OpenAI 兼容接口）
    spark_http_url: str = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    deepseek_http_url: str = "https://api.deepseek.com/chat/completions"

 # 讯飞 Spark X 深度推理（优先于 Spark 传统模型；X2 为默认端点）
 # model 固定为 spark-x（X2 与 X1.5 共用）；X2 端点 /x2/chat/completions，
 # X1.5 端点 /v2/chat/completions（2026-08-11 实测均可用，X2 12s / X1.5 7s）
    spark_x_url: str = "https://spark-api-open.xf-yun.com/x2/chat/completions"
    spark_x_model: str = "spark-x"

 # 数据源抓取与健康探测端点
    zhipin_base_url: str = "https://www.zhipin.com"
 # source_name → probe_url 兜底映射（数据源表缺失 probe_url 时用于健康探测）
    source_probe_urls: dict[str, str] = {
        "Arbeitnow (远程)": "https://arbeitnow.com/api/job-board-api",
        "Jobicy (远程)": "https://jobicy.com/api/v2/remote-jobs?count=1",
        "WeWorkRemotely (远程)": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "Remotive (远程)": "https://remotive.com/api/remote-jobs?limit=1",
    }

 # ── 阈值配置 ──
 # 抽取管线
    extraction_vector_threshold: float = 0.85
    extraction_min_sources: int = 3

 # 评估质量门禁（唯一常量， 验收口径 F1 >= 90%）
 # judge API 默认阈值 + evaluation/ 脚本门禁统一引用此值
    eval_f1_gate: float = 0.90

 # 入库完整性门禁（, ..07 CI 回归守护）——
 # evaluation/ingestion_consistency.py 引用的第二道门禁，阈值集中于此（与
 # eval_f1_gate 同模式，脚本不硬编码阈值）。SQL 口径见 docs/ingestion-kpi-calibers.md。
    ingestion_psr_tolerance: float = Field(
        default=0.005,
        ge=0.0,
        le=1.0,
        description="PG approved PSR 边数 vs Neo4j REQUIRES 边数容差（±0.5%），与 /admin/reconcile-neo4j 同口径",
    )
    ingestion_position_diff: int = Field(
        default=0,
        ge=0,
        description="count(PositionRecord) vs count(Position) 允许最大绝对差（默认 0，IS-01 P0 漂移根除）",
    )
    ingestion_skill_diff: int = Field(
        default=0,
        ge=0,
        description="count(SkillRecord) vs count(Skill) 允许最大绝对差（默认 0）",
    )
    ingestion_orphan_ratio: float = Field(
        default=0.005,
        ge=0.0,
        le=1.0,
        description="Neo4j canonical_id IS NULL 节点占比上限（<0.5%，超过即孤儿漂移）",
    )
    ingestion_dedup_rate: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="jd_raw 去重率下限（非 duplicate 行占比 ≥95%）",
    )
    ingestion_kpi_drift: float = Field(
        default=0.0,
        ge=0.0,
        description="quality dashboard 与 status_aggregator 重叠 KPI（待审计数）允许最大差（默认 0，IC-07）",
    )

 # 反幻觉守卫
    hallucination_semantic_threshold: float = 0.85
    hallucination_min_sources: int = 3
    hallucination_min_span_weeks: int = 4
    hallucination_verified_threshold: float = 0.8
    hallucination_pending_threshold: float = 0.5

 # 路径推荐（默认值与 core/evolution/path_recommender.py 的代码现状对齐，行为保持）
    path_min_similarity: float = 0.3
    path_min_evidence: int = 1

 # 信任度评分 (trust_integration)
    trust_decay_rate: float = 0.15
    trust_max_sources: int = 10
    trust_verified_threshold: float = 0.8
    trust_pending_threshold: float = 0.5
 # 演化信任写回门槛（core/evolution/trust_scorer.py WRITEBACK_TRUST_THRESHOLD）
    trust_writeback_threshold: float = 0.6

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
    pipeline_import_batch_size: int = 200  # 阶段 import 每次读取已清洗 JD 的批量上限 (2026-08-16: 500 -> 200)
    pipeline_graph_sync_reconcile_on_sync: bool = False  # graph_sync 阶段可选对账开关

 # ── 资源探测超时 ──
    httpx_health_check_timeout: float = 3.0  # 健康探测（Ollama / Redis / Neo4j 等）

 # ── Pipeline match 并发（替代 pipeline/steps.py 内的 Semaphore(50)）──
    pipeline_match_concurrency: int = 50

 # ── ①: X-Forwarded-For 可信代理白名单 (CIDR 列表, 逗号分隔)
 # 空 = 不可信, 拒绝伪造的 XFF 头 (默认最保守)
 # 生产示例: "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" (k8s 内部 + RFC1918)
    trusted_proxy_cidrs: str = Field(
        default="", description="XFF 可信代理 CIDR 白名单 (逗号分隔); 空=拒绝伪造"
    )

 # ── ②: forgot-password 通道决策
 # 默认 out_of_band: token 写入 Redis 但**不返回响应**, 等邮件/外带渠道接入
 # dev_return_token: 仅 dev 环境允许响应中回 token, 供 e2e / 手动验证
 # (字段名故意宽松, 未来可挂 "smtp" / "webhook" 等真实通道)
    forgot_password_delivery: str = Field(
        default="out_of_band",
        description="forgot-password 令牌投递方式: out_of_band (默认, 仅写 Redis) / dev_return_token (响应回 token, 仅 dev)",
    )

 # P1-AUDIT-FIX (2026-08-13): 原方法每次请求都 split + ip_network × N
 # （限流中间件/审计每请求调用一次）。trusted_proxy_cidrs 非运行时可变，
 # 缓存为 cached_property 只解析一次。
    @cached_property
    def trusted_proxy_networks(self) -> list:
        """PLAN-015①: 解析 trusted_proxy_cidrs 为 ipaddress 网列表 (惰性, 只解析一次)。"""
        import ipaddress
        if not self.trusted_proxy_cidrs:
            return []
        nets: list = []
        for raw in self.trusted_proxy_cidrs.split(","):
            cidr = raw.strip()
            if not cidr:
                continue
            try:
                nets.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                logger.warning("trusted_proxy_cidrs 忽略非法 CIDR: {!r}", cidr)
        return nets

 # ── Runtime-mutable config whitelist () ──
    _mutable_config_keys: ClassVar[set[str]] = {
        "pipeline_stage_timeout",
        "pipeline_worker_concurrency",
        "pipeline_crawl_concurrency",
        "pipeline_retry_max",
        "pipeline_retry_backoff",
        "rate_limit_window",
        "rate_limit_max",
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
 # P1-AUDIT-FIX (2026-08-13): 原实现用 `model_validate({key, app_env})`
 # 校验单字段——整模型重建开销大，且一旦 Settings 未来加必填字段
 # 就会误失败。TypeAdapter 只校验该字段类型，语义一致、开销更小。
            field_info = type(self).model_fields.get(key)
            validated_value: Any
            if field_info is not None:
                try:
                    validated_value = TypeAdapter(field_info.annotation).validate_python(value)
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
 # fix (): asyncpg 的 connect() 只接受 libpq 风格的 SSLMode
 # 字符串（disable/allow/prefer/require/verify_ca/verify_full），
 # 而不接受 libpq 旧的 `sslmode=` 或非布尔 `ssl=false/true`。
 # 直白塞 `?sslmode=...` 会让 asyncpg 抛 `unexpected keyword
 # argument 'sslmode'`（alembic 立即触发；FastAPI 的连接池懒加载
 # 偶尔能掩盖）。asyncpg 0.27+ 还会在 `ssl=` 接收到无效字符串时
 # 抛 `AttributeError: type object 'SSLMode' has no attribute ...`。
 # P1-AUDIT-FIX (2026-08-13): 此前注释声称 "prefer/allow/disable
 # 直接省略 SSL 参数"，但实际实现对所有合法 mode（含 prefer/allow/
 # disable）都显式传 `?ssl=<asyncpg_mode>`——功能正确（asyncpg 原生
 # 接受这些字符串），注释与实现不符。现按实现如实描述：
 # 把 libpq 风格 mode（可带连字符）统一转成 asyncpg 的 underscore
 # 形式透传；未知值保守回落 `?ssl=prefer`（asyncpg 默认行为）。
            sslmode = (self.postgres_sslmode or "prefer").lower()
            if sslmode in {"require", "verify-ca", "verify-full", "allow", "prefer", "disable"}:
 # asyncpg SSLMode 名称：用 underscore 形式（verify_ca / verify_full）
                asyncpg_ssl_mode = sslmode.replace("-", "_")
                ssl_query = f"?ssl={asyncpg_ssl_mode}"
            else:
 # 未知值：保守走 prefer（asyncpg 默认 = 优先加密、失败回退明文）
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
 # fix: 若 bootstrap 开启，admin 密码也算敏感字段
        if self.bootstrap_seed_admin:
            sensitive_fields["bootstrap_admin_password"] = self.bootstrap_admin_password
        unconfigured = [name for name, value in sensitive_fields.items() if value == _UNCONFIGURED]
        if unconfigured:
            msg = f"⚠️  以下配置仍为默认占位值 {_UNCONFIGURED!r}，请在 .env 中设置真实值：{', '.join(unconfigured)}"
            if self.app_env == "production":
 # P1 修复 (/): 生产环境必须配置真实密钥/密码
                raise RuntimeError(msg + "（生产环境必须修改！）")
            else:
                logger.warning(msg)

 # P1 fix: production environment must have debug mode disabled
        if self.app_env == "production" and self.app_debug:
            raise RuntimeError("Debug mode (APP_DEBUG=True) must be disabled in production environment")

 # P1 修复 (): 生产环境 Redis 必须有密码
        if self.app_env == "production" and "@" not in self.redis_uri:
            raise RuntimeError(
                "Redis URI 缺少密码认证（生产环境必须配置 REDIS_URL 含密码），格式：redis://:password@host:port/db"
            )

 # P1 修复 (): 生产环境 SECRET_KEY 必须足够长
        if self.app_env == "production" and len(self.secret_key) < 32:
            raise RuntimeError(
                f"SECRET_KEY 长度不足（当前 {len(self.secret_key)} 字符），"
                f"生产环境至少需要 32 字符。"
                f'生成方式：python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

 # fix: 生产环境必须配置独立的 bootstrap_admin_password
        if self.app_env == "production" and self.bootstrap_admin_password == _UNCONFIGURED:
            raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD 未配置。生产环境必须在 .env.production 中设置强密码。")

 # NEW-P1a (AUDIT_VERIFICATION C5): 生产严禁自动播种弱管理员。
 # 即便运维误把 .env.production 的 BOOTSTRAP_SEED_ADMIN 设回 true，
 # 启动期也必须 fail-fast，不允许 admin:starmap2024 进入生产库。
        if self.app_env == "production" and self.bootstrap_seed_admin:
            raise RuntimeError(
                "BOOTSTRAP_SEED_ADMIN=true 在生产环境被拒绝。"
                "生产部署严禁自动播种管理员账户；"
                "请通过 /api/v1/admin/users 显式创建。"
            )

 # (PLAN §): dev 匿名 admin 旁路仅允许在 dev 且显式 opt-in。
 # 生产部署绝不允许启用——它会让匿名请求获得 admin 角色。
        if self.app_env == "production" and self.dev_anon_admin:
            raise RuntimeError("DEV_ANON_ADMIN=true 在生产环境被拒绝。生产部署必须强制 JWT 鉴权。")

 # public-deploy-preflight 2026-08-20 (P0): 生产严禁开启一次性全量 bootstrap run。
 # 误开会在首启 30s 后自动跑全量管线，烧光 LLM token 且写脏数据。
        if self.app_env == "production" and self.pipeline_bootstrap:
            raise RuntimeError(
                "PIPELINE_BOOTSTRAP=true 在生产环境被拒绝。"
                "生产部署严禁首启自动跑全量管线；"
                "请通过 /admin/seed/reset 或 admin API 显式触发。"
            )

 # public-deploy-preflight 2026-08-20 (P0): 生产严禁 forgot-password token 直接返回响应。
 # 误开会让任何 email 拿到 reset token 接管账户——高危账户接管风险。
        if self.app_env == "production" and self.forgot_password_delivery == "dev_return_token":
            raise RuntimeError(
                "FORGOT_PASSWORD_DELIVERY=dev_return_token 在生产环境被拒绝。"
                "生产部署必须使用 out_of_band（仅写 Redis，由邮件渠道投递 token）。"
            )

 # fix (): 生产 Postgres 必须强制 SSL。
 # 仅 `require`/`verify-ca`/`verify-full` 三档视为合规。
 # `disable`/`prefer`/`allow` 在生产等同裸奔——拒绝启动。
        if self.app_env == "production":
            sslmode = (self.postgres_sslmode or "").lower()
            if sslmode not in {"require", "verify-ca", "verify-full"}:
                raise RuntimeError(
                    f"POSTGRES_SSLMODE={self.postgres_sslmode!r} 在生产环境被拒绝。"
                    f"生产必须使用 require / verify-ca / verify-full 之一。"
                )

 # fix (): 生产 Neo4j 必须走 bolt+s://。
 # 否则 Bolt 协议明文传输，节点凭据与查询内容均裸奔。
        if self.app_env == "production" and not self.neo4j_uri.startswith(("bolt+s://", "neo4j+s://", "bolt+ssc://")):
            raise RuntimeError(f"NEO4J_URI={self.neo4j_uri!r} 在生产环境被拒绝。生产必须使用 bolt+s:// 启用 TLS。")

 # fix: 生产 CORS 白名单校验
 # 默认 cors_origins 仅含 localhost dev 端口，生产必须通过
 # CORS_ALLOWED_ORIGINS 环境变量显式覆盖为真实域名。
 # 任何 dev-only origin 出现即拒绝（混合配置也拦截）
        if self.app_env == "production":
            _dev_only_origins = {
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5176",
                "http://127.0.0.1:5176",
                "http://localhost:5174",
                "http://localhost:5175",
            }
            _found_dev_origins = [o for o in self.cors_origins if o in _dev_only_origins]
            if _found_dev_origins:
                raise RuntimeError(
                    f"CORS_ALLOWED_ORIGINS 包含开发环境专有 origin: {_found_dev_origins}。"
                    f"生产环境必须通过 CORS_ALLOWED_ORIGINS 环境变量移除所有 dev localhost 值。"
                    f"如需添加生产域名，请设置 CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com"
                )

 # public-deploy-preflight 2026-08-20 (P0): TrustedHostMiddleware 必须显式允许。
 # 默认 ["*"] 在 dev OK；生产必须 ALLOWED_HOSTS=starmap.example.com,api.example.com 防止 Host header 注入。
        if self.app_env == "production" and (not self.allowed_hosts or self.allowed_hosts == ["*"]):
            raise RuntimeError(
                "ALLOWED_HOSTS 未配置或仍为通配符 ['*']。"
                "生产环境必须显式列出 TrustedHostMiddleware 允许的 Host 头（逗号分隔）。"
                "例如 ALLOWED_HOSTS=starmap.example.com,api.example.com"
            )

 # Phase DB-AUTH: 密码策略由 PostgreSQL users 表的 bcrypt hash 保证
 # 这里不再做 AUTH_USERS plaintext 校验（该 env 已废弃）

 # : LLM key 启动校验 — 仅 WARNING 不阻止启动
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
