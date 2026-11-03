"""为可核验且仍在平台窗口内的会话补齐订单，不复制地址或原始平台载荷。"""

import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.orders.models import Order
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.workspace.sidebar import (
    SidebarOrder,
    _live_order_view,
    _tiktok_client,
    _verified_buyer_user_id,
)

from .authorization import bound_agent, policy_authorizer, verified_remote_window
from .models import LogisticsNotificationPolicy

logger = logging.getLogger(__name__)


async def read_verified_buyer_orders(session: AsyncSession, conversation: Conversation) -> tuple[SidebarOrder, ...]:
    client = await _tiktok_client(session, conversation.store_id)
    buyer_id = await _verified_buyer_user_id(session, conversation, client)
    orders: list[SidebarOrder] = []
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    token: str | None = None
    for _ in range(20):
        page, next_token, _ = await client.search_orders(page_size=100, page_token=token, buyer_user_id=buyer_id)
        if any(item.user_id != buyer_id or item.id in seen_ids for item in page):
            raise ValueError("verified_buyer_orders_invalid")
        if len({item.id for item in page}) != len(page):
            raise ValueError("verified_buyer_orders_invalid")
        seen_ids.update(item.id for item in page)
        orders.extend(_live_order_view(item) for item in page)
        if not next_token:
            return tuple(orders)
        if next_token in seen_tokens:
            raise ValueError("verified_buyer_orders_pagination_invalid")
        seen_tokens.add(next_token)
        token = next_token
    raise ValueError("verified_buyer_orders_limit_exceeded")


async def synchronize_conversation_orders(
    session: AsyncSession, user: User, conversation: Conversation, settings: Settings
) -> int:
    grant, identity, window = await verified_remote_window(session, settings, conversation)
    if not (grant and identity and window):
        return 0
    orders = await read_verified_buyer_orders(session, conversation)
    count = 0
    for order in orders:
        if order.total_amount is None or not order.currency:
            continue
        statement = insert(Order).values(
            id=uuid.uuid4(),
            store_id=conversation.store_id,
            customer_id=conversation.customer_id,
            platform="tiktok",
            external_order_id=order.external_order_id,
            status=order.status,
            payment_status=order.payment_status,
            currency=order.currency,
            total_amount=order.total_amount,
            ordered_at=order.ordered_at,
            raw_payload={},
        )
        persisted = await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_order_store_platform_external",
                set_={
                    "customer_id": conversation.customer_id,
                    "status": statement.excluded.status,
                    "payment_status": statement.excluded.payment_status,
                    "currency": statement.excluded.currency,
                    "total_amount": statement.excluded.total_amount,
                    "ordered_at": statement.excluded.ordered_at,
                },
                where=or_(Order.customer_id.is_(None), Order.customer_id == conversation.customer_id),
            ).returning(Order.id)
        )
        if persisted.scalar_one_or_none() is None:
            raise ValueError("verified_order_ownership_conflict")
        count += 1
    return count


async def discover_eligible_orders(
    sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]], settings: Settings
) -> bool:
    """逐店持久预占补查周期；失效身份、撤权及无窗口会话都不读取买家订单。"""
    if not settings.logistics_notifications_enabled or not settings.real_tiktok_read_enabled:
        return False
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        policy = await session.scalar(
            select(LogisticsNotificationPolicy)
            .where(
                LogisticsNotificationPolicy.enabled.is_(True),
                or_(
                    LogisticsNotificationPolicy.last_scan_at.is_(None),
                    LogisticsNotificationPolicy.last_scan_at
                    <= now - timedelta(seconds=settings.logistics_notification_poll_seconds),
                ),
            )
            .order_by(
                LogisticsNotificationPolicy.last_scan_at.asc().nulls_first(), LogisticsNotificationPolicy.store_id
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if policy is None:
            return False
        store_id, revision = policy.store_id, policy.revision
        policy.last_scan_at = now
    async with sessions() as session:
        policy = await session.get(LogisticsNotificationPolicy, store_id)
        if policy is None or not policy.enabled or policy.revision != revision:
            return False
        user = await policy_authorizer(session, policy)
        if user is None or await bound_agent(session, store_id, policy.agent_id) is None:
            return False
        actor_id = user.id
        conversations = (
            await session.execute(
                select(Conversation.id, Conversation.customer_id)
                .where(
                    Conversation.store_id == store_id,
                    Conversation.platform == "tiktok",
                    Conversation.status != "closed",
                    select(Message.id)
                    .where(
                        Message.store_id == store_id,
                        Message.conversation_id == Conversation.id,
                        Message.customer_id == Conversation.customer_id,
                        Message.direction == "inbound",
                        Message.role == "user",
                    )
                    .exists(),
                )
                .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id)
            )
        ).all()
    seen_customers: set[uuid.UUID] = set()
    count = failures = 0
    for conversation_id, customer_id in conversations:
        if customer_id in seen_customers:
            continue
        # 每个买家独立提交；不能跨下一次平台查询继续持有前一笔订单的写锁。
        async with sessions() as session:
            policy = await session.get(LogisticsNotificationPolicy, store_id)
            if policy is None or not policy.enabled or policy.revision != revision:
                break
            user = await policy_authorizer(session, policy)
            if user is None or await bound_agent(session, store_id, policy.agent_id) is None:
                break
            conversation = await session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.store_id == store_id,
                    Conversation.customer_id == customer_id,
                    Conversation.platform == "tiktok",
                    Conversation.status != "closed",
                )
            )
            if conversation is None:
                continue
            try:
                imported = await synchronize_conversation_orders(session, user, conversation, settings)
                await session.commit()
                count += imported
                if imported:
                    seen_customers.add(customer_id)
            except Exception as error:
                await session.rollback()
                failures += 1
                logger.warning("logistics_order_discovery_failed", extra={"error_type": type(error).__name__})
    async with sessions() as session:
        session.add(
            AuditLog(
                store_id=store_id,
                actor_type="job",
                actor_id=actor_id,
                action="logistics.notification.discover_orders",
                resource_type="store",
                resource_id=store_id,
                after_data={"verified_order_count": count, "failed_conversation_count": failures},
                result="failed" if failures else "succeeded",
            )
        )
        await session.commit()
    return bool(conversations)
