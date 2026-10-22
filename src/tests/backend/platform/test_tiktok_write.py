"""TikTok Shop 人工确认普通消息写契约测试。"""

import json
import uuid
from typing import Any

import httpx
import pytest

import app.integrations.tiktok_write as tiktok_write_module
from app.integrations.credential_crypto import encrypt_credential
from app.integrations.schemas import SendMessageCommand
from app.integrations.tiktok_oauth import generate_api_signature
from app.integrations.tiktok_write import SEND_MESSAGE_PATH_TEMPLATE, TikTokMessageClient
from app.shared.config.settings import Settings
from app.stores.models import ChannelAccount
from app.tools.contracts import validate_tool_arguments


def real_write_settings(**overrides: Any) -> Settings:
    """构造只包含测试密文的 REAL-FS-04 配置。"""
    values: dict[str, Any] = {
        "APP_ENV": "development",
        "REAL_TIKTOK_READ_ENABLED": True,
        "REAL_TIKTOK_MESSAGE_WRITE_ENABLED": True,
        "TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID": "710688832392260838",
        "TIKTOK_APP_KEY": "unit-test-app-key",
        "TIKTOK_SERVICE_ID": "unit-test-service-id",
        "TIKTOK_APP_SECRET": "unit-test-app-secret-value",
        "TIKTOK_OAUTH_REDIRECT_URI": "https://example.com/v1/integrations/tiktok/oauth/callback",
        "TIKTOK_CREDENTIAL_ENCRYPTION_KEY": "unit-test-encryption-key-with-at-least-32-characters",
        "TIKTOK_EGRESS_IP": "203.0.113.10",
        "TIKTOK_EGRESS_PROXY_URL": "socks5h://127.0.0.1:1080",
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


def test_text_send_arguments_keep_existing_idempotency_shape() -> None:
    assert validate_tool_arguments(
        "send_platform_message",
        {
            "conversation_id": str(uuid.uuid4()),
            "content": "hello",
        },
    ).keys() == {"conversation_id", "content"}


@pytest.mark.asyncio
async def test_send_message_uses_official_202606_body_signature_and_token_header() -> None:
    """真实发送必须使用官方路径、双层 JSON 正文和实时签名。"""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.url.path == SEND_MESSAGE_PATH_TEMPLATE.format(conversation_id="710688832392260838")
        assert request.headers["x-tts-access-token"] == "unit-test-access-token"
        body_bytes = request.content
        body = json.loads(body_bytes)
        assert body == {
            "type": "TEXT",
            "content": '{"content":"Where is my order?"}',
            "sender_role": "CUSTOMER_SERVICE",
        }
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
async def test_send_logistics_card_uses_official_message_type_and_identifiers() -> None:
    """物流卡片必须由平台原生类型发送，不能退化为长文本。"""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body == {
            "type": "LOGISTICS_CARD",
            "content": '{"order_id":"580874485811283206","package_id":"123456"}',
            "sender_role": "CUSTOMER_SERVICE",
        }
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "722323407926368819"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await TikTokMessageClient(real_write_settings(), connected_channel(), http_client).send_text_message(
            command(message_type="logistics_card", card_order_id="580874485811283206", card_package_id="123456")
        )
    assert result.status == "sent"


@pytest.mark.asyncio
async def test_staging_allowlisted_conversation_is_the_only_real_send_target() -> None:
    """受控窗口的其他会话在 HTTP 请求产生前被拒绝。"""
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "722323407926368819"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = TikTokMessageClient(
            real_write_settings(TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID="710688832392260838"),
            connected_channel(),
            http_client,
        )
        result = await client.send_text_message(command(external_conversation_id="710688832392260839"))

    assert attempts == 0
    assert result.status == "failed"
    assert result.error_code == "TIKTOK_CONVERSATION_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_store_allowlist_sends_two_conversations_but_never_another_store() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"code": 0, "data": {"message_id": str(722323407926368819 + attempts)}})

    channel = connected_channel()
    settings = real_write_settings(
        TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID=None,
        TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS=str(channel.store_id),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = TikTokMessageClient(settings, channel, http_client)
        first = await client.send_text_message(command())
        second = await client.send_text_message(command(external_conversation_id="710688832392260839"))
        other_channel = connected_channel()
        blocked = await TikTokMessageClient(settings, other_channel, http_client).send_text_message(command())

    assert (first.status, second.status, blocked.status) == ("sent", "sent", "failed")
    assert blocked.error_code == "TIKTOK_CONVERSATION_NOT_ALLOWED"
    assert attempts == 2


@pytest.mark.asyncio
async def test_write_default_client_uses_fixed_egress_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认人工消息发送必须经固定出口工厂且只构造一次客户端。"""
    settings = real_write_settings()
    factory_calls: list[Settings] = []
    async_client_type = httpx.AsyncClient

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "722323407926368819"}})

    def fake_factory(candidate: Settings) -> httpx.AsyncClient:
        factory_calls.append(candidate)
        return async_client_type(transport=httpx.MockTransport(handler))

    def reject_direct_client(**_kwargs: object) -> httpx.AsyncClient:
        raise AssertionError("write client bypassed the fixed-egress factory")

    monkeypatch.setattr(tiktok_write_module, "create_tiktok_http_client", fake_factory, raising=False)
    monkeypatch.setattr(tiktok_write_module.httpx, "AsyncClient", reject_direct_client)

    result = await TikTokMessageClient(settings, connected_channel()).send_text_message(command())

    assert result.status == "sent"
    assert result.external_message_id == "722323407926368819"
    assert factory_calls == [settings]


@pytest.mark.asyncio
async def test_write_factory_failure_is_unknown_without_direct_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """固定出口连接失败可能已到达平台边界，只能 unknown 且不得直连重试。"""
    settings = real_write_settings()
    factory_calls: list[Settings] = []
    direct_constructions = 0
    async_client_type = httpx.AsyncClient

    def failing_factory(candidate: Settings) -> httpx.AsyncClient:
        factory_calls.append(candidate)
        request = httpx.Request("POST", "https://open-api.tiktokglobalshop.com")
        raise httpx.ConnectError("fixed egress unavailable", request=request)

    def direct_client(**_kwargs: object) -> httpx.AsyncClient:
        nonlocal direct_constructions
        direct_constructions += 1
        return async_client_type(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={"code": 0, "data": {"message_id": "722323407926368819"}},
                )
            )
        )

    monkeypatch.setattr(tiktok_write_module, "create_tiktok_http_client", failing_factory, raising=False)
    monkeypatch.setattr(tiktok_write_module.httpx, "AsyncClient", direct_client)

    result = await TikTokMessageClient(settings, connected_channel()).send_text_message(command())

    assert result.status == "unknown"
    assert result.error_code == "TIKTOK_MESSAGE_RESULT_UNKNOWN"
    assert factory_calls == [settings]
    assert direct_constructions == 0


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
