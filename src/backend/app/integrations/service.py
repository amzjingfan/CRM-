"""Webhook 接收、认领和标准化入库服务。"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_management.models import AgentTask
from app.agent_management.repository import find_enabled_config
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.conversations.workflow import reopen_on_new_buyer_message
from app.customers.models import Customer
from app.integrations.adapters import get_platform_adapter
from app.integrations.models import WebhookEvent
from app.integrations.schemas import (
    CustomerPayload,
    MessageCreatedEvent,
    OrderUpdatedEvent,
    ReviewUpdatedEvent,
    TikTokAuthorizationLifecycleEvent,
    WebhookAccepted,
)
from app.marketing.models import CustomerReview
from app.orders.models import Order, OrderItem
from app.shared.config.settings import get_settings
from app.shared.database.redis import redis_client
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount


def stable_event_id(payload: dict[str, object], raw_body: bytes) -> str:
    """优先外部事件 ID，否则使用请求体哈希形成稳定幂等键。"""
    value = payload.get("tts_notification_id") or payload.get("event_id")
    return str(value)[:200] if value else hashlib.sha256(raw_body).hexdigest()


def webhook_external_store_id(payload: dict[str, object]) -> str:
    """兼容官方 TikTok shop_id 与既有统一 Mock 字段。"""
    return str(payload.get("shop_id") or payload.get("external_store_id") or "")[:200]


def webhook_event_type(platform: str, payload: dict[str, object]) -> str:
    """把已由官方主题页确认的 TikTok 数值主题映射为可审计语义。"""
    notification_type = payload.get("type")
    if platform == "tiktok" and type(notification_type) is int:
        return {
            1: "ORDER_STATUS_CHANGE",
            6: "SELLER_DEAUTHORIZATION",
            7: "UPCOMING_AUTHORIZATION_EXPIRATION",
            14: "NEW_MESSAGE",
        }.get(notification_type, f"UNSUPPORTED_{notification_type}")
    return str(payload.get("event_type", "unknown"))[:100]


def _duplicate_webhook_receipt(existing: WebhookEvent, event_id: str, payload_hash: str) -> WebhookAccepted:
    """只有同一已验签正文和已绑定店铺可以复用成功回执。"""
    if not existing.signature_valid or existing.payload_hash != payload_hash:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Webhook 通知 ID 与已接收事件冲突", 409)
    if existing.channel_account_id is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "平台店铺未授权", 404)
    return WebhookAccepted(event_id=event_id, duplicate=True, accepted=True)


def _probe_matches(payload: dict[str, object], platform: str, *, check_expiry: bool = True) -> bool:
    settings = get_settings()
    if settings.app_env != "staging" or not settings.real_tiktok_webhook_enabled:
        return False
    if settings.g2_webhook_probe_mode == "off" or platform != "tiktok" or type(payload.get("type")) is not int:
        return False
    if payload["type"] != 14:
        return False
    if check_expiry and (
        settings.g2_webhook_probe_expires_at is None or settings.g2_webhook_probe_expires_at <= datetime.now(UTC)
    ):
        return False
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("conversation_id") != settings.g2_webhook_probe_conversation_id:
        return False
    sender = data.get("sender")
    return (
        isinstance(sender, dict)
        and sender.get("role") == "BUYER"
        and data.get("is_visible", True) is True
        and str(payload.get("tts_notification_id", "")).isdigit()
        and str(payload.get("shop_id", "")).isdigit()
        and str(sender.get("im_user_id", "")).isdigit()
        and str(data.get("message_id", "")).isdigit()
        and type(data.get("create_time")) is int
    )


def _probe_marker_key() -> str:
    return f"g2:webhook-retry-probe:{get_settings().g2_webhook_probe_run_id}:first"


def _probe_audit(
    *, store_id: uuid.UUID, event: WebhookEvent | None, payload_hash: str, result: str, mode: str
) -> AuditLog:
    # 只存正文摘要和固定类别；真实买家消息、平台标识及原始异常均不进入探针审计。
    return AuditLog(
        store_id=store_id,
        actor_type="system",
        action="webhook.retry_probe",
        resource_type="webhook_event",
        resource_id=event.id if event is not None else None,
        result=result,
        after_data={"payload_sha256": payload_hash, "mode": mode},
    )


async def _maybe_force_probe_503(
    session: AsyncSession,
    *,
    platform: str,
    payload: dict[str, object],
    payload_hash: str,
    channel: ChannelAccount,
    phase: str,
    event: WebhookEvent | None = None,
) -> None:
    settings = get_settings()
    if not _probe_matches(payload, platform) or settings.g2_webhook_probe_mode != phase:
        return
    if channel.store_id != settings.g2_webhook_probe_store_id:
        return
    marker = f"{payload_hash}:{channel.id}"
    # Redis 的 NX 使多副本/并发通知也只能命中一次；配置的绝对失效时间防止 TTL 后再次武装。
    if not await redis_client.set(_probe_marker_key(), marker, nx=True, ex=86400):
        return
    session.add(
        _probe_audit(store_id=channel.store_id, event=event, payload_hash=payload_hash, result="forced_503", mode=phase)
    )
    await session.commit()
    raise AppError(ErrorCode.THIRD_PARTY_ERROR, "Webhook 暂时不可用", 503)


async def _maybe_audit_probe_redelivery(
    session: AsyncSession,
    *,
    platform: str,
    payload: dict[str, object],
    payload_hash: str,
    event: WebhookEvent,
) -> None:
    settings = get_settings()
    if not _probe_matches(payload, platform, check_expiry=False):
        return
    if settings.g2_webhook_probe_store_id is None:
        return
    marker = await redis_client.get(_probe_marker_key())
    if marker != f"{payload_hash}:{event.channel_account_id}":
        return
    # 收到同一已验签正文后只留一条配对审计；是否属于官方重投仍须现场来源证据。
    audit_key = f"{_probe_marker_key()}:redelivered"
    if not await redis_client.set(audit_key, "1", nx=True, ex=86400):
        return
    session.add(
        _probe_audit(
            store_id=settings.g2_webhook_probe_store_id,
            event=event,
            payload_hash=payload_hash,
            result="redelivered",
            mode=settings.g2_webhook_probe_mode,
        )
    )
    await session.commit()


async def receive_webhook(
    session: AsyncSession,
    platform: str,
    raw_body: bytes,
    payload: dict[str, object],
    headers: dict[str, str],
) -> WebhookAccepted:
    """验证后原子保存事件；重复事件稳定返回成功。"""
    adapter = get_platform_adapter(platform)
    if not adapter.verify_webhook(raw_body, headers):
        # 先验签再查询或插入：伪造 ID 不能占用唯一键，阻断稍后的官方投递。
        raise AppError(ErrorCode.TOKEN_INVALID, "Webhook 签名无效", 401)
    event_id = stable_event_id(payload, raw_body)
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    existing = await session.scalar(
        select(WebhookEvent).where(
            WebhookEvent.platform == platform,
            WebhookEvent.external_event_id == event_id,
        )
    )
    if existing is not None:
        receipt = _duplicate_webhook_receipt(existing, event_id, payload_hash)
        await _maybe_audit_probe_redelivery(
            session, platform=platform, payload=payload, payload_hash=payload_hash, event=existing
        )
        return receipt

    external_store_id = webhook_external_store_id(payload)
    channel = await session.scalar(
        select(ChannelAccount).where(
            ChannelAccount.platform == platform,
            ChannelAccount.external_store_id == external_store_id,
        )
    )
    if channel is None:
        # 未绑定店铺的通知不得留下客户载荷或占用 ID，稍后授权后可正常重投。
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "平台店铺未授权", 404)
    await _maybe_force_probe_503(
        session,
        platform=platform,
        payload=payload,
        payload_hash=payload_hash,
        channel=channel,
        phase="before_commit_503",
    )
    event = WebhookEvent(
        platform=platform,
        channel_account_id=channel.id,
        external_event_id=event_id,
        event_type=webhook_event_type(platform, payload),
        signature_valid=True,
        payload_hash=payload_hash,
        raw_payload=payload,
        status="received",
        error_code=None,
        received_at=datetime.now(UTC),
    )
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # 并发插入失败后重新读取事件；没有同键事件时保留原完整性错误。
        existing = await session.scalar(
            select(WebhookEvent).where(
                WebhookEvent.platform == platform,
                WebhookEvent.external_event_id == event_id,
            )
        )
        if existing is None:
            raise
        receipt = _duplicate_webhook_receipt(existing, event_id, payload_hash)
        await _maybe_audit_probe_redelivery(
            session, platform=platform, payload=payload, payload_hash=payload_hash, event=existing
        )
        return receipt
    await _maybe_force_probe_503(
        session,
        platform=platform,
        payload=payload,
        payload_hash=payload_hash,
        channel=channel,
        phase="after_commit_503",
        event=event,
    )
    await _maybe_audit_probe_redelivery(
        session, platform=platform, payload=payload, payload_hash=payload_hash, event=event
    )
    return WebhookAccepted(event_id=event_id, duplicate=False, accepted=True)


async def _upsert_customer(
    session: AsyncSession,
    store_id: uuid.UUID,
    platform: str,
    data: CustomerPayload | None,
) -> Customer | None:
    """按店铺、平台和外部客户 ID 幂等更新客户。"""
    if data is None:
        return None
    external_id = str(data.external_id)
    customer = await session.scalar(
        select(Customer).where(
            Customer.store_id == store_id,
            Customer.platform == platform,
            Customer.external_customer_id == external_id,
        )
    )
    if customer is None:
        customer = Customer(store_id=store_id, platform=platform, external_customer_id=external_id)
        session.add(customer)
    # 新消息通知可不带昵称；缺失字段不能清空会话同步得到的买家名称。
    if data.name is not None:
        customer.name = data.name
    customer.email = data.email
    customer.avatar = data.avatar
    customer.last_seen_at = datetime.now(UTC)
    await session.flush()
    return customer


async def _process_message(
    session: AsyncSession,
    event: WebhookEvent,
    channel: ChannelAccount,
    normalized: MessageCreatedEvent,
) -> None:
    """幂等创建客户、会话和入站消息。"""
    customer = await _upsert_customer(session, channel.store_id, event.platform, normalized.customer)
    assert customer is not None
    conversation = await session.scalar(
        select(Conversation)
        .where(
            Conversation.store_id == channel.store_id,
            Conversation.external_conversation_id == normalized.external_conversation_id,
        )
        .with_for_update()
    )
    if conversation is None:
        conversation = Conversation(
            store_id=channel.store_id,
            customer_id=customer.id,
            platform=event.platform,
            external_conversation_id=normalized.external_conversation_id,
        )
        session.add(conversation)
        await session.flush()
    existing = await session.scalar(
        select(Message).where(
            Message.platform == event.platform,
            Message.external_message_id == normalized.external_message_id,
        )
    )
    if existing is not None:
        return
    message = Message(
        store_id=channel.store_id,
        conversation_id=conversation.id,
        customer_id=customer.id,
        platform=event.platform,
        external_message_id=normalized.external_message_id,
        role="user",
        direction="inbound",
        content=normalized.content,
        language=normalized.language,
        status="received",
        raw_payload={},
        created_at=normalized.created_at,
    )
    session.add(message)
    await session.flush()
    if conversation.last_message_at is None or normalized.created_at >= conversation.last_message_at:
        conversation.last_message_id = message.id
        conversation.last_message_at = normalized.created_at
    if reopen_on_new_buyer_message(conversation, normalized.created_at):
        session.add(
            AuditLog(
                store_id=channel.store_id,
                actor_type="system",
                action="conversation.reopen.inbound",
                resource_type="conversation",
                resource_id=conversation.id,
                after_data={"status": "active"},
                result="succeeded",
            )
        )
    conversation.unread_count += 1
    if get_settings().auto_reply_enabled:
        config = await find_enabled_config(session, channel.store_id)
        if config is not None:
            session.add(
                AgentTask(
                    store_id=channel.store_id,
                    agent_config_id=config.id,
                    conversation_id=conversation.id,
                    trigger_message_id=message.id,
                    trace_id=str(event.id),
                )
            )


async def _process_order(
    session: AsyncSession,
    event: WebhookEvent,
    channel: ChannelAccount,
    normalized: OrderUpdatedEvent,
) -> None:
    """幂等更新订单及商品快照。"""
    customer = await _upsert_customer(session, channel.store_id, event.platform, normalized.customer)
    order = await session.scalar(
        select(Order).where(
            Order.store_id == channel.store_id,
            Order.platform == event.platform,
            Order.external_order_id == normalized.external_order_id,
        )
    )
    if order is None:
        order = Order(
            store_id=channel.store_id,
            platform=event.platform,
            external_order_id=normalized.external_order_id,
            currency=normalized.currency,
            status=normalized.status,
        )
        session.add(order)
        await session.flush()
    order.customer_id = customer.id if customer else None
    order.status = normalized.status
    order.payment_status = normalized.payment_status
    order.fulfillment_status = normalized.fulfillment_status
    order.currency = normalized.currency
    order.total_amount = normalized.total_amount
    order.tracking_number = normalized.tracking_number
    order.tracking_status = normalized.tracking_status
    order.ordered_at = normalized.ordered_at
    await session.execute(delete(OrderItem).where(OrderItem.order_id == order.id))
    for item in normalized.items:
        session.add(
            OrderItem(
                order_id=order.id,
                external_item_id=item.external_item_id,
                sku=item.sku,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=Decimal(item.quantity) * item.unit_price,
                raw_payload={},
            )
        )


async def _process_review(
    session: AsyncSession,
    event: WebhookEvent,
    channel: ChannelAccount,
    normalized: ReviewUpdatedEvent,
) -> None:
    """幂等更新客户评价；评分改善后营销 Worker 会标记转化。"""
    customer = await _upsert_customer(session, channel.store_id, event.platform, normalized.customer)
    order = None
    if normalized.external_order_id:
        order = await session.scalar(
            select(Order).where(
                Order.store_id == channel.store_id,
                Order.platform == event.platform,
                Order.external_order_id == normalized.external_order_id,
            )
        )
    review = await session.scalar(
        select(CustomerReview).where(
            CustomerReview.store_id == channel.store_id,
            CustomerReview.platform == event.platform,
            CustomerReview.external_review_id == normalized.external_review_id,
        )
    )
    if review is None:
        review = CustomerReview(
            store_id=channel.store_id,
            platform=event.platform,
            external_review_id=normalized.external_review_id,
            reviewed_at=normalized.reviewed_at,
        )
        session.add(review)
    review.customer_id = customer.id if customer else None
    review.order_id = order.id if order else None
    review.rating = normalized.rating
    review.content = normalized.content
    review.reviewed_at = normalized.reviewed_at
    review.raw_payload = {}


async def _process_tiktok_authorization(
    session: AsyncSession,
    event: WebhookEvent,
    channel: ChannelAccount,
    normalized: TikTokAuthorizationLifecycleEvent,
) -> None:
    """处理卖家撤销和到期提醒，确保失效凭证不会继续被 Worker 使用。"""
    if normalized.action == "deauthorized":
        channel.status = "disconnected"
        channel.access_token_ref = f"revoked://{channel.id}"
        channel.refresh_token_ref = None
        channel.token_expires_at = None
        channel.metadata_json = {
            key: value for key, value in channel.metadata_json.items() if key not in {"shop_cipher", "open_id_hash"}
        }
        channel.metadata_json = {**channel.metadata_json, "oauth_status": "deauthorized"}
        audit_action = "channel.deauthorized"
    else:
        channel.metadata_json = {
            **channel.metadata_json,
            "oauth_status": "reauthorization_required",
            "authorization_expires_at": normalized.expiration_time.isoformat() if normalized.expiration_time else None,
        }
        audit_action = "channel.authorization_expiring"
    session.add(
        AuditLog(
            store_id=channel.store_id,
            actor_type="job",
            action=audit_action,
            resource_type="channel_account",
            resource_id=channel.id,
            request_id=normalized.event_id[:100],
            result="succeeded",
            after_data={"platform": "tiktok", "oauth_status": channel.metadata_json["oauth_status"]},
        )
    )
    event.processed_at = datetime.now(UTC)


async def claim_and_process_one(session: AsyncSession, max_retries: int) -> bool:
    """使用 SKIP LOCKED 认领一个事件并独立提交处理结果。"""
    event = await session.scalar(
        select(WebhookEvent)
        .where(WebhookEvent.status.in_(["received", "failed"]), WebhookEvent.retry_count < max_retries)
        .order_by(WebhookEvent.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if event is None:
        return False
    event_id = event.id
    event.status = "processing"
    await session.flush()
    try:
        if event.channel_account_id is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "渠道账号不存在", 404)
        channel = await session.get(ChannelAccount, event.channel_account_id)
        if channel is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "渠道账号不存在", 404)
        normalized = await get_platform_adapter(event.platform).resolve_webhook_event(channel, event.raw_payload)
        if normalized is None:
            # 未订阅或尚未实现的官方主题只保留原始事件和摘要，不猜测字段含义。
            event.status = "ignored"
            event.error_code = "UNSUPPORTED_EVENT_TYPE"
            event.processed_at = datetime.now(UTC)
            await session.commit()
            return True
        if isinstance(normalized, MessageCreatedEvent):
            await _process_message(session, event, channel, normalized)
        elif isinstance(normalized, OrderUpdatedEvent):
            await _process_order(session, event, channel, normalized)
        elif isinstance(normalized, ReviewUpdatedEvent):
            await _process_review(session, event, channel, normalized)
        else:
            await _process_tiktok_authorization(session, event, channel, normalized)
        event.status = "succeeded"
        event.error_code = None
        event.processed_at = datetime.now(UTC)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        failed = await session.get(WebhookEvent, event_id, with_for_update=True)
        if failed is not None:
            failed.retry_count += 1
            failed.status = "failed"
            failed.error_code = exc.code.value if isinstance(exc, AppError) else type(exc).__name__[:100]
            await session.commit()
    return True


async def cleanup_processed_payloads(session: AsyncSession, retention_days: int) -> int:
    """清空超过保留期的成功载荷正文，摘要与审计字段继续保留。"""
    threshold = datetime.now(UTC) - timedelta(days=retention_days)
    result = await session.execute(
        update(WebhookEvent)
        .where(
            WebhookEvent.status == "succeeded",
            WebhookEvent.processed_at < threshold,
            WebhookEvent.raw_payload != {},
        )
        .values(raw_payload={})
    )
    await session.commit()
    rowcount = getattr(result, "rowcount", 0)
    return rowcount if isinstance(rowcount, int) else 0
