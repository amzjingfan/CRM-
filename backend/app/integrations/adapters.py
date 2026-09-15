"""平台契约适配器；Shopee/Amazon 在 Phase 2 明确为 Mock。"""

import hashlib
import hmac
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime

from pydantic import ValidationError

from app.integrations.schemas import (
    CustomerPayload,
    MessageCreatedEvent,
    OrderItemPayload,
    OrderUpdatedEvent,
    PlatformEvent,
    ResolvedPlatformEvent,
    SendMessageCommand,
    SendMessageResult,
    TikTokAuthorizationLifecycleEvent,
    platform_event_adapter,
)
from app.integrations.tiktok_read import TikTokOrder, TikTokReadClient, parse_money
from app.integrations.tiktok_write import TikTokMessageClient
from app.shared.config.settings import Settings, get_settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount


class PlatformAdapter(ABC):
    """所有平台实现必须满足的安全边界。"""

    platform: str
    # 当前三个实现都仍是契约级 Mock。未来真实适配器必须显式覆盖为 True，
    # 自动回复 Worker 才可能执行平台写操作。
    real_writes: bool = False

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        """验证原始请求体签名。"""

    def normalize_event(self, payload: dict[str, object]) -> PlatformEvent:
        """在进入业务层前完成统一事件类型校验。"""
        event: PlatformEvent = platform_event_adapter.validate_python(payload)
        return event

    async def resolve_webhook_event(
        self,
        channel_account: ChannelAccount,
        payload: dict[str, object],
    ) -> ResolvedPlatformEvent:
        """把已验签载荷转换为业务事件；Mock 平台保持同步契约兼容。"""
        return self.normalize_event(payload)

    async def send_message(self, channel_account: ChannelAccount, command: SendMessageCommand) -> SendMessageResult:
        """Phase 2 返回可识别的契约级 Mock 发送结果。"""
        settings = get_settings()
        # 显式开关是 Mock 能力的唯一授权来源；直接调用也不得绕过 resolver。
        if not settings.allow_mock_platform_adapters:
            return SendMessageResult(
                external_message_id=f"mock-disabled-{uuid.uuid4()}",
                status="failed",
                error_code="MOCK_ADAPTER_DISABLED",
            )
        if channel_account.status != "connected":
            return SendMessageResult(
                external_message_id=f"mock-failed-{uuid.uuid4()}",
                status="failed",
                error_code="CHANNEL_DISCONNECTED",
            )
        return SendMessageResult(external_message_id=f"mock-{self.platform}-{uuid.uuid4()}", status="sent")

    def normalize_order(self, payload: dict[str, object]) -> OrderUpdatedEvent:
        """标准化订单事件并拒绝非订单载荷。"""
        event = self.normalize_event(payload)
        if not isinstance(event, OrderUpdatedEvent):
            raise AppError(ErrorCode.VALIDATION_ERROR, "不是订单事件", 422)
        return event


class TikTokAdapter(PlatformAdapter):
    """TikTok Webhook 官方验签、事件标准化和真实只读补全适配器。"""

    platform = "tiktok"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.real_writes = settings.real_tiktok_message_write_enabled

    async def send_message(self, channel_account: ChannelAccount, command: SendMessageCommand) -> SendMessageResult:
        """真实写开关开启时只接受人工确认命令，否则保持明确 Mock。"""
        if not self.settings.real_tiktok_message_write_enabled:
            return await super().send_message(channel_account, command)
        if not command.human_confirmed:
            return SendMessageResult(
                status="failed",
                mock=False,
                error_code="REAL_WRITE_REQUIRES_HUMAN_CONFIRMATION",
            )
        try:
            return await TikTokMessageClient(self.settings, channel_account).send_text_message(command)
        except AppError as error:
            # 配置、渠道和 Scope 校验均发生在网络请求前，因此是确定失败，
            # 只向工具层返回项目稳定错误码，不暴露平台凭证或配置细节。
            return SendMessageResult(status="failed", mock=False, error_code=error.code.value)

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        if self.settings.real_tiktok_webhook_enabled:
            signature = headers.get("authorization", "")
            secret_value = self.settings.tiktok_app_secret
            if secret_value is None:
                return False
            secret = secret_value.get_secret_value().encode()
        else:
            # 本地契约回归继续接受旧 Mock Header；真实环境永远不会进入此分支。
            signature = headers.get("x-tts-signature", "")
            secret = self.settings.tiktok_webhook_secret.get_secret_value().encode()
        signed = self.settings.tiktok_app_key.encode() + raw_body
        expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
        return bool(signature) and hmac.compare_digest(signature, expected)

    async def resolve_webhook_event(
        self,
        channel_account: ChannelAccount,
        payload: dict[str, object],
    ) -> ResolvedPlatformEvent:
        """解析官方数值主题；订单通过最新只读详情 API 补全可信快照。"""
        if not self.settings.real_tiktok_webhook_enabled:
            return self.normalize_event(payload)
        notification_type = payload.get("type")
        event_id = str(payload.get("tts_notification_id", ""))
        external_store_id = str(payload.get("shop_id", ""))
        data = payload.get("data")
        if (
            not event_id.isdigit()
            or not external_store_id.isdigit()
            or type(notification_type) is not int
            or not isinstance(data, dict)
        ):
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok Webhook 数据结构无效", 422)

        # 官方主题页明确给出的数值映射：1=订单状态、14=新客服消息、
        # 6=卖家撤销授权、7=授权即将到期。未知主题不猜测、不写业务表。
        if notification_type == 1:
            return await self._resolve_order_event(channel_account, event_id, external_store_id, data)
        if notification_type == 14:
            return self._resolve_message_event(event_id, external_store_id, data)
        if notification_type == 6:
            return TikTokAuthorizationLifecycleEvent(
                action="deauthorized",
                event_id=event_id,
                external_store_id=external_store_id,
            )
        if notification_type == 7:
            expiration_time = _unix_datetime(data.get("expiration_time"), required=False)
            return TikTokAuthorizationLifecycleEvent(
                action="expiring",
                event_id=event_id,
                external_store_id=external_store_id,
                expiration_time=expiration_time,
            )
        return None

    async def _resolve_order_event(
        self,
        channel_account: ChannelAccount,
        event_id: str,
        external_store_id: str,
        data: dict[str, object],
    ) -> OrderUpdatedEvent:
        """按 Webhook 的订单 ID 拉取权威订单详情，避免把通知摘要当完整事实。"""
        order_id = str(data.get("order_id", ""))
        if not order_id.isdigit():
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 订单事件缺少订单 ID", 422)
        orders, _request_id = await TikTokReadClient(self.settings, channel_account).get_order_details([order_id])
        order = next((item for item in orders if item.id == order_id), None)
        if order is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "TikTok 订单详情尚不可用", 404)
        return _normalize_tiktok_order(order, event_id, external_store_id)

    @staticmethod
    def _resolve_message_event(
        event_id: str,
        external_store_id: str,
        data: dict[str, object],
    ) -> MessageCreatedEvent | None:
        """标准化官方新消息载荷；非买家或不可见消息不进入客服未读队列。"""
        sender = data.get("sender")
        if not isinstance(sender, dict) or sender.get("role") != "BUYER" or data.get("is_visible", True) is not True:
            return None
        external_customer_id = str(sender.get("im_user_id", ""))
        conversation_id = str(data.get("conversation_id", ""))
        message_id = str(data.get("message_id", ""))
        if not external_customer_id.isdigit() or not conversation_id.isdigit() or not message_id.isdigit():
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息标识无效", 422)
        message_type = str(data.get("type", "OTHER"))
        content = _message_content(message_type, data.get("content"))
        created_at = _unix_datetime(data.get("create_time"), required=True)
        if created_at is None:  # required=True 已保证非空，此分支用于静态类型和纵深防御。
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息时间无效", 422)
        try:
            return MessageCreatedEvent(
                event_type="message.created",
                event_id=event_id,
                external_store_id=external_store_id,
                external_conversation_id=conversation_id,
                external_message_id=message_id,
                customer=CustomerPayload(
                    external_id=external_customer_id,
                    name=str(sender["nickname"]) if sender.get("nickname") else None,
                    avatar=str(sender["avatar"]) if sender.get("avatar") else None,
                ),
                content=content,
                created_at=created_at,
            )
        except ValidationError as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息事件字段无效", 422) from exc


class MockHmacAdapter(PlatformAdapter):
    """Shopee/Amazon 契约测试适配器，不表示真实平台联调完成。"""

    def __init__(self, platform: str, secret: str) -> None:
        self.platform = platform
        self.secret = secret

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        signature = headers.get("x-mock-signature", "")
        expected = hmac.new(self.secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return bool(signature) and hmac.compare_digest(signature, expected)


def get_platform_adapter(platform: str) -> PlatformAdapter:
    """从白名单解析平台，禁止动态加载任意适配器。"""
    settings = get_settings()
    if platform == "tiktok":
        if not settings.real_tiktok_webhook_enabled and not settings.allow_mock_platform_adapters:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok Webhook 与 Mock 适配器均未启用", 503)
        return TikTokAdapter(settings)
    if platform in {"shopee", "amazon"}:
        if not settings.allow_mock_platform_adapters:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "未启用 Mock 平台适配器", 503)
        secret = settings.shopee_webhook_secret if platform == "shopee" else settings.amazon_webhook_secret
        return MockHmacAdapter(platform, secret)
    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "不支持的平台", 404)


def get_message_adapter(platform: str) -> PlatformAdapter:
    """解析消息发送适配器，避免把 Webhook 开关错误复用为写能力门禁。"""
    settings = get_settings()
    if platform == "tiktok":
        if not settings.real_tiktok_message_write_enabled and not settings.allow_mock_platform_adapters:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 普通消息发送未启用", 503)
        return TikTokAdapter(settings)
    if platform in {"shopee", "amazon"}:
        if not settings.allow_mock_platform_adapters:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "未启用该平台消息适配器", 503)
        secret = settings.shopee_webhook_secret if platform == "shopee" else settings.amazon_webhook_secret
        return MockHmacAdapter(platform, secret)
    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "不支持的平台", 404)


def _unix_datetime(value: object, *, required: bool) -> datetime | None:
    """解析 TikTok 秒级 Unix 时间，拒绝布尔值、负数和越界值。"""
    if (value is None or value == "") and not required:
        return None
    if isinstance(value, bool):
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 时间字段无效", 422)
    try:
        timestamp = int(str(value))
        if timestamp <= 0:
            raise ValueError
        return datetime.fromtimestamp(timestamp, UTC)
    except (ValueError, OverflowError, OSError) as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 时间字段无效", 422) from exc


def _message_content(message_type: str, raw_content: object) -> str:
    """提取客服可展示内容；卡片只显示类型占位，不持久化完整第三方载荷。"""
    if not isinstance(raw_content, str):
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息内容无效", 422)
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息内容无效", 422) from exc
    if isinstance(parsed, dict):
        text_content = parsed.get("content")
        if isinstance(text_content, str) and text_content.strip():
            return text_content.strip()
    return f"[TikTok {message_type}]"


def _normalize_tiktok_order(order: TikTokOrder, event_id: str, external_store_id: str) -> OrderUpdatedEvent:
    """把 TikTok 202507 订单详情映射为项目统一订单事件。"""
    payment = order.payment
    currency = (
        payment.currency
        if payment and payment.currency
        else next(
            (item.currency for item in order.line_items if item.currency),
            None,
        )
    )
    if currency is None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单币种缺失", 502)
    items = [
        OrderItemPayload(
            external_item_id=item.id,
            sku=item.seller_sku,
            product_name=item.product_name or item.sku_name or "TikTok 商品",
            quantity=1,
            unit_price=parse_money(item.sale_price),
        )
        for item in order.line_items
    ]
    customer = None
    if order.user_id:
        customer = CustomerPayload(
            external_id=order.user_id,
            name=order.buyer_nickname,
            avatar=order.buyer_avatar,
        )
    payment_status = "paid" if order.paid_time is not None else ("unpaid" if order.status == "UNPAID" else None)
    return OrderUpdatedEvent(
        event_type="order.updated",
        event_id=event_id,
        external_store_id=external_store_id,
        external_order_id=order.id,
        customer=customer,
        status=order.status,
        payment_status=payment_status,
        fulfillment_status=order.status,
        currency=currency,
        total_amount=parse_money(payment.total_amount if payment else None),
        tracking_number=order.tracking_number,
        tracking_status=order.status,
        ordered_at=_unix_datetime(order.create_time, required=False),
        items=items,
    )
