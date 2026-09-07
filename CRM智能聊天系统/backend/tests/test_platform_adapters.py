"""平台契约适配器和统一事件类型测试。"""

import hashlib
import hmac

import pytest
from pydantic import ValidationError

from app.integrations import adapters
from app.integrations.adapters import MockHmacAdapter, TikTokAdapter
from app.integrations.schemas import MessageCreatedEvent
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError


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
