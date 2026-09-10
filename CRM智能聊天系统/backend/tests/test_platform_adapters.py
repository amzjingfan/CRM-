"""平台契约适配器和统一事件类型测试。"""

import hashlib
import hmac

import pytest
from pydantic import ValidationError

from app.integrations import adapters
from app.integrations.adapters import MockHmacAdapter, TikTokAdapter
from app.integrations.schemas import MessageCreatedEvent, SendMessageCommand
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount


def adapter_settings(app_env: str, *, allow_mock: bool) -> Settings:
    """使用真实 Settings 和虚构安全凭据，避免启动校验掩盖适配器门禁。"""
    host = "staging.overselfx.com" if app_env == "staging" else "www.hophorsefit.com"
    return Settings(
        _env_file=None,
        APP_ENV=app_env,
        ALLOW_MOCK_PLATFORM_ADAPTERS=allow_mock,
        AUTH_COOKIE_SECURE=True,
        JWT_SECRET_KEY="unit-test-jwt-secret-with-at-least-32-characters",
        MINIO_SECRET_KEY="unit-test-minio-secret",
        DATABASE_URL="postgresql+asyncpg://crm:unit-test-password@localhost:5432/crm",
        PUBLIC_BASE_URL=f"https://{host}",
        CORS_ORIGINS=f"https://{host}",
        TIKTOK_EGRESS_IP="203.0.113.10",
        TIKTOK_OAUTH_REDIRECT_URI=f"https://{host}/v1/integrations/tiktok/oauth/callback",
        REAL_TIKTOK_WEBHOOK_ENABLED=False,
        REAL_TIKTOK_MESSAGE_WRITE_ENABLED=False,
    )


@pytest.mark.parametrize("app_env", ["development", "test", "integration", "staging", "production"])
@pytest.mark.parametrize("platform", ["tiktok", "shopee", "amazon"])
@pytest.mark.parametrize("resolver_name", ["get_platform_adapter", "get_message_adapter"])
def test_disabled_mock_resolvers_fail_closed_in_every_environment(
    monkeypatch: pytest.MonkeyPatch, app_env: str, platform: str, resolver_name: str
) -> None:
    """将任何 resolver 恢复为 production-only 会误解析未启用的 Mock 能力。"""
    settings = adapter_settings(app_env, allow_mock=False)
    monkeypatch.setattr(adapters, "get_settings", lambda: settings)
    with pytest.raises(AppError) as error:
        getattr(adapters, resolver_name)(platform)
    assert error.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert error.value.status_code == 503


@pytest.mark.parametrize("webhook_enabled", [True, False])
def test_tiktok_real_capabilities_resolve_independently_when_mock_disabled(
    monkeypatch: pytest.MonkeyPatch, webhook_enabled: bool
) -> None:
    """误用另一个真实能力开关会造成错误授权或拒绝，两个 resolver 必须交叉隔离。"""
    settings = Settings(
        _env_file=None,
        APP_ENV="staging",
        ALLOW_MOCK_PLATFORM_ADAPTERS=False,
        AUTH_COOKIE_SECURE=True,
        JWT_SECRET_KEY="unit-test-jwt-secret-with-at-least-32-characters",
        MINIO_SECRET_KEY="unit-test-minio-secret",
        DATABASE_URL="postgresql+asyncpg://crm:unit-test-password@localhost:5432/crm",
        PUBLIC_BASE_URL="https://staging.overselfx.com",
        CORS_ORIGINS="https://staging.overselfx.com",
        TIKTOK_EGRESS_IP="203.0.113.10",
        TIKTOK_OAUTH_REDIRECT_URI="https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback",
        REAL_TIKTOK_READ_ENABLED=True,
        REAL_TIKTOK_WEBHOOK_ENABLED=webhook_enabled,
        REAL_TIKTOK_MESSAGE_WRITE_ENABLED=not webhook_enabled,
        TIKTOK_APP_KEY="unit-test-real-app",
        TIKTOK_SERVICE_ID="unit-test-service",
        TIKTOK_APP_SECRET="unit-test-app-secret",
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-32-characters",
    )
    monkeypatch.setattr(adapters, "get_settings", lambda: settings)
    enabled_resolver = adapters.get_platform_adapter if webhook_enabled else adapters.get_message_adapter
    disabled_resolver = adapters.get_message_adapter if webhook_enabled else adapters.get_platform_adapter

    assert isinstance(enabled_resolver("tiktok"), TikTokAdapter)
    with pytest.raises(AppError) as error:
        disabled_resolver("tiktok")
    assert error.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert error.value.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["development", "test", "integration", "staging", "production"])
@pytest.mark.parametrize("platform", ["tiktok", "shopee", "amazon"])
async def test_disabled_mock_send_fails_closed_in_every_environment(
    monkeypatch: pytest.MonkeyPatch, app_env: str, platform: str
) -> None:
    """直接调用适配器也不能越过显式关闭开关返回 synthetic sent。"""
    settings = adapter_settings(app_env, allow_mock=False)
    monkeypatch.setattr(adapters, "get_settings", lambda: settings)
    adapter = TikTokAdapter(settings) if platform == "tiktok" else MockHmacAdapter(platform, "fixture")
    result = await adapter.send_message(
        ChannelAccount(status="connected"),
        SendMessageCommand(external_conversation_id="fixture", content="fixture", idempotency_key="fixture"),
    )
    assert result.status == "failed"
    assert result.error_code == "MOCK_ADAPTER_DISABLED"


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["development", "test"])
@pytest.mark.parametrize("platform", ["tiktok", "shopee", "amazon"])
async def test_enabled_mock_contract_remains_available(
    monkeypatch: pytest.MonkeyPatch, app_env: str, platform: str
) -> None:
    """开发和测试显式开启时继续提供带 mock 标识的签名与发送契约。"""
    settings = adapter_settings(app_env, allow_mock=True)
    monkeypatch.setattr(adapters, "get_settings", lambda: settings)
    webhook_adapter = adapters.get_platform_adapter(platform)
    body = b"{}"
    if platform == "tiktok":
        signature = hmac.new(
            settings.tiktok_webhook_secret.get_secret_value().encode(),
            settings.tiktok_app_key.encode() + body,
            hashlib.sha256,
        ).hexdigest()
        headers = {"x-tts-signature": signature}
    else:
        secret = settings.shopee_webhook_secret if platform == "shopee" else settings.amazon_webhook_secret
        headers = {"x-mock-signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}
    assert webhook_adapter.verify_webhook(body, headers) is True
    result = await adapters.get_message_adapter(platform).send_message(
        ChannelAccount(status="connected"),
        SendMessageCommand(external_conversation_id="fixture", content="fixture", idempotency_key="fixture"),
    )
    assert result.status == "sent"
    assert result.mock is True
    assert result.error_code is None


def test_tiktok_hmac_signature_uses_raw_body() -> None:
    """TikTok 签名必须基于未经重新序列化的原始请求体。"""
    body = b'{"event_id":"evt-1"}'
    settings = Settings(TIKTOK_APP_KEY="app-key", TIKTOK_WEBHOOK_SECRET="secret")
    signature = hmac.new(b"secret", b"app-key" + body, hashlib.sha256).hexdigest()
    assert TikTokAdapter(settings).verify_webhook(body, {"x-tts-signature": signature}) is True
    assert TikTokAdapter(settings).verify_webhook(body + b" ", {"x-tts-signature": signature}) is False


def test_mock_adapter_rejects_invalid_signature() -> None:
    """Mock 平台同样不能跳过签名验证。"""
    assert MockHmacAdapter("shopee", "secret").verify_webhook(b"{}", {"x-mock-signature": "invalid"}) is False


def test_tiktok_adapter_fails_closed_when_real_and_mock_webhooks_are_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未启用真实 Webhook 或 Mock 时不得静默接受 TikTok 请求。"""
    settings = Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-secret-key-with-32-characters",
        REAL_TIKTOK_WEBHOOK_ENABLED="false",
        ALLOW_MOCK_PLATFORM_ADAPTERS="false",
    )
    monkeypatch.setattr(adapters, "get_settings", lambda: settings)

    with pytest.raises(AppError, match="均未启用"):
        adapters.get_platform_adapter("tiktok")


def test_message_event_validation_rejects_oversized_content() -> None:
    """第三方消息在进入业务层前限制为最多 4000 字符。"""
    adapter = MockHmacAdapter("amazon", "secret")
    with pytest.raises(ValidationError):
        adapter.normalize_event(
            {
                "event_type": "message.created",
                "event_id": "evt-1",
                "external_store_id": "store-1",
                "external_conversation_id": "conversation-1",
                "external_message_id": "message-1",
                "customer": {"external_id": "customer-1"},
                "content": "x" * 4001,
                "created_at": "2026-08-19T10:00:00Z",
            }
        )


def test_message_event_normalizes_to_discriminated_type() -> None:
    """message.created 必须解析为明确类型。"""
    event = MockHmacAdapter("amazon", "secret").normalize_event(
        {
            "event_type": "message.created",
            "event_id": "evt-1",
            "external_store_id": "store-1",
            "external_conversation_id": "conversation-1",
            "external_message_id": "message-1",
            "customer": {"external_id": "customer-1", "name": "Customer"},
            "content": "Where is my order?",
            "created_at": "2026-08-19T10:00:00Z",
        }
    )
    assert isinstance(event, MessageCreatedEvent)
    assert event.customer.external_id == "customer-1"
