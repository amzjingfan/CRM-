"""集中管理应用配置，避免业务代码直接读取环境变量。"""

from decimal import Decimal
from functools import lru_cache
from ipaddress import ip_address
from math import ceil
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.config.llm_pricing import validate_approved_llm_pricing

SOURCE_ROOT = Path(__file__).resolve().parents[4]
PROJECT_ENV_FILE = SOURCE_ROOT / "config" / ".env"

# TikTok Partner Center、反向代理和 FastAPI 必须共享同一回调契约。真实环境
# 不允许通过环境变量改变域名或路径；测试环境只允许替换主机，便于使用假凭证验证流程。
TIKTOK_OAUTH_CALLBACK_ROUTE = "/integrations/tiktok/oauth/callback"
TIKTOK_OAUTH_PUBLIC_CALLBACK_PATH = f"/v1{TIKTOK_OAUTH_CALLBACK_ROUTE}"
TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI = f"https://www.overselfx.com{TIKTOK_OAUTH_PUBLIC_CALLBACK_PATH}"
TIKTOK_OAUTH_STAGING_REDIRECT_URI = f"https://staging.overselfx.com{TIKTOK_OAUTH_PUBLIC_CALLBACK_PATH}"
# 兼容仍导入旧常量的生产调用方；新代码应按 app_env 使用映射常量。
TIKTOK_OAUTH_FIXED_REDIRECT_URI = TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI
TIKTOK_OAUTH_FIXED_REDIRECT_URIS = {
    "integration": TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI,
    "staging": TIKTOK_OAUTH_STAGING_REDIRECT_URI,
    "production": TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI,
}
TIKTOK_FIXED_EGRESS_PROXY_URL = "socks5h://tiktok-egress:1080"
REAL_DEPLOYMENT_ENVIRONMENTS = {"integration", "staging", "production"}
TIKTOK_REAL_READ_SCOPES = {
    "seller.authorization.info",
    "seller.order.info",
    "seller.customer_service",
    "seller.logistics",
}
CHAT_STREAM_LEASE_GRACE_SECONDS = 60
SSE_LOAD_TEST_MINIMUM_QUERY_LIMIT = 50


def has_non_blank_secret(value: SecretStr | None) -> bool:
    """判断密钥是否真实包含非空白内容，不在返回值或日志中展开密钥。"""
    return value is not None and bool(value.get_secret_value().strip())


class Settings(BaseSettings):
    """应用运行配置。"""

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_name: str = Field(default="crm-chat-system", validation_alias="APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://crm:crm@localhost:5432/crm",
        validation_alias="DATABASE_URL",
        repr=False,
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
        repr=False,
    )
    minio_endpoint: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minio", validation_alias="MINIO_ACCESS_KEY", repr=False)
    minio_secret_key: str = Field(default="change-me", validation_alias="MINIO_SECRET_KEY", repr=False)
    minio_bucket: str = Field(default="crm-files", validation_alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, validation_alias="MINIO_SECURE")
    knowledge_import_max_bytes: int = Field(default=10_485_760, validation_alias="KNOWLEDGE_IMPORT_MAX_BYTES")
    knowledge_import_max_rows: int = Field(default=5000, validation_alias="KNOWLEDGE_IMPORT_MAX_ROWS")
    jobs_poll_seconds: float = Field(default=1.0, gt=0, le=60, validation_alias="JOBS_POLL_SECONDS")
    marketing_poll_seconds: float = Field(default=60.0, gt=0, le=300, validation_alias="MARKETING_POLL_SECONDS")
    ai_marketing_enabled: bool = Field(default=False, validation_alias="AI_MARKETING_ENABLED")
    metrics_poll_seconds: float = Field(default=300.0, gt=0, le=3600, validation_alias="METRICS_POLL_SECONDS")
    request_timeout_seconds: float = Field(default=30.0, gt=1, le=300, validation_alias="REQUEST_TIMEOUT_SECONDS")
    chat_query_limit: int = Field(default=10, ge=1, le=1000, validation_alias="CHAT_QUERY_LIMIT")
    chat_query_window_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        validation_alias="CHAT_QUERY_WINDOW_SECONDS",
    )
    chat_user_concurrency: int = Field(default=2, ge=1, le=20, validation_alias="CHAT_USER_CONCURRENCY")
    chat_stream_timeout_seconds: float = Field(
        default=180.0,
        gt=5,
        le=600,
        validation_alias="CHAT_STREAM_TIMEOUT_SECONDS",
    )
    chat_sse_heartbeat_seconds: float = Field(
        default=15.0,
        gt=1,
        le=30,
        validation_alias="CHAT_SSE_HEARTBEAT_SECONDS",
    )
    sse_load_test_enabled: bool = Field(default=False, validation_alias="SSE_LOAD_TEST_ENABLED")
    auto_reply_enabled: bool = Field(default=False, validation_alias="AUTO_REPLY_ENABLED")
    auto_reply_poll_seconds: float = Field(default=1.0, gt=0, le=60, validation_alias="AUTO_REPLY_POLL_SECONDS")
    auto_reply_max_attempts: int = Field(default=3, ge=1, le=3, validation_alias="AUTO_REPLY_MAX_ATTEMPTS")
    jwt_secret_key: str = Field(
        default="development-only-change-me-32-bytes",
        validation_alias="JWT_SECRET_KEY",
        repr=False,
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=120, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")
    auth_cookie_domain: str | None = Field(default=None, validation_alias="AUTH_COOKIE_DOMAIN")
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", validation_alias="AUTH_COOKIE_SAMESITE")
    auth_login_limit: int = Field(default=10, validation_alias="AUTH_LOGIN_LIMIT")
    auth_login_window_seconds: int = Field(default=900, validation_alias="AUTH_LOGIN_WINDOW_SECONDS")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    api_prefix: str = Field(default="/v1", validation_alias="API_PREFIX")
    public_base_url: str | None = Field(default=None, validation_alias="PUBLIC_BASE_URL")
    allow_mock_platform_adapters: bool = Field(
        default=False,
        validation_alias="ALLOW_MOCK_PLATFORM_ADAPTERS",
    )
    webhook_max_body_bytes: int = Field(default=1_048_576, validation_alias="WEBHOOK_MAX_BODY_BYTES")
    webhook_max_retries: int = Field(default=3, validation_alias="WEBHOOK_MAX_RETRIES")
    webhook_poll_seconds: float = Field(default=1.0, validation_alias="WEBHOOK_POLL_SECONDS")
    webhook_payload_retention_days: int = Field(default=30, validation_alias="WEBHOOK_PAYLOAD_RETENTION_DAYS")
    tiktok_webhook_secret: SecretStr = Field(
        default=SecretStr("change-me-tiktok"),
        validation_alias="TIKTOK_WEBHOOK_SECRET",
    )
    tiktok_app_key: str = Field(default="mock-app", validation_alias="TIKTOK_APP_KEY")
    tiktok_service_id: str | None = Field(default=None, validation_alias="TIKTOK_SERVICE_ID")
    tiktok_app_secret: SecretStr | None = Field(default=None, validation_alias="TIKTOK_APP_SECRET")
    tiktok_oauth_redirect_uri: str | None = Field(default=None, validation_alias="TIKTOK_OAUTH_REDIRECT_URI")
    tiktok_oauth_market: Literal["US", "ROW"] = Field(default="ROW", validation_alias="TIKTOK_OAUTH_MARKET")
    tiktok_oauth_state_ttl_seconds: int = Field(
        default=600,
        ge=60,
        le=1800,
        validation_alias="TIKTOK_OAUTH_STATE_TTL_SECONDS",
    )
    tiktok_token_refresh_poll_seconds: float = Field(
        default=300.0,
        gt=0,
        le=3600,
        validation_alias="TIKTOK_TOKEN_REFRESH_POLL_SECONDS",
    )
    tiktok_token_refresh_lead_seconds: int = Field(
        default=86_400,
        ge=3600,
        le=604_800,
        validation_alias="TIKTOK_TOKEN_REFRESH_LEAD_SECONDS",
    )
    tiktok_token_refresh_batch_size: int = Field(
        default=20,
        ge=1,
        le=100,
        validation_alias="TIKTOK_TOKEN_REFRESH_BATCH_SIZE",
    )
    tiktok_required_scopes: str = Field(
        default="seller.authorization.info,seller.order.info,seller.customer_service,seller.logistics",
        validation_alias="TIKTOK_REQUIRED_SCOPES",
    )
    tiktok_credential_encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias="TIKTOK_CREDENTIAL_ENCRYPTION_KEY",
    )
    tiktok_egress_ip: str | None = Field(default=None, validation_alias="TIKTOK_EGRESS_IP")
    tiktok_egress_proxy_url: str | None = Field(default=None, validation_alias="TIKTOK_EGRESS_PROXY_URL")
    real_tiktok_read_enabled: bool = Field(default=False, validation_alias="REAL_TIKTOK_READ_ENABLED")
    tiktok_conversation_sync_enabled: bool = Field(default=False, validation_alias="TIKTOK_CONVERSATION_SYNC_ENABLED")
    tiktok_conversation_sync_poll_seconds: float = Field(
        default=900.0, ge=60, le=86_400, validation_alias="TIKTOK_CONVERSATION_SYNC_POLL_SECONDS"
    )
    real_tiktok_webhook_enabled: bool = Field(default=False, validation_alias="REAL_TIKTOK_WEBHOOK_ENABLED")
    real_tiktok_message_write_enabled: bool = Field(
        default=False,
        validation_alias="REAL_TIKTOK_MESSAGE_WRITE_ENABLED",
    )
    real_tiktok_high_risk_write_enabled: bool = Field(
        default=False,
        validation_alias="REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED",
    )
    shopee_webhook_secret: str = Field(
        default="change-me-shopee",
        validation_alias="SHOPEE_WEBHOOK_SECRET",
        repr=False,
    )
    amazon_webhook_secret: str = Field(
        default="change-me-amazon",
        validation_alias="AMAZON_WEBHOOK_SECRET",
        repr=False,
    )
    llm_enabled: bool = Field(default=False, validation_alias="LLM_ENABLED")
    llm_live_eval: bool = Field(default=False, validation_alias="LLM_LIVE_EVAL")
    ai_synthetic_demo_enabled: bool = Field(default=False, validation_alias="AI_SYNTHETIC_DEMO_ENABLED")
    ai_translation_enabled: bool = Field(default=False, validation_alias="AI_TRANSLATION_ENABLED")
    workspace_message_translation_enabled: bool = Field(
        default=False, validation_alias="WORKSPACE_MESSAGE_TRANSLATION_ENABLED"
    )
    llm_primary_provider: str = Field(default="openai", validation_alias="LLM_PRIMARY_PROVIDER")
    llm_primary_model: str | None = Field(default=None, validation_alias="LLM_PRIMARY_MODEL")
    llm_fallback_provider: str | None = Field(default="anthropic", validation_alias="LLM_FALLBACK_PROVIDER")
    llm_fallback_model: str | None = Field(default=None, validation_alias="LLM_FALLBACK_MODEL")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    deepseek_api_key: SecretStr | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_thinking_enabled: bool = Field(default=False, validation_alias="DEEPSEEK_THINKING_ENABLED")
    llm_timeout_seconds: float = Field(default=15.0, gt=0, le=120, validation_alias="LLM_TIMEOUT_SECONDS")
    llm_max_attempts: int = Field(default=3, ge=1, le=3, validation_alias="LLM_MAX_ATTEMPTS")
    llm_max_output_tokens: int = Field(
        default=256,
        ge=64,
        le=2048,
        validation_alias="LLM_MAX_OUTPUT_TOKENS",
    )
    llm_input_cost_per_million_usd: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        validation_alias="LLM_INPUT_COST_PER_MILLION_USD",
    )
    llm_output_cost_per_million_usd: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        validation_alias="LLM_OUTPUT_COST_PER_MILLION_USD",
    )
    llm_pricing_version: str | None = Field(default=None, validation_alias="LLM_PRICING_VERSION")
    llm_pricing_currency: Literal["USD"] = Field(default="USD", validation_alias="LLM_PRICING_CURRENCY")
    llm_pricing_basis: Literal["not_configured", "flat_estimate", "conservative_peak_cache_miss"] = Field(
        default="not_configured",
        validation_alias="LLM_PRICING_BASIS",
    )
    embedding_enabled: bool = Field(default=False, validation_alias="EMBEDDING_ENABLED")
    embedding_provider: str = Field(default="local_bge", validation_alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-m3", validation_alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1024, ge=1, le=4096, validation_alias="EMBEDDING_DIMENSIONS")
    embedding_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        le=120,
        validation_alias="EMBEDDING_TIMEOUT_SECONDS",
    )
    embedding_max_attempts: int = Field(default=3, ge=1, le=3, validation_alias="EMBEDDING_MAX_ATTEMPTS")
    embedding_batch_size: int = Field(default=4, ge=1, le=128, validation_alias="EMBEDDING_BATCH_SIZE")
    embedding_max_length: int = Field(default=8192, ge=128, le=8192, validation_alias="EMBEDDING_MAX_LENGTH")
    retrieval_model_service_url: str = Field(
        default="http://retrieval-model-service:8010",
        validation_alias="RETRIEVAL_MODEL_SERVICE_URL",
    )
    retrieval_model_service_token: SecretStr | None = Field(
        default=None,
        validation_alias="RETRIEVAL_MODEL_SERVICE_TOKEN",
    )
    readiness_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        le=30,
        validation_alias="READINESS_TIMEOUT_SECONDS",
    )
    bge_m3_model_path: Path = Field(default=Path("/models/bge-m3"), validation_alias="BGE_M3_MODEL_PATH")
    bge_reranker_model_path: Path = Field(
        default=Path("/models/bge-reranker-large"),
        validation_alias="BGE_RERANKER_MODEL_PATH",
    )
    retrieval_model_device: str = Field(default="auto", validation_alias="RETRIEVAL_MODEL_DEVICE")
    retrieval_model_use_fp16: bool = Field(default=True, validation_alias="RETRIEVAL_MODEL_USE_FP16")
    retrieval_model_verify_hashes: bool = Field(
        default=False,
        validation_alias="RETRIEVAL_MODEL_VERIFY_HASHES",
    )
    reranker_batch_size: int = Field(default=4, ge=1, le=32, validation_alias="RERANKER_BATCH_SIZE")
    reranker_max_length: int = Field(default=512, ge=64, le=512, validation_alias="RERANKER_MAX_LENGTH")
    reranker_max_attempts: int = Field(default=2, ge=1, le=3, validation_alias="RERANKER_MAX_ATTEMPTS")
    rag_dense_top_k: int = Field(default=20, ge=1, le=100, validation_alias="RAG_DENSE_TOP_K")
    rag_lexical_top_k: int = Field(default=20, ge=1, le=100, validation_alias="RAG_LEXICAL_TOP_K")
    rag_candidate_top_k: int = Field(default=20, ge=1, le=100, validation_alias="RAG_CANDIDATE_TOP_K")
    rag_top_k: int = Field(default=5, ge=1, le=10, validation_alias="RAG_TOP_K")
    rag_rrf_k: int = Field(default=60, ge=1, le=1000, validation_alias="RAG_RRF_K")
    rag_min_score: float = Field(default=0.52, ge=0, le=1, validation_alias="RAG_MIN_SCORE")
    rag_min_lexical_score: float = Field(
        default=0.10,
        ge=0,
        le=1,
        validation_alias="RAG_MIN_LEXICAL_SCORE",
    )
    rag_max_context_tokens: int = Field(default=6000, ge=256, le=20_000, validation_alias="RAG_MAX_CONTEXT_TOKENS")
    agent_auto_reply_threshold: float = Field(
        default=0.80,
        ge=0,
        le=1,
        validation_alias="AGENT_AUTO_REPLY_THRESHOLD",
    )
    agent_human_review_threshold: float = Field(
        default=0.60,
        ge=0,
        le=1,
        validation_alias="AGENT_HUMAN_REVIEW_THRESHOLD",
    )

    # 本地环境文件固定在 src/config；容器通过 Compose 注入变量，不要求镜像内存在该文件。
    # 使用绝对路径避免从 backend/ 执行评测、迁移或测试时静默回退到默认配置。
    model_config = SettingsConfigDict(env_file=PROJECT_ENV_FILE, extra="ignore", case_sensitive=False)

    @model_validator(mode="after")
    def validate_production_runtime(self) -> Self:
        """在进程启动前校验 staging/production 基础安全和真实平台能力门禁。

        业务边界：REAL-FS-04 只放行人工确认的普通消息；高风险写入和
        自动回复仍属于后续阶段，配置为 true 时必须在启动阶段失败关闭。
        """
        if self.app_env not in {"development", "test", "integration", "staging", "production"}:
            raise ValueError("APP_ENV 必须为受支持的环境名称")
        if self.app_env == "production" and self.llm_live_eval:
            raise ValueError("生产环境禁止启用真实模型评测")
        if self.ai_synthetic_demo_enabled and self.app_env not in {"development", "test"}:
            raise ValueError("AI 合成演示只允许在 development/test 环境启用")
        if self.app_env in REAL_DEPLOYMENT_ENVIRONMENTS:
            self.validate_tiktok_oauth_redirect_uri()
        if self.llm_live_eval and not self.llm_enabled:
            raise ValueError("启用真实模型评测时必须同时启用 LLM")
        if self.llm_live_eval:
            pricing_version = (self.llm_pricing_version or "").strip()
            if (
                self.llm_input_cost_per_million_usd <= 0
                or self.llm_output_cost_per_million_usd <= 0
                or not pricing_version
                or self.llm_pricing_basis == "not_configured"
            ):
                raise ValueError("启用真实模型评测时必须配置正数 Token 单价、价格版本和计价口径")
            validate_approved_llm_pricing(
                provider=self.llm_primary_provider,
                model=self.llm_primary_model or "",
                version=pricing_version,
                currency=self.llm_pricing_currency,
                basis=self.llm_pricing_basis,
                input_per_million=self.llm_input_cost_per_million_usd,
                output_per_million=self.llm_output_cost_per_million_usd,
            )
        if self.ai_synthetic_demo_enabled and not self.llm_enabled:
            raise ValueError("启用 AI 合成演示时必须同时启用 LLM")
        if self.auto_reply_enabled and not self.llm_enabled:
            raise ValueError("启用自动回复时必须同时启用 LLM")
        if self.chat_sse_heartbeat_seconds >= self.chat_stream_timeout_seconds:
            raise ValueError("SSE 心跳间隔必须小于 AI 建议总超时时间")
        if self.sse_load_test_enabled:
            if self.app_env not in {"integration", "staging"}:
                raise ValueError("SSE 专用压测配置只允许在 integration/staging 环境启用")
            if self.chat_query_limit < SSE_LOAD_TEST_MINIMUM_QUERY_LIMIT:
                raise ValueError("SSE 专用压测的 CHAT_QUERY_LIMIT 不得低于 50")

        real_tiktok_enabled = any(
            (
                self.real_tiktok_read_enabled,
                self.real_tiktok_webhook_enabled,
                self.real_tiktok_message_write_enabled,
                self.real_tiktok_high_risk_write_enabled,
            )
        )
        if self.real_tiktok_message_write_enabled and not self.real_tiktok_read_enabled:
            raise ValueError("启用 TikTok 普通消息写入前必须先启用真实只读能力")
        if self.real_tiktok_webhook_enabled and not self.real_tiktok_read_enabled:
            raise ValueError("启用 TikTok Webhook 前必须先启用真实只读能力")
        if self.real_tiktok_high_risk_write_enabled and not self.real_tiktok_message_write_enabled:
            raise ValueError("启用 TikTok 高风险写入前必须先启用普通消息写入")
        if real_tiktok_enabled:
            self._validate_real_tiktok_prerequisites()
        if self.real_tiktok_message_write_enabled and self.auto_reply_enabled:
            raise ValueError("REAL-FS-04 真实 TikTok 普通消息仅允许人工确认发送，禁止同时启用自动回复")
        if self.real_tiktok_high_risk_write_enabled:
            raise ValueError("真实 TikTok 高风险写入尚未完成后续灰度，禁止启用")
        if self.app_env in REAL_DEPLOYMENT_ENVIRONMENTS and self.llm_enabled:
            self._validate_production_llm()

        # staging 公网部署与 production 使用相同基础安全要求；integration
        # 保留合成夹具能力，其真实平台、LLM 和压测开关仍受上方独立门禁约束。
        if self.app_env not in {"staging", "production"}:
            return self
        environment_label = "生产环境" if self.app_env == "production" else "预发布环境"
        if self.allow_mock_platform_adapters:
            raise ValueError(f"{environment_label}禁止启用契约级 Mock 平台适配器")
        if not self.auth_cookie_secure:
            raise ValueError(f"{environment_label}必须启用 Secure 认证 Cookie")
        if len(self.jwt_secret_key) < 32 or "change-me" in self.jwt_secret_key.lower():
            raise ValueError(f"{environment_label} JWT_SECRET_KEY 必须使用至少 32 字符的非示例密钥")
        if len(self.minio_secret_key) < 16 or "change-me" in self.minio_secret_key.lower():
            raise ValueError(f"{environment_label} MINIO_SECRET_KEY 必须使用非示例密钥")
        if "crm:crm@" in self.database_url.lower():
            raise ValueError(f"{environment_label} DATABASE_URL 不得使用开发默认凭证")
        self._validate_https_url(self.public_base_url, "PUBLIC_BASE_URL")
        origins = self.cors_origin_list
        if not origins:
            raise ValueError(f"{environment_label} CORS_ORIGINS 必须只包含明确的 HTTPS 来源")
        for origin in origins:
            self._validate_cors_origin(origin)
        if not self.tiktok_egress_ip:
            raise ValueError(f"{environment_label}必须声明已分配的 TIKTOK_EGRESS_IP")
        try:
            ip_address(self.tiktok_egress_ip)
        except ValueError as error:
            raise ValueError("TIKTOK_EGRESS_IP 必须为有效的固定出口 IP") from error
        return self

    def _validate_real_tiktok_prerequisites(self) -> None:
        """校验真实 TikTok 能力未来启用时必须具备的低层配置。"""
        if self.tiktok_app_key in {"", "mock-app"}:
            raise ValueError("真实 TikTok 能力必须配置正式 TIKTOK_APP_KEY")
        if not self.tiktok_service_id:
            raise ValueError("真实 TikTok 能力必须配置 TIKTOK_SERVICE_ID")
        if self.tiktok_app_secret is None or len(self.tiktok_app_secret.get_secret_value()) < 16:
            raise ValueError("真实 TikTok 能力必须配置 TIKTOK_APP_SECRET")
        if self.tiktok_credential_encryption_key is None:
            raise ValueError("真实 TikTok 能力必须配置凭证加密密钥")
        if len(self.tiktok_credential_encryption_key.get_secret_value()) < 32:
            raise ValueError("TikTok 凭证加密密钥必须至少 32 个字符")
        self.validate_tiktok_oauth_redirect_uri()
        if not self.tiktok_egress_ip:
            raise ValueError("真实 TikTok 能力必须配置固定出口 IP")
        try:
            ip_address(self.tiktok_egress_ip)
        except ValueError as error:
            raise ValueError("TIKTOK_EGRESS_IP 必须为有效 IP") from error
        self._validate_tiktok_egress_proxy()
        if self.real_tiktok_read_enabled and not TIKTOK_REAL_READ_SCOPES.issubset(self.tiktok_required_scope_set):
            raise ValueError("真实 TikTok 只读能力必须声明授权、订单、客服消息和物流 Scope")

    def _validate_tiktok_egress_proxy(self) -> None:
        """真实 TikTok 请求只允许走显式、无凭据的 SOCKS5H 固定出口。"""
        value = self.tiktok_egress_proxy_url
        if not value:
            raise ValueError("真实 TikTok 能力必须配置 TIKTOK_EGRESS_PROXY_URL")
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("TIKTOK_EGRESS_PROXY_URL 必须包含有效端口") from error
        if parsed.scheme != "socks5h" or not parsed.hostname or port is None:
            raise ValueError("TIKTOK_EGRESS_PROXY_URL 必须为带显式端口的 SOCKS5H URL")
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("TIKTOK_EGRESS_PROXY_URL 不得包含凭证、路径、查询参数或片段")
        if self.app_env in {"staging", "production"} and value != TIKTOK_FIXED_EGRESS_PROXY_URL:
            raise ValueError("TIKTOK_EGRESS_PROXY_URL 必须使用真实环境固定代理地址")

    def _validate_production_llm(self) -> None:
        """校验生产 LLM 的最低配置，不展开或记录任何 SecretStr。"""
        if not self.llm_primary_model or not self.llm_primary_model.strip():
            raise ValueError("生产环境启用 LLM 时必须配置主模型")
        provider = self.llm_primary_provider.strip().lower()
        if provider not in {"deepseek", "openai", "anthropic"}:
            raise ValueError("生产环境主模型 Provider 不在白名单")
        if provider == "deepseek" and not has_non_blank_secret(self.deepseek_api_key):
            raise ValueError("生产环境启用 DeepSeek 时必须安全注入 API Key")
        if provider == "openai" and not has_non_blank_secret(self.openai_api_key):
            raise ValueError("生产环境启用 OpenAI 时必须安全注入 API Key")
        if provider == "anthropic" and not has_non_blank_secret(self.anthropic_api_key):
            raise ValueError("生产环境启用 Anthropic 时必须安全注入 API Key")
        if provider == "deepseek":
            self._validate_https_url(self.deepseek_base_url, "DEEPSEEK_BASE_URL")

    def validate_tiktok_oauth_redirect_uri(self) -> None:
        """校验 OAuth 回调与应用实际路由及真实环境固定域名一致。"""
        value = self.tiktok_oauth_redirect_uri
        self._validate_https_url(value, "TIKTOK_OAUTH_REDIRECT_URI")
        if value is None:  # 纵深防御：即使校验函数后续调整，也不允许空值继续解析。
            raise ValueError("TIKTOK_OAUTH_REDIRECT_URI 不能为空")
        parsed = urlsplit(value)
        if parsed.path != TIKTOK_OAUTH_PUBLIC_CALLBACK_PATH:
            raise ValueError("TIKTOK_OAUTH_REDIRECT_URI 必须使用固定 OAuth 回调路径")
        if self.app_env in REAL_DEPLOYMENT_ENVIRONMENTS and value != TIKTOK_OAUTH_FIXED_REDIRECT_URIS[self.app_env]:
            raise ValueError("TIKTOK_OAUTH_REDIRECT_URI 必须与真实环境固定回调地址完全一致")

    @staticmethod
    def _validate_https_url(value: str | None, field_name: str) -> None:
        """要求公网地址使用无内嵌凭证、查询串或片段的 HTTPS URL。"""
        if not value:
            raise ValueError(f"{field_name} 不能为空")
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError(f"{field_name} 必须为有效的 HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"{field_name} 不得包含凭证、查询参数或片段")

    @staticmethod
    def _validate_cors_origin(origin: str) -> None:
        """按浏览器 Origin 语法校验真实部署环境跨域来源。

        Origin 只允许协议、主机和可选端口。路径、凭证、查询参数或片段
        都不是合法来源，若被接受会让配置错误绕过部署启动门禁。
        """
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError as error:
            raise ValueError("真实部署环境 CORS_ORIGINS 包含无效来源") from error
        if (
            origin == "*"
            or origin != origin.strip()
            or "*" in parsed.netloc
            or parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("真实部署环境 CORS_ORIGINS 必须只包含明确的 HTTPS 来源")

    @model_validator(mode="after")
    def validate_enabled_local_bge(self) -> Self:
        """在启动阶段阻止本地 BGE 与数据库/内部服务契约不一致。

        AI 默认关闭时允许开发者不配置模型服务；一旦启用，必须使用架构师
        确认的 1024 维 BGE-M3 和足够强的内部服务令牌，避免把 1536 维旧向量
        写入当前 pgvector 字段，或让内部推理端点处于弱认证状态。
        """
        if (self.ai_marketing_enabled or self.ai_translation_enabled) and not self.llm_enabled:
            raise ValueError("启用 AI 翻译或营销时必须同时启用 LLM")
        if self.workspace_message_translation_enabled and (
            self.app_env == "production"
            or self.llm_primary_provider != "deepseek"
            or not self.llm_primary_model
            or self.deepseek_api_key is None
        ):
            raise ValueError("工作台消息翻译仅限非生产环境且必须配置 DeepSeek 模型")
        if not self.embedding_enabled:
            return self
        if self.embedding_provider != "local_bge":
            raise ValueError("启用向量化时 EMBEDDING_PROVIDER 必须为 local_bge")
        if self.embedding_model.lower() not in {"baai/bge-m3", "bge-m3"}:
            raise ValueError("启用向量化时 EMBEDDING_MODEL 必须为 BAAI/bge-m3")
        if self.embedding_dimensions != 1024:
            raise ValueError("BGE-M3 向量维度必须为 1024")
        token = self.retrieval_model_service_token
        if token is None or len(token.get_secret_value()) < 32:
            raise ValueError("内部模型服务令牌必须至少为 32 个字符")
        parsed_url = urlsplit(self.retrieval_model_service_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("内部模型服务地址必须为有效的 HTTP(S) URL")
        if parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
            raise ValueError("内部模型服务地址不得包含凭证、查询参数或片段")
        if self.rag_top_k > self.rag_candidate_top_k:
            raise ValueError("最终 RAG Top K 不能超过混合检索候选数量")
        if self.rag_candidate_top_k > self.rag_dense_top_k + self.rag_lexical_top_k:
            raise ValueError("混合检索候选数量不能超过 Dense 与词法召回数量之和")
        return self

    @property
    def chat_stream_lease_seconds(self) -> int:
        """返回 SSE 并发租约时长，覆盖总超时并预留取消和传输清理时间。"""
        return ceil(self.chat_stream_timeout_seconds + CHAT_STREAM_LEASE_GRACE_SECONDS)

    @property
    def cors_origin_list(self) -> list[str]:
        """返回经过清洗的 CORS 来源列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def tiktok_required_scope_set(self) -> set[str]:
        """返回 OAuth 回调必须授予的 TikTok Scope 集合。"""
        return {scope.strip() for scope in self.tiktok_required_scopes.split(",") if scope.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回进程内复用的配置实例。"""
    return Settings()
