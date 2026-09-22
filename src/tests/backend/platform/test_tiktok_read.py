"""REAL-FS-03 TikTok 真实只读 API 与官方 Webhook 契约测试。"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

import app.integrations.adapters as adapters_module
import app.integrations.service as integration_service
import app.integrations.tiktok_read as tiktok_read_module
from app.audit.models import AuditLog
from app.integrations.adapters import TikTokAdapter
from app.integrations.credential_crypto import encrypt_credential
from app.integrations.models import WebhookEvent
from app.integrations.schemas import MessageCreatedEvent, OrderUpdatedEvent, TikTokAuthorizationLifecycleEvent
from app.integrations.service import stable_event_id, webhook_event_type, webhook_external_store_id
from app.integrations.tiktok_oauth import generate_api_signature
from app.integrations.tiktok_read import TikTokOrder, TikTokReadClient
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount


def real_settings(**overrides: Any) -> Settings:
    """构造不包含真实凭证的 REAL-FS-03 测试配置。"""
    values: dict[str, Any] = {
        "APP_ENV": "development",
        "REAL_TIKTOK_READ_ENABLED": True,
        "REAL_TIKTOK_WEBHOOK_ENABLED": True,
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
    """创建带上下文绑定密文和官方 shop_cipher 的渠道对象。"""
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
        scopes=[
            "seller.authorization.info",
            "seller.order.info",
            "seller.customer_service",
            "seller.logistics",
        ],
        metadata_json={"shop_cipher": "ROW_unit_test_shop_cipher"},
    )


def test_real_webhook_signature_uses_authorization_app_secret_and_raw_body() -> None:
    """真实模式只接受官方 Authorization HMAC，不接受旧 Mock Header。"""
    body = b'{"type":14,"tts_notification_id":"event-1"}'
    settings = real_settings()
    signature = hmac.new(
        b"unit-test-app-secret-value",
        b"unit-test-app-key" + body,
        hashlib.sha256,
    ).hexdigest()
    adapter = TikTokAdapter(settings)

    assert adapter.verify_webhook(body, {"authorization": signature}) is True
    assert adapter.verify_webhook(body + b" ", {"authorization": signature}) is False
    assert adapter.verify_webhook(body, {"x-tts-signature": signature}) is False


@pytest.mark.asyncio
async def test_order_detail_uses_202507_signed_get_and_encrypted_channel_token() -> None:
    """订单详情必须使用当前 202507 端点、逗号 ID 和 Token Header。"""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("x-tts-access-token")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "Success",
                "request_id": "platform-request-id",
                "data": {
                    "orders": [
                        {
                            "id": "576461413038785752",
                            "user_id": "7021436810468230477",
                            "status": "UNPAID",
                            "create_time": 1718305585,
                            "payment": {"currency": "USD", "total_amount": "12.50"},
                            "line_items": [
                                {
                                    "id": "577086512123755123",
                                    "product_name": "Product",
                                    "seller_sku": "SKU-1",
                                    "currency": "USD",
                                    "sale_price": "12.50",
                                }
                            ],
                        }
                    ]
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        orders, request_id = await TikTokReadClient(
            real_settings(), connected_channel(), http_client
        ).get_order_details(["576461413038785752"])

    query = parse_qs(urlparse(seen["url"]).query)
    assert urlparse(seen["url"]).path == "/order/202507/orders"
    assert query["ids"] == ["576461413038785752"]
    assert query["shop_cipher"] == ["ROW_unit_test_shop_cipher"]
    assert len(query["sign"][0]) == 64
    assert "access_token" not in query
    assert seen["token"] == "unit-test-access-token"
    assert orders[0].id == "576461413038785752"
    assert request_id == "platform-request-id"


@pytest.mark.asyncio
async def test_search_orders_signs_exact_compact_json_body() -> None:
    """POST 查询正文必须与签名正文完全一致，且该调用不属于平台写操作。"""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        seen["query"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={"code": 0, "data": {"orders": [], "next_page_token": ""}, "request_id": "request-2"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        orders, next_token, _request_id = await TikTokReadClient(
            real_settings(), connected_channel(), http_client
        ).search_orders(order_status="UNPAID")

    expected_body = b'{"order_status":"UNPAID"}'
    unsigned = {key: value for key, value in seen["query"].items() if key != "sign"}
    expected_sign = generate_api_signature(
        "/order/202309/orders/search",
        unsigned,
        "unit-test-app-secret-value",
        expected_body,
    )
    assert seen["body"] == expected_body
    assert seen["query"]["sign"] == expected_sign
    assert orders == []
    assert next_token is None


@pytest.mark.asyncio
async def test_shop_tracking_conversation_message_and_webhook_reads_use_get_only() -> None:
    """其余首期能力必须全部调用官方 GET 读取端点，且有效店铺查询不附加 shop_cipher。"""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/seller/202309/shops":
            data: dict[str, object] = {"shops": [{"id": "7494049642642441621", "region": "US"}]}
        elif path.endswith("/tracking"):
            data = {
                "order_id": "576461413038785752",
                "logistics_details": [
                    {
                        "newest_tracking_no": "861651122474",
                        "carrier_name": "J&T Express",
                        "track_list": [
                            {
                                "description": "In transit",
                                "tracking_no": "861651122474",
                                "update_time_millis": 1718305585000,
                                "action_code": 31301,
                                "action_code_name": "sc_inbound",
                            }
                        ],
                    }
                ],
            }
        elif path == "/customer_service/202309/conversations":
            data = {
                "conversations": [
                    {
                        "id": "710688832392260838",
                        "create_time": 1718305585,
                        "participants": [
                            {"im_user_id": "707885565181165594", "user_id": "7021436810468230477", "role": "BUYER"}
                        ],
                    }
                ],
                "next_page_token": "",
            }
        elif path.endswith("/messages"):
            data = {
                "messages": [
                    {
                        "id": "722323407926368819",
                        "content": '{"content":"hello"}',
                        "create_time": 1718305585,
                        "sender": {"im_user_id": "707885565181165594", "role": "BUYER"},
                        "type": "TEXT",
                    }
                ],
                "next_page_token": "",
            }
        elif path == "/event/202309/webhooks":
            data = {
                "webhooks": [
                    {
                        "event_type": "NEW_MESSAGE",
                        "address": "https://www.overselfx.com/v1/webhooks/tiktok",
                    }
                ]
            }
        else:
            raise AssertionError(path)
        return httpx.Response(200, json={"code": 0, "data": data, "request_id": "request-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = TikTokReadClient(real_settings(), connected_channel(), http_client)
        shops, _ = await client.get_active_shops()
        tracking, _ = await client.get_tracking("576461413038785752")
        conversations, _, _ = await client.get_conversations()
        messages, _, _ = await client.get_conversation_messages("710688832392260838")
        webhooks, _ = await client.get_webhooks()

    assert [len(shops), len(tracking), len(conversations), len(messages), len(webhooks)] == [1, 1, 1, 1, 1]
    assert all(request.method == "GET" for request in requests)
    assert requests[1].url.path == "/logistics/202604/orders/576461413038785752/tracking"
    active_shop_request = requests[0]
    assert "shop_cipher" not in active_shop_request.url.params
    assert all(request.headers.get("x-tts-access-token") == "unit-test-access-token" for request in requests)


@pytest.mark.asyncio
async def test_read_default_client_uses_fixed_egress_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认只读请求必须经固定出口工厂，不能自行构造直连客户端。"""
    settings = real_settings()
    factory_calls: list[Settings] = []
    async_client_type = httpx.AsyncClient

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "request_id": "factory-request-id",
                "data": {"shops": [{"id": "7494049642642441621", "region": "US"}]},
            },
        )

    def fake_factory(candidate: Settings) -> httpx.AsyncClient:
        factory_calls.append(candidate)
        return async_client_type(transport=httpx.MockTransport(handler))

    def reject_direct_client(**_kwargs: object) -> httpx.AsyncClient:
        raise AssertionError("read client bypassed the fixed-egress factory")

    monkeypatch.setattr(tiktok_read_module, "create_tiktok_http_client", fake_factory, raising=False)
    monkeypatch.setattr(tiktok_read_module.httpx, "AsyncClient", reject_direct_client)

    shops, request_id = await TikTokReadClient(settings, connected_channel()).get_active_shops()

    assert [shop.id for shop in shops] == ["7494049642642441621"]
    assert request_id == "factory-request-id"
    assert factory_calls == [settings]


@pytest.mark.asyncio
async def test_read_client_maps_expired_permission_and_rate_limit_errors() -> None:
    """平台通用错误必须转换为稳定认证、权限和限流错误。"""
    for code, expected in ((105002, ErrorCode.TOKEN_EXPIRED), (105005, ErrorCode.PERMISSION_DENIED)):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request, code=code: httpx.Response(200, json={"code": code, "message": "sensitive"})
            )
        ) as http_client:
            with pytest.raises(AppError) as caught:
                await TikTokReadClient(real_settings(), connected_channel(), http_client).get_order_details(
                    ["576461413038785752"]
                )
        assert caught.value.code == expected

    attempts = 0

    def limited(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"code": 429})

    async with httpx.AsyncClient(transport=httpx.MockTransport(limited)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_order_details(
                ["576461413038785752"]
            )
    assert caught.value.code == ErrorCode.RATE_LIMITED
    assert attempts == 2


@pytest.mark.asyncio
async def test_rate_limit_retry_respects_bounded_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 优先采用 Retry-After，但恶意或异常提示不能造成无界等待。"""
    attempts = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "60"}, json={"code": 429})
        return httpx.Response(200, json={"code": 0, "data": {"orders": []}})

    monkeypatch.setattr("app.integrations.tiktok_read.asyncio.sleep", fake_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        orders, request_id = await TikTokReadClient(
            real_settings(), connected_channel(), http_client
        ).get_order_details(["576461413038785752"])

    assert orders == []
    assert request_id is None
    assert attempts == 2
    assert delays == [5.0]


@pytest.mark.asyncio
async def test_tracking_202604_preserves_multiple_parcels_and_historical_numbers() -> None:
    """202604 物流必须保留多包裹和重发前后的历史单号，不能压平成单一轨迹。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "request_id": "tracking-request-id",
                "data": {
                    "order_id": "576461413038785752",
                    "logistics_details": [
                        {
                            "newest_tracking_no": "LAST-MILE-2",
                            "carrier_name": "Carrier A",
                            "track_list": [
                                {
                                    "description": "First-mile pickup",
                                    "tracking_no": "FIRST-MILE-1",
                                    "update_time_millis": 1718305585000,
                                    "action_code": 30901,
                                    "action_code_name": "pickup_success",
                                },
                                {
                                    "description": "Last-mile inbound",
                                    "tracking_no": "LAST-MILE-2",
                                    "update_time_millis": 1718305595000,
                                    "action_code": 31301,
                                    "action_code_name": "sc_inbound",
                                },
                            ],
                        },
                        {
                            "newest_tracking_no": "PARCEL-2",
                            "carrier_name": "Carrier B",
                            "track_list": [],
                        },
                    ],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        parcels, request_id = await TikTokReadClient(real_settings(), connected_channel(), http_client).get_tracking(
            "576461413038785752"
        )

    assert request_id == "tracking-request-id"
    assert len(parcels) == 2
    assert parcels[0].newest_tracking_no == "LAST-MILE-2"
    assert [event.tracking_no for event in parcels[0].track_list] == ["FIRST-MILE-1", "LAST-MILE-2"]
    assert parcels[0].track_list[0].action_code_name == "pickup_success"
    assert parcels[1].track_list == []


@pytest.mark.asyncio
async def test_tracking_rejects_required_field_drift_without_retry() -> None:
    """202604 必需轨迹字段漂移时应立即失败，不能返回不完整物流或重复请求。"""
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "order_id": "576461413038785752",
                    "logistics_details": [
                        {
                            "newest_tracking_no": "TRACKING-1",
                            "track_list": [
                                {
                                    "description": "In transit",
                                    "tracking_no": "TRACKING-1",
                                    "update_time_millis": 1718305585000,
                                    "action_code": 31301,
                                }
                            ],
                        }
                    ],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_tracking("576461413038785752")

    assert caught.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        {"order_id": "576461413038785752"},
        {
            "order_id": "576461413038785752",
            "logistics_details": [{"newest_tracking_no": "TRACKING-1"}],
        },
    ],
    ids=["missing-logistics-details", "missing-track-list"],
)
async def test_tracking_rejects_missing_required_array_fields(data: dict[str, object]) -> None:
    """关键数组缺失表示平台契约漂移，必须失败关闭且不能重试。"""
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"code": 0, "data": data})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_tracking("576461413038785752")

    assert caught.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "expected_package_count"),
    [
        ({"order_id": "576461413038785752", "logistics_details": []}, 0),
        (
            {
                "order_id": "576461413038785752",
                "logistics_details": [{"newest_tracking_no": "TRACKING-1", "track_list": []}],
            },
            1,
        ),
    ],
    ids=["explicit-empty-logistics-details", "explicit-empty-track-list"],
)
async def test_tracking_accepts_explicit_empty_array_fields(
    data: dict[str, object],
    expected_package_count: int,
) -> None:
    """平台明确返回空数组是合法业务空结果，不能与字段缺失混淆。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": data})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        parcels, _request_id = await TikTokReadClient(real_settings(), connected_channel(), http_client).get_tracking(
            "576461413038785752"
        )

    assert len(parcels) == expected_package_count
    if parcels:
        assert parcels[0].track_list == []


@pytest.mark.asyncio
async def test_tracking_rejects_missing_logistics_scope_before_http() -> None:
    """缺少 seller.logistics 时必须在发出平台请求前失败关闭。"""
    attempts = 0
    channel = connected_channel()
    channel.scopes = [scope for scope in channel.scopes if scope != "seller.logistics"]

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"code": 0, "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), channel, http_client).get_tracking("576461413038785752")

    assert caught.value.code == ErrorCode.PERMISSION_DENIED
    assert attempts == 0


@pytest.mark.asyncio
async def test_tracking_rejects_mismatched_order_response() -> None:
    """平台返回其他订单的轨迹时必须失败关闭，避免跨订单展示物流。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 0, "data": {"order_id": "576461413038785753", "logistics_details": []}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_tracking("576461413038785752")

    assert caught.value.code == ErrorCode.THIRD_PARTY_ERROR


@pytest.mark.asyncio
async def test_read_client_retries_only_official_transient_platform_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """稳定业务错误只请求一次，官方 36009003 内部错误才允许有限重试。"""
    caplog.set_level("WARNING", logger="app.integrations.tiktok_read")
    stable_attempts = 0

    def stable_error(_request: httpx.Request) -> httpx.Response:
        nonlocal stable_attempts
        stable_attempts += 1
        return httpx.Response(200, json={"code": 123456, "message": "stable", "request_id": "stable-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(stable_error)) as http_client:
        with pytest.raises(AppError) as stable_caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_order_details(
                ["576461413038785752"]
            )

    assert stable_caught.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert stable_attempts == 1
    stable_logs = [record for record in caplog.records if record.message == "tiktok_read_api_failed"]
    assert len(stable_logs) == 1
    assert stable_logs[0].provider_request_id == "stable-id"
    caplog.clear()

    transient_attempts = 0

    def transient_error(_request: httpx.Request) -> httpx.Response:
        nonlocal transient_attempts
        transient_attempts += 1
        return httpx.Response(200, json={"code": 36009003, "message": "internal", "request_id": "transient-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transient_error)) as http_client:
        with pytest.raises(AppError) as transient_caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_order_details(
                ["576461413038785752"]
            )

    assert transient_caught.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert transient_attempts == 2
    transient_logs = [record for record in caplog.records if record.message == "tiktok_read_api_failed"]
    assert len(transient_logs) == 2
    assert all(record.provider_request_id == "transient-id" for record in transient_logs)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["network", "http_5xx"])
async def test_read_client_retries_only_transient_transport_failures(failure_kind: str) -> None:
    """连接异常和 5xx 最多尝试两次，且最终统一返回第三方服务错误。"""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if failure_kind == "network":
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_order_details(
                ["576461413038785752"]
            )

    assert caught.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert attempts == 2


@pytest.mark.asyncio
async def test_read_client_does_not_retry_malformed_success_payload() -> None:
    """成功状态下的非法 JSON 属于契约漂移，原样重试不会恢复。"""
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, text="not-json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(AppError) as caught:
            await TikTokReadClient(real_settings(), connected_channel(), http_client).get_order_details(
                ["576461413038785752"]
            )

    assert caught.value.code == ErrorCode.THIRD_PARTY_ERROR
    assert attempts == 1


@pytest.mark.asyncio
async def test_new_message_webhook_normalizes_visible_buyer_text() -> None:
    """官方 14 号消息事件只把可见买家消息写入客服工作台。"""
    event = await TikTokAdapter(real_settings()).resolve_webhook_event(
        connected_channel(),
        {
            "type": 14,
            "tts_notification_id": "7327112393057371910",
            "shop_id": "7494049642642441621",
            "timestamp": 1718305585,
            "data": {
                "message_id": "722323407926368819",
                "conversation_id": "710688832392260838",
                "type": "TEXT",
                "content": json.dumps({"content": "Where is my order?"}),
                "create_time": 1718305585,
                "is_visible": True,
                "sender": {"im_user_id": "707885565181165594", "role": "BUYER", "nickname": "Buyer"},
            },
        },
    )

    assert isinstance(event, MessageCreatedEvent)
    assert event.external_message_id == "722323407926368819"
    assert event.customer.external_id == "707885565181165594"
    assert event.content == "Where is my order?"


@pytest.mark.asyncio
async def test_order_webhook_hydrates_with_read_api_before_standardization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """订单通知摘要不能直接落库，必须先获取匹配的权威订单详情。"""
    order = TikTokOrder.model_validate(
        {
            "id": "576461413038785752",
            "user_id": "7021436810468230477",
            "status": "AWAITING_SHIPMENT",
            "create_time": 1718305585,
            "paid_time": 1718305586,
            "payment": {"currency": "USD", "total_amount": "9.99"},
            "line_items": [
                {"id": "577086512123755123", "product_name": "Product", "currency": "USD", "sale_price": "9.99"}
            ],
        }
    )

    class FakeReadClient:
        def __init__(self, _settings: Settings, _channel: ChannelAccount) -> None:
            pass

        async def get_order_details(self, order_ids: list[str]) -> tuple[list[TikTokOrder], str]:
            assert order_ids == ["576461413038785752"]
            return [order], "request-1"

    monkeypatch.setattr(adapters_module, "TikTokReadClient", FakeReadClient)
    event = await TikTokAdapter(real_settings()).resolve_webhook_event(
        connected_channel(),
        {
            "type": 1,
            "tts_notification_id": "7380066284010030890",
            "shop_id": "7494049642642441621",
            "timestamp": 1718305585,
            "data": {"order_id": "576461413038785752", "order_status": "AWAITING_SHIPMENT"},
        },
    )

    assert isinstance(event, OrderUpdatedEvent)
    assert event.external_order_id == "576461413038785752"
    assert event.payment_status == "paid"
    assert event.total_amount == Decimal("9.99")


@pytest.mark.asyncio
async def test_unknown_and_non_buyer_tiktok_events_are_ignored() -> None:
    """未知主题和卖家自己发出的消息不能制造客户未读消息。"""
    adapter = TikTokAdapter(real_settings())
    unknown = await adapter.resolve_webhook_event(
        connected_channel(),
        {
            "type": 999,
            "tts_notification_id": "7327112393057371911",
            "shop_id": "7494049642642441621",
            "timestamp": 1718305585,
            "data": {},
        },
    )
    outbound = await adapter.resolve_webhook_event(
        connected_channel(),
        {
            "type": 14,
            "tts_notification_id": "7327112393057371912",
            "shop_id": "7494049642642441621",
            "timestamp": 1718305585,
            "data": {"is_visible": True, "sender": {"im_user_id": "7494049642642441621", "role": "SHOP"}},
        },
    )

    assert unknown is None
    assert outbound is None


@pytest.mark.asyncio
async def test_seller_deauthorization_destroys_local_token_and_writes_lifecycle_audit() -> None:
    """官方 6 号撤销事件必须立即停用本地凭证，不能等待下一次 API 失败。"""
    channel = connected_channel()
    event = WebhookEvent(
        id=uuid.uuid4(),
        platform="tiktok",
        channel_account_id=channel.id,
        external_event_id="7327112393057371913",
        event_type="SELLER_DEAUTHORIZATION",
        signature_valid=True,
        payload_hash="a" * 64,
        raw_payload={},
        status="processing",
        received_at=datetime.now(UTC),
    )
    added: list[object] = []
    session = SimpleNamespace(add=added.append)

    await integration_service._process_tiktok_authorization(
        session,  # type: ignore[arg-type]
        event,
        channel,
        TikTokAuthorizationLifecycleEvent(
            action="deauthorized",
            event_id="7327112393057371913",
            external_store_id=channel.external_store_id,
        ),
    )

    assert channel.status == "disconnected"
    assert channel.access_token_ref == f"revoked://{channel.id}"
    assert channel.refresh_token_ref is None
    assert "shop_cipher" not in channel.metadata_json
    assert any(isinstance(value, AuditLog) and value.action == "channel.deauthorized" for value in added)


@pytest.mark.asyncio
async def test_duplicate_event_id_never_bypasses_signature_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """攻击者复用已落库通知 ID 时仍需提供与当前原始正文匹配的签名。"""
    existing = SimpleNamespace(signature_valid=True, channel_account_id=uuid.uuid4())

    class FakeSession:
        async def scalar(self, _statement: object) -> object:
            return existing

    class InvalidAdapter:
        def verify_webhook(self, _raw_body: bytes, _headers: dict[str, str]) -> bool:
            return False

    monkeypatch.setattr(integration_service, "get_platform_adapter", lambda _platform: InvalidAdapter())
    with pytest.raises(AppError) as caught:
        await integration_service.receive_webhook(
            FakeSession(),  # type: ignore[arg-type]
            "tiktok",
            b'{"tts_notification_id":"7327112393057371910"}',
            {"tts_notification_id": "7327112393057371910"},
            {"authorization": "invalid"},
        )

    assert caught.value.code == ErrorCode.TOKEN_INVALID


def test_official_envelope_fields_drive_idempotency_store_and_event_semantics() -> None:
    """官方通知 ID、shop_id 和数值主题必须进入既有幂等与审计字段。"""
    payload: dict[str, object] = {
        "type": 14,
        "tts_notification_id": "7327112393057371910",
        "shop_id": "7494049642642441621",
        "data": {},
    }

    assert stable_event_id(payload, b"different-body") == "7327112393057371910"
    assert webhook_external_store_id(payload) == "7494049642642441621"
    assert webhook_event_type("tiktok", payload) == "NEW_MESSAGE"
    assert webhook_event_type("tiktok", {**payload, "type": 999}) == "UNSUPPORTED_999"


def test_fallback_event_id_is_raw_body_hash() -> None:
    """平台缺少通知 ID 时仍使用原始正文摘要形成稳定幂等键。"""
    raw = b'{"type":999}'
    assert stable_event_id({}, raw) == hashlib.sha256(raw).hexdigest()
