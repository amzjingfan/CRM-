"""TikTok Shop 人工确认普通消息写契约测试。"""

import json
import uuid
from typing import Any

import httpx
import pytest

from app.integrations.credential_crypto import encrypt_credential
from app.integrations.schemas import SendMessageCommand
from app.integrations.tiktok_oauth import generate_api_signature
from app.integrations.tiktok_write import SEND_MESSAGE_PATH_TEMPLATE, TikTokMessageClient
from app.shared.config.settings import Settings
from app.stores.models import ChannelAccount


def real_write_settings(**overrides: Any) -> Settings:
    """构造只包含测试密文的 REAL-FS-04 配置。"""
    values: dict[str, Any] = {
        "APP_ENV": "development",
        "REAL_TIKTOK_READ_ENABLED": True,
        "REAL_TIKTOK_MESSAGE_WRITE_ENABLED": True,
        "TIKTOK_APP_KEY": "unit-test-app-key",
        "TIKTOK_SERVICE_ID": "unit-test-service-id",
        "TIKTOK_APP_SECRET": "unit-test-app-secret-value",
        "TIKTOK_OAUTH_REDIRECT_URI": "https://example.com/v1/integrations/tiktok/oauth/callback",
        "TIKTOK_CREDENTIAL_ENCRYPTION_KEY": "unit-test-encryption-key-with-at-least-32-characters",
        "TIKTOK_EGRESS_IP": "203.0.113.10",
        "TIKTOK_REQUIRED_SCOPES": (
            "seller.authorization.info,seller.order.info,seller.customer_service,seller.logistics"
        ),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def connected_channel() -> ChannelAccount:
    """创建与店铺上下文绑定的加密渠道测试对象。"""
    store_id = uuid.uuid4()
    external_store_id = "7494049642642441621"
    key = "unit-test-encryption-key-with-at-least-32-characters"
    return ChannelAccount(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_store_id=external_store_id,
        display_name="TikTok Shop One",
        access_token_ref=encrypt_credential(
            "unit-test-access-token",
            key,
            f"tiktok:{store_id}:{external_store_id}:access",
        ),
        status="connected",
        scopes=["seller.customer_service"],
        metadata_json={"shop_cipher": "ROW_unit_test_shop_cipher"},
    )


def command(**overrides: object) -> SendMessageCommand:
    """构造已确认的普通文本消息。"""
    values: dict[str, object] = {
        "external_conversation_id": "710688832392260838",
        "content": "Where is my order?",
        "idempotency_key": str(uuid.uuid4()),
        "human_confirmed": True,
    }
    values.update(overrides)
    return SendMessageCommand.model_validate(values)


@pytest.mark.asyncio
async def test_send_message_uses_official_202309_body_signature_and_token_header() -> None:
    """真实发送必须使用官方路径、双层 JSON 正文和实时签名。"""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.url.path == SEND_MESSAGE_PATH_TEMPLATE.format(conversation_id="710688832392260838")
        assert request.headers["x-tts-access-token"] == "unit-test-access-token"
        body_bytes = request.content
        body = json.loads(body_bytes)
        assert body == {"type": "TEXT", "content": '{"content":"Where is my order?"}'}
        params = dict(request.url.params)
        supplied_signature = params.pop("sign")
        expected_signature = generate_api_signature(
            request.url.path,
            {key: int(value) if key == "timestamp" else value for key, value in params.items()},
            "unit-test-app-secret-value",
            body_bytes,
        )
        assert supplied_signature == expected_signature
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "722323407926368819"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await TikTokMessageClient(real_write_settings(), connected_channel(), http_client).send_text_message(
            command()
        )

    assert attempts == 1
    assert result.status == "sent"
    assert result.external_message_id == "722323407926368819"
    assert result.mock is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_kind",
    ["timeout", "server", "malformed", "missing-message-id", "internal", "customer-service-internal"],
)
async def test_uncertain_platform_results_are_unknown_and_never_retried(failure_kind: str) -> None:
    """可能已经产生副作用的异常只能记 unknown，且始终只调用一次。"""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if failure_kind == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if failure_kind == "server":
            return httpx.Response(503, request=request)
        if failure_kind == "malformed":
            return httpx.Response(200, text="not-json", request=request)
        if failure_kind == "missing-message-id":
            return httpx.Response(200, json={"code": 0, "data": {}}, request=request)
        error_code = 45101001 if failure_kind == "customer-service-internal" else 36009003
        return httpx.Response(200, json={"code": error_code, "request_id": "request-1"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await TikTokMessageClient(real_write_settings(), connected_channel(), http_client).send_text_message(
            command()
        )

    assert attempts == 1
    assert result.status == "unknown"
    assert result.error_code == "TIKTOK_MESSAGE_RESULT_UNKNOWN"
    assert result.external_message_id is None


@pytest.mark.asyncio
async def test_human_confirmation_is_required_before_any_http_request() -> None:
    """缺少可信人工确认时必须在网络调用前失败关闭。"""
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "1"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await TikTokMessageClient(real_write_settings(), connected_channel(), http_client).send_text_message(
            command(human_confirmed=False)
        )

    assert attempts == 0
    assert result.status == "failed"
    assert result.error_code == "REAL_WRITE_REQUIRES_HUMAN_CONFIRMATION"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (httpx.Response(429), "TIKTOK_RATE_LIMITED"),
        (httpx.Response(403), "TIKTOK_PERMISSION_DENIED"),
        (httpx.Response(200, json={"code": 105002}), "TIKTOK_TOKEN_EXPIRED"),
        (httpx.Response(200, json={"code": 123456}), "TIKTOK_MESSAGE_REJECTED"),
    ],
)
async def test_definite_rejections_are_failed_without_retry(
    response: httpx.Response,
    expected_error: str,
) -> None:
    """明确未成功的限流、权限和业务错误允许记录为 failed。"""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        response.request = request
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await TikTokMessageClient(real_write_settings(), connected_channel(), http_client).send_text_message(
            command()
        )

    assert attempts == 1
    assert result.status == "failed"
    assert result.error_code == expected_error
