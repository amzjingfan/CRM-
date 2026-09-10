"""真实环境配置与日志出口安全测试。"""

import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.shared.config.settings import (
    TIKTOK_OAUTH_FIXED_REDIRECT_URI,
    TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI,
    TIKTOK_OAUTH_STAGING_REDIRECT_URI,
    Settings,
)
from app.shared.logging.setup import JsonFormatter, redact_log_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def production_settings(**overrides: object) -> Settings:
    """构造不包含真实凭证的生产配置测试样本。"""
    values: dict[str, object] = {
        "APP_ENV": "production",
        "PUBLIC_BASE_URL": "https://www.example.com",
        "CORS_ORIGINS": "https://www.example.com",
        "AUTH_COOKIE_SECURE": True,
        "ALLOW_MOCK_PLATFORM_ADAPTERS": False,
        "JWT_SECRET_KEY": "unit-test-jwt-secret-with-at-least-32-characters",
        "DATABASE_URL": "postgresql+asyncpg://crm:strong-password@postgres:5432/crm",
        "MINIO_SECRET_KEY": "unit-test-minio-secret",
        "TIKTOK_EGRESS_IP": "203.0.113.10",
        "TIKTOK_OAUTH_REDIRECT_URI": TIKTOK_OAUTH_FIXED_REDIRECT_URI,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def compose_service_block(compose_text: str, service_name: str) -> str:
    """提取指定服务的 YAML 文本块，供不依赖 Docker 的配置契约测试使用。"""
    lines = compose_text.splitlines()
    start = lines.index(f"  {service_name}:")
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            break
        block.append(line)
    return "\n".join(block)


def test_safe_production_configuration_can_start_with_real_capabilities_disabled() -> None:
    """真实适配器未接入时，安全生产基础服务仍应允许启动。"""
    settings = production_settings()
    assert settings.app_env == "production"
    assert settings.real_tiktok_read_enabled is False
    assert settings.auto_reply_enabled is False


def test_production_rejects_mock_platform_adapters() -> None:
    """生产环境不得通过打开 Mock 开关绕过真实平台门禁。"""
    with pytest.raises(ValidationError, match="生产环境禁止启用契约级 Mock"):
        production_settings(ALLOW_MOCK_PLATFORM_ADAPTERS=True)


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize(
    ("field", "unsafe_value", "error_pattern"),
    [
        ("ALLOW_MOCK_PLATFORM_ADAPTERS", True, "契约级 Mock"),
        ("AUTH_COOKIE_SECURE", False, "Secure 认证 Cookie"),
        ("JWT_SECRET_KEY", "x" * 31, "JWT_SECRET_KEY"),
        ("JWT_SECRET_KEY", "example-CHANGE-ME-secret-with-32-characters", "JWT_SECRET_KEY"),
        ("MINIO_SECRET_KEY", "x" * 15, "MINIO_SECRET_KEY"),
        ("MINIO_SECRET_KEY", "example-CHANGE-ME-secret", "MINIO_SECRET_KEY"),
        ("DATABASE_URL", "postgresql+asyncpg://crm:crm@postgres:5432/crm", "DATABASE_URL"),
        ("PUBLIC_BASE_URL", None, "PUBLIC_BASE_URL"),
        ("PUBLIC_BASE_URL", "", "PUBLIC_BASE_URL"),
        ("PUBLIC_BASE_URL", "http://staging.example.com", "PUBLIC_BASE_URL"),
        ("PUBLIC_BASE_URL", "https://user:secret@staging.example.com", "PUBLIC_BASE_URL"),
        ("PUBLIC_BASE_URL", "https://staging.example.com?next=other", "PUBLIC_BASE_URL"),
        ("PUBLIC_BASE_URL", "https://staging.example.com#other", "PUBLIC_BASE_URL"),
        ("CORS_ORIGINS", "", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "*", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "http://staging.example.com", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://user:secret@staging.example.com", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://staging.example.com/path", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://staging.example.com?next=other", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://staging.example.com#other", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://*.example.com", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://staging.example.com:invalid", "CORS_ORIGINS"),
        ("TIKTOK_EGRESS_IP", None, "TIKTOK_EGRESS_IP"),
        ("TIKTOK_EGRESS_IP", "invalid-ip", "TIKTOK_EGRESS_IP"),
    ],
)
def test_deployed_security_baseline_rejects_unsafe_configuration(
    app_env: str, field: str, unsafe_value: object, error_pattern: str
) -> None:
    """恢复 production-only guard 会让 staging 的每种不安全配置绕过启动门禁。"""
    callback = TIKTOK_OAUTH_STAGING_REDIRECT_URI if app_env == "staging" else TIKTOK_OAUTH_FIXED_REDIRECT_URI
    with pytest.raises(ValidationError, match=error_pattern):
        production_settings(APP_ENV=app_env, TIKTOK_OAUTH_REDIRECT_URI=callback, **{field: unsafe_value})


@pytest.mark.parametrize("app_env", ["development", "test", "integration"])
def test_deployed_security_baseline_preserves_local_fixture_configuration(app_env: str) -> None:
    """开发、测试、集成夹具不强制使用部署级基础凭证，但仍受独立真实能力门禁保护。"""
    settings = Settings(
        _env_file=None,
        APP_ENV=app_env,
        TIKTOK_OAUTH_REDIRECT_URI=TIKTOK_OAUTH_FIXED_REDIRECT_URI,
        ALLOW_MOCK_PLATFORM_ADAPTERS=True,
        AUTH_COOKIE_SECURE=False,
        JWT_SECRET_KEY="fixture",
        MINIO_SECRET_KEY="change-me",
        DATABASE_URL="postgresql+asyncpg://crm:crm@localhost:5432/crm",
        PUBLIC_BASE_URL="http://localhost:3000",
        CORS_ORIGINS="*",
        TIKTOK_EGRESS_IP=None,
    )
    assert settings.app_env == app_env
    assert settings.allow_mock_platform_adapters is True


def test_real_tiktok_read_and_webhook_can_start_with_complete_prerequisites() -> None:
    """REAL-FS-03 完成后，只读与 Webhook 可以独立于平台写能力启用。"""
    settings = production_settings(
        REAL_TIKTOK_READ_ENABLED=True,
        REAL_TIKTOK_WEBHOOK_ENABLED=True,
        TIKTOK_APP_KEY="real-app-key",
        TIKTOK_SERVICE_ID="real-service-id",
        TIKTOK_APP_SECRET="unit-test-app-secret",
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
        TIKTOK_REQUIRED_SCOPES=("seller.authorization.info,seller.order.info,seller.customer_service,seller.logistics"),
    )

    assert settings.real_tiktok_read_enabled is True
    assert settings.real_tiktok_webhook_enabled is True
    assert settings.real_tiktok_message_write_enabled is False


def test_real_tiktok_webhook_requires_read_capability() -> None:
    """Webhook 订单补全依赖只读 API，因此不能单独绕过只读门禁。"""
    with pytest.raises(ValidationError, match="Webhook 前必须先启用真实只读"):
        production_settings(REAL_TIKTOK_WEBHOOK_ENABLED=True)


def test_real_tiktok_manual_message_write_can_start_after_real_fs04() -> None:
    """普通消息写入满足前置条件后可以独立开启，自动回复仍保持关闭。"""
    settings = production_settings(
        REAL_TIKTOK_READ_ENABLED=True,
        REAL_TIKTOK_MESSAGE_WRITE_ENABLED=True,
        TIKTOK_APP_KEY="real-app-key",
        TIKTOK_SERVICE_ID="real-service-id",
        TIKTOK_APP_SECRET="unit-test-app-secret",
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
        TIKTOK_REQUIRED_SCOPES=("seller.authorization.info,seller.order.info,seller.customer_service,seller.logistics"),
    )

    assert settings.real_tiktok_message_write_enabled is True
    assert settings.auto_reply_enabled is False


def test_real_tiktok_manual_write_rejects_auto_reply() -> None:
    """REAL-FS-04 不得被自动回复 Worker 复用为公开自动发送。"""
    with pytest.raises(ValidationError, match="仅允许人工确认发送"):
        production_settings(
            REAL_TIKTOK_READ_ENABLED=True,
            REAL_TIKTOK_MESSAGE_WRITE_ENABLED=True,
            AUTO_REPLY_ENABLED=True,
            LLM_ENABLED=True,
            LLM_PRIMARY_MODEL="unit-test-model",
            OPENAI_API_KEY="unit-test-openai-key",
            TIKTOK_APP_KEY="real-app-key",
            TIKTOK_SERVICE_ID="real-service-id",
            TIKTOK_APP_SECRET="unit-test-app-secret",
            TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
        )


def test_real_tiktok_high_risk_write_remains_blocked() -> None:
    """发券、地址和营销写操作仍需后续独立灰度。"""
    with pytest.raises(ValidationError, match="高风险写入尚未完成"):
        production_settings(
            REAL_TIKTOK_READ_ENABLED=True,
            REAL_TIKTOK_MESSAGE_WRITE_ENABLED=True,
            REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=True,
            TIKTOK_APP_KEY="real-app-key",
            TIKTOK_SERVICE_ID="real-service-id",
            TIKTOK_APP_SECRET="unit-test-app-secret",
            TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
        )


def test_real_tiktok_read_rejects_missing_logistics_scope() -> None:
    """真实只读启动必须包含物流 Scope，避免授权成功后物流调用稳定 403。"""
    with pytest.raises(ValidationError, match="物流 Scope"):
        production_settings(
            REAL_TIKTOK_READ_ENABLED=True,
            TIKTOK_APP_KEY="real-app-key",
            TIKTOK_SERVICE_ID="real-service-id",
            TIKTOK_APP_SECRET="unit-test-app-secret",
            TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
            TIKTOK_REQUIRED_SCOPES="seller.authorization.info,seller.order.info,seller.customer_service",
        )


@pytest.mark.parametrize("app_env", ["integration", "staging", "production"])
@pytest.mark.parametrize(
    "unsafe_redirect_uri",
    [
        "http://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback",
        "https://attacker.example/v1/integrations/tiktok/oauth/callback",
        "https://www.hophorsefit.com/v1/integrations/tiktok/oauth/wrong",
        "https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback?next=unexpected",
        "https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback#fragment",
    ],
)
def test_real_environments_reject_oauth_redirect_configuration_drift(
    app_env: str,
    unsafe_redirect_uri: str,
) -> None:
    """真实环境必须在启动阶段拒绝非固定 HTTPS OAuth 回调。"""
    with pytest.raises(ValidationError, match="TIKTOK_OAUTH_REDIRECT_URI"):
        production_settings(
            APP_ENV=app_env,
            TIKTOK_OAUTH_REDIRECT_URI=unsafe_redirect_uri,
        )


@pytest.mark.parametrize(
    ("app_env", "redirect_uri"),
    [
        ("integration", TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI),
        ("staging", TIKTOK_OAUTH_STAGING_REDIRECT_URI),
        ("production", TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI),
    ],
)
def test_real_environments_accept_only_their_fixed_oauth_redirect_uri(
    app_env: str,
    redirect_uri: str,
) -> None:
    """集成、预发布和生产环境只接受各自固定的 OAuth 回调地址。"""
    settings = production_settings(
        APP_ENV=app_env,
        TIKTOK_OAUTH_REDIRECT_URI=redirect_uri,
    )
    assert settings.tiktok_oauth_redirect_uri == redirect_uri


def test_staging_oauth_redirect_uses_overselfx_domain_and_rejects_superseded_domain() -> None:
    """staging 域名切换后只能接受新回调，旧域名必须立即失败关闭。"""
    expected_redirect_uri = "https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback"
    assert TIKTOK_OAUTH_STAGING_REDIRECT_URI == expected_redirect_uri

    settings = production_settings(
        APP_ENV="staging",
        TIKTOK_OAUTH_REDIRECT_URI=expected_redirect_uri,
    )
    assert settings.tiktok_oauth_redirect_uri == expected_redirect_uri

    with pytest.raises(ValidationError, match="TIKTOK_OAUTH_REDIRECT_URI"):
        production_settings(
            APP_ENV="staging",
            TIKTOK_OAUTH_REDIRECT_URI="https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback",
        )


@pytest.mark.parametrize(
    ("app_env", "redirect_uri"),
    [
        ("integration", TIKTOK_OAUTH_STAGING_REDIRECT_URI),
        ("staging", TIKTOK_OAUTH_PRODUCTION_REDIRECT_URI),
        ("production", TIKTOK_OAUTH_STAGING_REDIRECT_URI),
    ],
)
def test_real_environments_reject_another_environments_oauth_redirect(
    app_env: str,
    redirect_uri: str,
) -> None:
    """真实环境拒绝其他环境的 OAuth 回调地址，避免凭据与回调错配。"""
    with pytest.raises(ValidationError, match="TIKTOK_OAUTH_REDIRECT_URI"):
        production_settings(
            APP_ENV=app_env,
            TIKTOK_OAUTH_REDIRECT_URI=redirect_uri,
        )


def test_tiktok_webhook_secret_is_hidden_from_settings_repr() -> None:
    """验证 TikTok Webhook 密钥不会在 Settings 调试输出中暴露。"""
    secret = "tiktok-webhook-secret-value"

    settings = Settings(TIKTOK_WEBHOOK_SECRET=secret)

    assert secret not in repr(settings)


def test_all_core_runtime_secrets_are_hidden_from_settings_repr() -> None:
    """配置对象意外进入异常日志时，不得展开核心运行密钥。"""
    sentinels = {
        "JWT_SECRET_KEY": "repr-jwt-secret-with-at-least-32-characters",
        "DATABASE_URL": "postgresql+asyncpg://crm:repr-database-password@postgres:5432/crm",
        "REDIS_URL": "redis://default:repr-redis-password@redis:6379/0",
        "MINIO_ACCESS_KEY": "repr-minio-access-key",
        "MINIO_SECRET_KEY": "repr-minio-secret-key",
        "SHOPEE_WEBHOOK_SECRET": "repr-shopee-secret",
        "AMAZON_WEBHOOK_SECRET": "repr-amazon-secret",
    }

    rendered = repr(Settings(_env_file=None, **sentinels))

    for value in sentinels.values():
        assert value not in rendered


def test_production_deepseek_requires_server_side_key() -> None:
    """启用 DeepSeek 时缺少服务端 Key 必须在启动阶段失败。"""
    with pytest.raises(ValidationError, match="DeepSeek"):
        production_settings(
            LLM_ENABLED=True,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="deepseek-chat",
            DEEPSEEK_API_KEY=None,
        )


def test_log_redaction_removes_credentials_and_customer_payloads() -> None:
    """日志出口必须脱敏 Bearer、JWT、密钥、地址和消息正文。"""
    raw = (
        "authorization=Bearer secret-token access_token=token-value "
        "content=customer-message address=customer-address "
        "jwt=eyJhbGciOiJIUzI1NiJ9.payload.signature"
    )
    redacted = redact_log_text(raw)
    assert "secret-token" not in redacted
    assert "token-value" not in redacted
    assert "customer-message" not in redacted
    assert "customer-address" not in redacted
    assert "eyJhbGci" not in redacted


def test_log_redaction_covers_real_secret_names_oauth_query_and_dsn_password() -> None:
    """集中日志出口必须覆盖真实命名、OAuth 查询参数和连接串密码。"""
    raw = (
        "app_secret=app-sentinel client_secret=client-sentinel "
        "tiktok_app_secret=tiktok-sentinel message=message-sentinel "
        "GET /callback?code=oauth-code-sentinel&auth_code=auth-code-sentinel&state=oauth-state-sentinel "
        "database_url=postgresql+asyncpg://crm:database-sentinel@postgres:5432/crm"
    )

    redacted = redact_log_text(raw)

    for sentinel in (
        "app-sentinel",
        "client-sentinel",
        "tiktok-sentinel",
        "message-sentinel",
        "oauth-code-sentinel",
        "auth-code-sentinel",
        "oauth-state-sentinel",
        "database-sentinel",
    ):
        assert sentinel not in redacted


def test_log_redaction_covers_prefixed_fields_and_unquoted_multiword_values() -> None:
    """业务前缀和未加引号的多词值不得绕过日志出口脱敏。"""
    sentinels = (
        "second-message-word",
        "third-message-word",
        "customer-message-sentinel",
        "shipping-address-sentinel",
        "minio-access-key-sentinel",
        "credential-encryption-key-sentinel",
    )
    raw = (
        "message=first-message-word second-message-word third-message-word; "
        '{"customer_message":"customer-message-sentinel",'
        '"shipping_address":"shipping-address-sentinel",'
        '"MINIO_ACCESS_KEY":"minio-access-key-sentinel",'
        '"TIKTOK_CREDENTIAL_ENCRYPTION_KEY":"credential-encryption-key-sentinel"}'
    )

    redacted = redact_log_text(raw)

    for sentinel in sentinels:
        assert sentinel not in redacted


def test_json_formatter_redacts_prefixed_fields_and_multiword_values() -> None:
    """最终 JSON Formatter 不能重新暴露变形字段或多词正文。"""
    sentinels = (
        "second-message-word",
        "customer-message-sentinel",
        "shipping-address-sentinel",
        "minio-access-key-sentinel",
        "credential-encryption-key-sentinel",
    )
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            "message=first-message-word second-message-word; "
            '{"customer_message":"customer-message-sentinel",'
            '"shipping_address":"shipping-address-sentinel",'
            '"minio_access_key":"minio-access-key-sentinel",'
            '"tiktok_credential_encryption_key":"credential-encryption-key-sentinel"}'
        ),
        args=(),
        exc_info=None,
    )

    rendered = JsonFormatter().format(record)

    for sentinel in sentinels:
        assert sentinel not in rendered


@pytest.mark.parametrize(
    ("raw", "sentinel"),
    [
        ("X-API-Key: colon-api-key-sentinel", "colon-api-key-sentinel"),
        ("TIKTOK_APP_SECRET: colon-platform-secret-sentinel", "colon-platform-secret-sentinel"),
    ],
)
def test_log_redaction_covers_unquoted_colon_credentials(raw: str, sentinel: str) -> None:
    """HTTP Header 和第三方诊断文本的未加引号冒号凭据必须在最终出口脱敏。"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=raw,
        args=(),
        exc_info=None,
    )

    assert sentinel not in redact_log_text(raw)
    assert sentinel not in JsonFormatter().format(record)


@pytest.mark.parametrize(
    "invalid_origin",
    [
        "https://user:password@example.com",
        "https://example.com/private",
        "https://example.com/?token=sentinel",
        "https://example.com/#fragment",
        "https://*.example.com",
        "http://example.com",
    ],
)
def test_production_rejects_non_origin_cors_values(invalid_origin: str) -> None:
    """生产 CORS 只接受 HTTPS scheme、主机和可选端口。"""
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        production_settings(CORS_ORIGINS=invalid_origin)


def test_production_accepts_explicit_https_origins_with_optional_port() -> None:
    """严格校验不能误拒绝多个合法 HTTPS Origin。"""
    settings = production_settings(CORS_ORIGINS="https://example.com,https://admin.example.com:8443")

    assert settings.cors_origin_list == ["https://example.com", "https://admin.example.com:8443"]


def test_production_compose_resets_dev_env_and_separates_secret_domains() -> None:
    """生产服务必须重置开发环境文件并按职责拆分平台与模型密钥。"""
    compose_text = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert compose_text.count("env_file: !reset []") == 5
    assert "x-production-platform: &production-platform" in compose_text
    assert "x-production-model: &production-model" in compose_text
    expected_merges = {
        "backend": "<<: [*production-runtime, *production-platform, *production-model]",
        "worker": "<<: [*production-runtime, *production-platform]",
        "jobs": "<<: [*production-runtime, *production-platform, *production-model]",
        "agent-worker": "<<: [*production-runtime, *production-model]",
    }
    for service_name, expected_merge in expected_merges.items():
        assert expected_merge in compose_service_block(compose_text, service_name)
    required_redirect_config = "".join(
        [
            "TIKTOK_OAUTH_REDIRECT_URI: ${TIKTOK_OAUTH_REDIRECT_URI:",
            "?TIKTOK_OAUTH_REDIRECT_URI is required}",
        ]
    )
    assert required_redirect_config in compose_text


def test_production_compose_enforces_least_secret_service_matrix() -> None:
    """防止公共锚点和本地检索服务再次跨域持有平台或模型凭据。"""
    compose_text = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    runtime_block = compose_text.split("x-production-platform: &production-platform", 1)[0]
    retrieval_block = compose_service_block(compose_text, "retrieval-model-service")

    assert "TIKTOK_EGRESS_IP" in runtime_block
    assert "TIKTOK_APP_SECRET" not in runtime_block
    assert "DEEPSEEK_API_KEY" not in runtime_block
    assert "env_file: !reset []" in retrieval_block
    assert "production-runtime" not in retrieval_block
    assert "production-platform" not in retrieval_block
    assert "production-model" not in retrieval_block


@pytest.mark.parametrize(
    "service_name",
    ["backend", "worker", "jobs", "agent-worker", "retrieval-model-service"],
)
def test_development_compose_keeps_live_evaluation_out_of_long_lived_services(service_name: str) -> None:
    """一次性真实模型评测开关不得从根环境文件污染常驻服务或迁移进程。"""
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    service_lines = compose_service_block(compose_text, service_name).splitlines()

    assert any(line.strip() == 'LLM_LIVE_EVAL: "false"' for line in service_lines)


def test_tiktok_manual_overlay_limits_real_write_to_backend() -> None:
    """真实普通消息开关只能进入人工 HTTP 服务，Worker 保持写入关闭。"""
    overlay = (PROJECT_ROOT / "docker-compose.tiktok-manual.yml").read_text(encoding="utf-8")
    backend = compose_service_block(overlay, "backend")
    worker = compose_service_block(overlay, "worker")

    assert "REAL_TIKTOK_MESSAGE_WRITE_ENABLED: ${REAL_TIKTOK_MESSAGE_WRITE_ENABLED:-false}" in backend
    assert 'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED: "false"' in backend
    assert 'AUTO_REPLY_ENABLED: "false"' in backend
    assert 'REAL_TIKTOK_MESSAGE_WRITE_ENABLED: "false"' in worker
    assert 'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED: "false"' in worker


def test_rootless_staging_overlay_is_loopback_only_and_fail_closed() -> None:
    """预发布覆盖层必须限制代理到回环地址并集中关闭真实能力。"""
    overlay = (PROJECT_ROOT / "docker-compose.rootless-staging.yml").read_text(encoding="utf-8")

    assert "x-rootless-staging-runtime: &rootless-staging-runtime" in overlay
    assert 'APP_ENV: "staging"' in overlay.split("services:", 1)[0]
    for name in (
        "REAL_TIKTOK_READ_ENABLED",
        "REAL_TIKTOK_WEBHOOK_ENABLED",
        "REAL_TIKTOK_MESSAGE_WRITE_ENABLED",
        "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED",
        "LLM_ENABLED",
        "LLM_LIVE_EVAL",
        "AI_TRANSLATION_ENABLED",
        "AI_MARKETING_ENABLED",
        "AUTO_REPLY_ENABLED",
        "ALLOW_MOCK_PLATFORM_ADAPTERS",
    ):
        assert f'{name}: "false"' in overlay.split("services:", 1)[0]

    for service_name in ("backend", "worker", "jobs", "agent-worker"):
        service_block = compose_service_block(overlay, service_name)
        assert "<<: *rootless-staging-runtime" in service_block
        assert 'APP_ENV: "staging"' not in service_block

    assert '"127.0.0.1:10080:80"' in overlay
    assert '"127.0.0.1:10443:443"' in overlay
    assert '"0.0.0.0:10080:80"' not in overlay
    assert '"0.0.0.0:10443:443"' not in overlay


def test_nginx_access_log_format_excludes_query_string() -> None:
    """代理日志不得在正常或上游错误路径记录 OAuth 查询参数。"""
    nginx_text = (PROJECT_ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")

    assert "access_log /dev/stdout safe_json;" in nginx_text
    assert '"uri":"$uri"' in nginx_text
    assert '"request":"$request"' not in nginx_text
    assert '"request_uri":"$request_uri"' not in nginx_text
    assert "location = /v1/integrations/tiktok/oauth/callback" in nginx_text
    assert "error_log /dev/null;" in nginx_text


def test_json_formatter_drops_unstructured_sensitive_message() -> None:
    """结构化日志必须丢弃任意自由文本，不能只依赖有限字段名脱敏。"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='{"deepseek_api_key":"secret-value","content":"private-message"}',
        args=(),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "unstructured_log_redacted"
    assert payload["message"] == "unstructured_log_redacted"
    assert "secret-value" not in json.dumps(payload)
    assert "private-message" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("logger_name", "expected_event"),
    [
        ("httpx", "http_client_request"),
        ("httpcore.http11", "http_client_transport"),
        ("uvicorn.access", "http_server_access"),
        ("uvicorn.error", "http_server_runtime"),
        ("sqlalchemy.engine.Engine", "database_engine_event"),
        ("alembic.runtime.migration", "database_migration_event"),
    ],
)
def test_json_formatter_maps_known_framework_loggers_without_exposing_message(
    logger_name: str,
    expected_event: str,
) -> None:
    """已知框架日志应保留稳定事件语义，同时继续丢弃不可信自由文本。"""
    sentinel = "customer-message-and-access-token-sentinel"
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"request failed: {sentinel}",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))
    rendered = json.dumps(payload)

    assert payload["event"] == expected_event
    assert payload["message"] == expected_event
    assert sentinel not in rendered


def test_alembic_offline_command_uses_unified_json_logging() -> None:
    """Alembic 真实入口在 ``fileConfig`` 后仍必须输出统一低敏 JSON。"""
    backend_root = PROJECT_ROOT / "backend"
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "base", "--sql"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    log_lines = [line for line in completed.stderr.splitlines() if line.strip()]
    assert log_lines
    payloads = [json.loads(line) for line in log_lines]
    assert {payload["event"] for payload in payloads} == {"database_migration_event"}
    assert all(payload["message"] == "database_migration_event" for payload in payloads)


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    [
        ("trace_id", "客户要求寄到北京市朝阳区建国路88号"),
        ("trace_id", "x" * 101),
        ("trace_id", "trace-ok\nforged-log-line"),
    ],
)
def test_json_formatter_rejects_untrusted_identifier_text(field_name: str, unsafe_value: str) -> None:
    """日志标识只接受有限 ASCII 元数据，正文、超长值和控制字符必须失败关闭。"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="deepseek_call_succeeded",
        args=(),
        exc_info=None,
    )
    record.event = "deepseek_call_succeeded"
    record.trace_id = "00000000-0000-4000-8000-000000000000"
    setattr(record, field_name, unsafe_value)

    payload = json.loads(JsonFormatter().format(record))
    rendered = json.dumps(payload, ensure_ascii=False)

    assert unsafe_value not in rendered
    assert payload[field_name] == "[INVALID_LOG_METADATA]"


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "private-customer-message",
        "350-Fifth-Avenue-Apt-12B",
        "sk-1234567890abcdef",
    ],
)
def test_json_formatter_hashes_untrusted_provider_request_id(unsafe_value: str) -> None:
    """供应商请求 ID 是外部输入，只能以不可逆摘要进入生产日志。"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="deepseek_call_succeeded",
        args=(),
        exc_info=None,
    )
    record.event = "deepseek_call_succeeded"
    record.trace_id = "00000000-0000-4000-8000-000000000000"
    record.provider_request_id = unsafe_value

    payload = json.loads(JsonFormatter().format(record))
    expected_digest = hashlib.sha256(unsafe_value.encode("utf-8")).hexdigest()

    assert unsafe_value not in json.dumps(payload)
    assert payload["provider_request_id"] == f"sha256:{expected_digest}"


@pytest.mark.parametrize(
    "unsafe_trace_id",
    [
        "trace-safe-looking",
        "00000000000040008000000000000000",
        "{00000000-0000-4000-8000-000000000000}",
    ],
)
def test_json_formatter_accepts_only_canonical_uuid_trace_id(unsafe_trace_id: str) -> None:
    """最终日志出口不接受看似安全但非 UUID 的追踪字符串。"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.event = "request_completed"
    record.trace_id = unsafe_trace_id

    payload = json.loads(JsonFormatter().format(record))

    assert payload["trace_id"] == "[INVALID_LOG_METADATA]"


@pytest.mark.parametrize(
    ("relative_path", "forbidden_trace_source"),
    [
        ("backend/app/main.py", '"trace_id": "startup"'),
        ("backend/app/main.py", '"trace_id": "shutdown"'),
        ("backend/app/main.py", '"trace_id": "validation"'),
        ("backend/app/integrations/service.py", 'trace_id=f"webhook-{event.id}"'),
        ("backend/app/integrations/worker.py", '"trace_id": "worker"'),
        ("backend/app/jobs/worker.py", '"trace_id": "jobs-worker"'),
        ("backend/app/chat/worker.py", '"trace_id": "agent-worker"'),
        ("backend/app/marketing/worker.py", 'trace_id=f"marketing:{event.id}"'),
        ("backend/scripts/evaluate_intents.py", 'trace_id=f"live-eval-{case.case_id}"'),
    ],
)
def test_internal_trace_producers_do_not_emit_legacy_non_uuid_values(
    relative_path: str,
    forbidden_trace_source: str,
) -> None:
    """内部生产路径必须生成 UUID Trace ID，业务语义由 event 等字段承载。"""
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    assert forbidden_trace_source not in source
