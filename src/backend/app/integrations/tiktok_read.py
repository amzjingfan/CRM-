"""TikTok Shop 真实只读 API 客户端和官方响应契约。"""

import asyncio
import json
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.integrations.oauth_service import decrypt_tiktok_access_token
from app.integrations.tiktok_http import create_tiktok_http_client
from app.integrations.tiktok_oauth import generate_api_signature
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount

API_BASE_URL = "https://open-api.tiktokglobalshop.com"
READ_MAX_ATTEMPTS = 2
READ_RETRY_BASE_DELAY_SECONDS = 0.25
READ_RETRY_MAX_DELAY_SECONDS = 5.0
TOKEN_EXPIRED_CODES = {105002}
TOKEN_INVALID_CODES = {105001, 36009004}
PERMISSION_DENIED_CODES = {105005, 36009033}
TRANSIENT_PLATFORM_CODES = {36009003}

logger = logging.getLogger(__name__)


class TikTokModel(BaseModel):
    """允许平台增量增加字段，但所有被业务使用的字段仍需显式校验。"""

    model_config = ConfigDict(extra="ignore")


class TikTokApiEnvelope(TikTokModel):
    """TikTok Shop OpenAPI 的统一响应信封。"""

    code: int
    message: str = ""
    request_id: str | None = None
    data: dict[str, Any] | None = None


class TikTokActiveShop(TikTokModel):
    """Get Active Shops 返回的低敏店铺摘要。"""

    id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    region: str | None = Field(default=None, max_length=20)


class TikTokPayment(TikTokModel):
    """订单支付金额摘要。"""

    currency: str | None = Field(default=None, max_length=10)
    total_amount: str | None = Field(default=None, max_length=50)


class TikTokOrderLineItem(TikTokModel):
    """TikTok 订单行；平台每个 line item 本身代表一个商品实例。"""

    id: str | None = Field(default=None, max_length=200, pattern=r"^\d+$")
    product_id: str | None = Field(default=None, max_length=200, pattern=r"^\d+$")
    product_name: str | None = Field(default=None, max_length=500)
    sku_name: str | None = Field(default=None, max_length=500)
    seller_sku: str | None = Field(default=None, max_length=200)
    currency: str | None = Field(default=None, max_length=10)
    sale_price: str | None = Field(default=None, max_length=50)
    tracking_number: str | None = Field(default=None, max_length=200)


class TikTokOrder(TikTokModel):
    """Get Order Detail 202507 中本系统实际消费的字段。"""

    id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    user_id: str | None = Field(default=None, max_length=200, pattern=r"^\d+$")
    buyer_nickname: str | None = Field(default=None, max_length=200)
    buyer_avatar: str | None = Field(default=None, max_length=500)
    status: str = Field(min_length=1, max_length=30)
    create_time: int | None = None
    paid_time: int | None = None
    fulfillment_type: str | None = Field(default=None, max_length=30)
    tracking_number: str | None = Field(default=None, max_length=200)
    payment: TikTokPayment | None = None
    line_items: list[TikTokOrderLineItem] = Field(default_factory=list, max_length=500)


class TikTokTrackingEntry(TikTokModel):
    """202604 物流轨迹节点；动作码用于稳定展示，描述只作为平台补充文本。"""

    description: str = Field(min_length=1, max_length=1000)
    tracking_no: str = Field(min_length=1, max_length=200)
    update_time_millis: int = Field(ge=0)
    action_code: int
    action_code_name: str = Field(min_length=1, max_length=100)


class TikTokStandardTrackingEntry(TikTokModel):
    """通用 202309 物流节点；普通承运商没有 CBT 专有单号和动作名称。"""

    description: str = Field(min_length=1, max_length=1000)
    update_time_millis: int = Field(ge=0)
    action_code: int


class TikTokLogisticsDetail(TikTokModel):
    """订单中的单个包裹；重发后最新单号与历史节点单号可以不同。"""

    newest_tracking_no: str | None = Field(default=None, max_length=200)
    carrier_name: str | None = Field(default=None, max_length=200)
    track_list: list[TikTokTrackingEntry] = Field(max_length=1000)


class TikTokLogisticsData(TikTokModel):
    """Get Logistics Tracking 202604 的业务数据。"""

    order_id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    logistics_details: list[TikTokLogisticsDetail] = Field(max_length=200)


class TikTokMessageSender(TikTokModel):
    """客服消息发送者；IM ID 只用于消息域身份，不用于订单查询。"""

    im_user_id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    nickname: str | None = Field(default=None, max_length=200)
    avatar: str | None = Field(default=None, max_length=500)
    role: str = Field(min_length=1, max_length=30)


class TikTokConversationMessage(TikTokModel):
    """Get Conversation Messages 202309 的消息摘要。"""

    id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    content: str = Field(max_length=20_000)
    create_time: int
    is_visible: bool = True
    sender: TikTokMessageSender
    type: str = Field(min_length=1, max_length=50)


class TikTokConversationParticipant(TikTokModel):
    """会话参与者摘要。"""

    im_user_id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    user_id: str | None = Field(default=None, max_length=200, pattern=r"^\d+$")
    nickname: str | None = Field(default=None, max_length=200)
    role: str = Field(min_length=1, max_length=30)


class TikTokLatestMessage(TikTokModel):
    """会话列表的最新消息标识，用于跳过未变化会话。"""

    id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")


class TikTokConversation(TikTokModel):
    """Get Conversations 202309 的会话摘要。"""

    id: str = Field(min_length=1, max_length=200, pattern=r"^\d+$")
    create_time: int
    unread_count: int = Field(default=0, ge=0)
    can_send_message: bool = False
    participants: list[TikTokConversationParticipant] = Field(default_factory=list)
    latest_message: TikTokLatestMessage | None = None


class TikTokWebhookSubscription(TikTokModel):
    """已配置 Webhook 主题；地址只用于部署核对，不写入业务日志。"""

    event_type: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=500)
    create_time: int | None = None
    update_time: int | None = None


class TikTokReadClient:
    """只允许调用经白名单声明的 TikTok Shop 读取端点。

    客户端固定官方域名和路径，不接受调用方传入任意 URL；所有请求使用
    当前渠道的加密 Access Token、shop_cipher 和 App Secret 生成实时签名。
    读取请求最多尝试两次，写请求不在本类能力范围内。
    """

    def __init__(
        self,
        settings: Settings,
        channel: ChannelAccount,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.real_tiktok_read_enabled:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 真实只读能力未启用", 503)
        if channel.platform != "tiktok" or channel.status != "connected":
            raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 渠道未连接", 401)
        shop_cipher = channel.metadata_json.get("shop_cipher")
        if not isinstance(shop_cipher, str) or not shop_cipher:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 店铺标识缺失，请重新授权", 503)
        secret = settings.tiktok_app_secret
        if secret is None:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 真实只读能力未配置", 503)

        self.settings = settings
        self.channel = channel
        self.client = client
        self.shop_cipher = shop_cipher
        self.app_secret = secret.get_secret_value()
        self.access_token = decrypt_tiktok_access_token(channel, settings)

    def _require_scope(self, required_scope: str) -> None:
        """在发出请求前拒绝已知缺失的 Scope，避免无意义地访问平台。"""
        if required_scope not in set(self.channel.scopes):
            raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权权限不足，请重新授权", 403)

    async def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        query: dict[str, str | int],
        body: dict[str, object] | None = None,
        *,
        include_shop_cipher: bool = True,
    ) -> TikTokApiEnvelope:
        """签名并执行安全可重试的只读请求，统一映射平台错误。"""
        body_bytes = (
            json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if body is not None else b""
        )
        last_error: Exception | None = None
        for attempt in range(READ_MAX_ATTEMPTS):
            params: dict[str, str | int] = {"app_key": self.settings.tiktok_app_key, "timestamp": int(time.time())}
            if include_shop_cipher:
                params["shop_cipher"] = self.shop_cipher
            params.update(query)
            params["sign"] = generate_api_signature(path, params, self.app_secret, body_bytes)
            headers = {"content-type": "application/json", "x-tts-access-token": self.access_token}
            try:
                response = await self._send(method, path, params, headers, body_bytes)
            except httpx.TransportError as exc:
                # 只有连接、超时等传输失败可以安全重试；平台业务错误不能消耗额外配额。
                last_error = exc
                if attempt + 1 < READ_MAX_ATTEMPTS:
                    await self._sleep_before_retry(attempt)
                    continue
                break

            if response.status_code == 429:
                if attempt + 1 < READ_MAX_ATTEMPTS:
                    await self._sleep_before_retry(attempt, response)
                    continue
                raise AppError(ErrorCode.RATE_LIMITED, "TikTok 请求过于频繁，请稍后重试", 429)
            if response.status_code == 401:
                raise AppError(ErrorCode.TOKEN_EXPIRED, "TikTok 授权已过期，请重新授权", 401)
            if response.status_code == 403:
                raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权权限不足", 403)
            if response.status_code >= 500:
                last_error = httpx.HTTPStatusError(
                    "TikTok upstream failure",
                    request=response.request,
                    response=response,
                )
                if attempt + 1 < READ_MAX_ATTEMPTS:
                    await self._sleep_before_retry(attempt)
                    continue
                break
            if response.status_code >= 300:
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 读取请求失败", 502)

            try:
                envelope = TikTokApiEnvelope.model_validate(response.json())
            except (ValueError, ValidationError) as exc:
                # 契约或正文漂移不会因原样重试恢复，必须立即失败关闭并交由人工排查。
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 返回数据结构异常", 502) from exc
            if envelope.code in TRANSIENT_PLATFORM_CODES:
                self._log_envelope_error(envelope)
                if attempt + 1 < READ_MAX_ATTEMPTS:
                    await self._sleep_before_retry(attempt)
                    continue
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 读取服务暂时不可用", 502)
            if envelope.code != 0:
                self._raise_envelope_error(envelope, path)
            if envelope.data is None:
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 返回数据结构异常", 502)
            return envelope
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 读取服务暂时不可用", 502) from last_error

    @staticmethod
    async def _sleep_before_retry(attempt: int, response: httpx.Response | None = None) -> None:
        """按指数退避等待；429 的数字 Retry-After 提示优先且被限制在安全上限内。"""
        delay = min(READ_RETRY_BASE_DELAY_SECONDS * (2**attempt), READ_RETRY_MAX_DELAY_SECONDS)
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = min(max(float(retry_after), 0.0), READ_RETRY_MAX_DELAY_SECONDS)
                except ValueError:
                    pass
        await asyncio.sleep(delay)

    async def _send(
        self,
        method: str,
        path: str,
        params: dict[str, str | int],
        headers: dict[str, str],
        body: bytes,
    ) -> httpx.Response:
        """发送一次请求；注入客户端用于确定性测试，正式运行由上下文管理器关闭连接。"""
        url = f"{API_BASE_URL}{path}"
        if self.client is not None:
            return await self.client.request(method, url, params=params, headers=headers, content=body)
        async with create_tiktok_http_client(self.settings) as client:
            return await client.request(method, url, params=params, headers=headers, content=body)

    @staticmethod
    def _log_envelope_error(envelope: TikTokApiEnvelope) -> None:
        """只记录不可逆平台请求摘要和数字错误码。"""
        logger.warning(
            "tiktok_read_api_failed",
            extra={
                "event": "tiktok_read_api_failed",
                "provider_request_id": envelope.request_id,
                "status_code": envelope.code,
            },
        )

    @classmethod
    def _raise_envelope_error(cls, envelope: TikTokApiEnvelope, path: str) -> None:
        """按官方通用错误码转换稳定错误，不向外暴露平台原始消息。"""
        del path  # 路径由代码白名单固定，无需进入日志或外部错误。
        cls._log_envelope_error(envelope)
        if envelope.code in TOKEN_EXPIRED_CODES:
            raise AppError(ErrorCode.TOKEN_EXPIRED, "TikTok 授权已过期，请重新授权", 401)
        if envelope.code in TOKEN_INVALID_CODES:
            raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 授权无效，请重新授权", 401)
        if envelope.code in PERMISSION_DENIED_CODES:
            raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 授权权限不足", 403)
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 读取请求失败", 502)

    @staticmethod
    def _validated_list(data: dict[str, Any], key: str, model: type[TikTokModel]) -> list[TikTokModel]:
        """校验列表字段，字段缺失或类型漂移时失败关闭。"""
        values = data.get(key)
        if not isinstance(values, list):
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 返回数据结构异常", 502)
        try:
            return [model.model_validate(item) for item in values]
        except ValidationError as exc:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 返回数据结构异常", 502) from exc

    async def get_active_shops(self) -> tuple[list[TikTokActiveShop], str | None]:
        """读取当前授权主体下的有效店铺。"""
        self._require_scope("seller.authorization.info")
        envelope = await self._request("GET", "/seller/202309/shops", {}, include_shop_cipher=False)
        items = self._validated_list(envelope.data or {}, "shops", TikTokActiveShop)
        return [item for item in items if isinstance(item, TikTokActiveShop)], envelope.request_id

    async def search_orders(
        self,
        page_size: int = 20,
        page_token: str | None = None,
        order_status: str | None = None,
    ) -> tuple[list[TikTokOrder], str | None, str | None]:
        """分页读取订单；POST 仅是 TikTok 查询协议，不产生平台写操作。"""
        self._require_scope("seller.order.info")
        if not 1 <= page_size <= 100:
            raise AppError(ErrorCode.VALIDATION_ERROR, "订单分页大小无效", 400)
        query: dict[str, str | int] = {"page_size": page_size, "sort_order": "DESC", "sort_field": "create_time"}
        if page_token:
            query["page_token"] = page_token
        body: dict[str, object] = {}
        if order_status:
            body["order_status"] = order_status
        envelope = await self._request("POST", "/order/202309/orders/search", query, body)
        data = envelope.data or {}
        items = self._validated_list(data, "orders", TikTokOrder)
        next_token = data.get("next_page_token")
        return (
            [item for item in items if isinstance(item, TikTokOrder)],
            str(next_token) if next_token else None,
            envelope.request_id,
        )

    async def get_order_details(self, order_ids: list[str]) -> tuple[list[TikTokOrder], str | None]:
        """使用当前最新的 202507 订单详情端点读取最多 50 个订单。"""
        self._require_scope("seller.order.info")
        if not order_ids or len(order_ids) > 50 or any(not value.isdigit() for value in order_ids):
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 订单 ID 列表无效", 400)
        envelope = await self._request("GET", "/order/202507/orders", {"ids": ",".join(order_ids)})
        items = self._validated_list(envelope.data or {}, "orders", TikTokOrder)
        return [item for item in items if isinstance(item, TikTokOrder)], envelope.request_id

    async def get_tracking(self, order_id: str) -> tuple[list[TikTokLogisticsDetail], str | None]:
        """按 202604 契约读取多包裹物流，不调用任何履约写接口。"""
        self._require_scope("seller.logistics")
        if not order_id.isdigit():
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 订单 ID 无效", 400)
        path = f"/logistics/202604/orders/{order_id}/tracking"
        envelope = await self._request("GET", path, {})
        try:
            logistics = TikTokLogisticsData.model_validate(envelope.data)
        except ValidationError as exc:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 返回数据结构异常", 502) from exc
        if logistics.order_id != order_id:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 返回订单不匹配", 502)
        return logistics.logistics_details, envelope.request_id

    async def get_standard_tracking(self, order_id: str) -> tuple[list[TikTokStandardTrackingEntry], str | None]:
        """按 202309 通用契约读取订单轨迹，不推断 CBT 首程或执行履约写入。"""
        self._require_scope("seller.logistics")
        if not order_id.isdigit():
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 订单 ID 无效", 400)
        path = f"/fulfillment/202309/orders/{order_id}/tracking"
        envelope = await self._request("GET", path, {})
        items = self._validated_list(envelope.data or {}, "tracking", TikTokStandardTrackingEntry)
        return [item for item in items if isinstance(item, TikTokStandardTrackingEntry)], envelope.request_id

    async def get_conversations(
        self,
        page_size: int = 20,
        page_token: str | None = None,
    ) -> tuple[list[TikTokConversation], str | None, str | None]:
        """读取买家会话；该接口不会改变平台未读状态。"""
        self._require_scope("seller.customer_service")
        if not 1 <= page_size <= 20:
            raise AppError(ErrorCode.VALIDATION_ERROR, "会话分页大小无效", 400)
        query: dict[str, str | int] = {"page_size": page_size, "locale": "en"}
        if page_token:
            query["page_token"] = page_token
        envelope = await self._request("GET", "/customer_service/202309/conversations", query)
        data = envelope.data or {}
        items = self._validated_list(data, "conversations", TikTokConversation)
        next_token = data.get("next_page_token")
        return (
            [item for item in items if isinstance(item, TikTokConversation)],
            str(next_token) if next_token else None,
            envelope.request_id,
        )

    async def get_conversation_messages(
        self,
        conversation_id: str,
        page_size: int = 10,
        page_token: str | None = None,
    ) -> tuple[list[TikTokConversationMessage], str | None, str | None]:
        """读取会话消息；显式保持只读，不调用 Read Message。"""
        self._require_scope("seller.customer_service")
        if not conversation_id.isdigit() or not 1 <= page_size <= 10:
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 会话查询参数无效", 400)
        path = f"/customer_service/202309/conversations/{conversation_id}/messages"
        query: dict[str, str | int] = {
            "page_size": page_size,
            "locale": "en",
            "sort_order": "DESC",
            "sort_field": "create_time",
            "need_data": "false",
        }
        if page_token:
            query["page_token"] = page_token
        envelope = await self._request("GET", path, query)
        data = envelope.data or {}
        items = self._validated_list(data, "messages", TikTokConversationMessage)
        next_token = data.get("next_page_token")
        return (
            [item for item in items if isinstance(item, TikTokConversationMessage)],
            str(next_token) if next_token else None,
            envelope.request_id,
        )

    async def get_webhooks(self) -> tuple[list[TikTokWebhookSubscription], str | None]:
        """只读核对 Partner Center 当前订阅，不创建、更新或删除订阅。"""
        self._require_scope("seller.authorization.info")
        envelope = await self._request("GET", "/event/202309/webhooks", {})
        items = self._validated_list(envelope.data or {}, "webhooks", TikTokWebhookSubscription)
        return [item for item in items if isinstance(item, TikTokWebhookSubscription)], envelope.request_id


def parse_money(value: str | None) -> Decimal:
    """把平台十进制字符串转换为金额；无效值失败关闭，避免静默写入错误金额。"""
    if value is None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单金额缺失", 502)
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单金额无效", 502) from exc
    if amount < 0:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单金额无效", 502)
    return amount
