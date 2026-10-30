"""已授权 TikTok 客服会话的只读回填与增量同步。"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.conversations.workflow import reopen_on_new_buyer_message
from app.customers.models import Customer
from app.integrations.adapters import _message_content
from app.integrations.tiktok_read import TikTokConversation, TikTokConversationMessage, TikTokReadClient
from app.reception_assignment.dispatch import dispatch_conversation
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncSummary:
    """只包含低敏计数，不包含买家或消息内容。"""

    conversations: int = 0
    messages: int = 0


def _platform_time(timestamp: int) -> datetime:
    """平台秒级时间必须是可表示的正数。"""
    try:
        if isinstance(timestamp, bool) or timestamp <= 0:
            raise ValueError
        return datetime.fromtimestamp(timestamp, UTC)
    except (ValueError, OverflowError, OSError) as exc:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 消息时间无效", 502) from exc


def _message_role(sender_role: str) -> tuple[str, str]:
    roles = {
        "BUYER": ("user", "inbound"),
        "CUSTOMER_SERVICE": ("agent", "outbound"),
        "SHOP": ("agent", "outbound"),
        "ROBOT": ("assistant", "outbound"),
        "SYSTEM": ("system", "outbound"),
    }
    result = roles.get(sender_role)
    if result is None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 消息发送者类型未知", 502)
    return result


async def _persist_page(
    session: AsyncSession,
    channel: ChannelAccount,
    conversation: Conversation,
    customer: Customer,
    buyer_im_user_id: str,
    messages: list[TikTokConversationMessage],
    reopen_cutoff: datetime | None,
) -> tuple[int, datetime | None]:
    inserted = 0
    # 每页重新锁定会话，避免同步期间的人工关闭与回填互相覆盖。
    await session.refresh(conversation, with_for_update=True)
    closed_at = conversation.closed_at if conversation.status == "closed" else reopen_cutoff
    for remote in messages:
        if not remote.is_visible:
            continue
        role, direction = _message_role(remote.sender.role)
        if role == "user" and remote.sender.im_user_id != buyer_im_user_id:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 会话买家不匹配", 502)
        existing = await session.scalar(
            select(Message).where(Message.platform == "tiktok", Message.external_message_id == remote.id)
        )
        if existing is not None:
            if existing.store_id != channel.store_id or existing.conversation_id != conversation.id:
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 消息店铺或会话冲突", 502)
            message = existing
        else:
            created_at = _platform_time(remote.create_time)
            message = Message(
                store_id=channel.store_id,
                conversation_id=conversation.id,
                customer_id=customer.id if role == "user" else None,
                platform="tiktok",
                external_message_id=remote.id,
                role=role,
                direction=direction,
                message_type=remote.type.lower() if len(remote.type) <= 30 else "other",
                content=_message_content(remote.type, remote.content),
                status="received" if role == "user" else "sent",
                sent_at=created_at if direction == "outbound" else None,
                raw_payload={"delivery_mode": "real", "source": "tiktok_sync"} if role != "user" else {},
                created_at=created_at,
            )
            session.add(message)
            await session.flush()
            inserted += 1
            if role == "user":
                # 首次历史回填不制造大量未读；后续周期缺失 Webhook 时由只读同步补记新消息。
                is_new_since_sync = channel.last_sync_at is not None and created_at > channel.last_sync_at
                is_new_since_close = closed_at is not None and created_at > closed_at
                if is_new_since_sync or is_new_since_close:
                    conversation.unread_count += 1
                    if conversation.last_human_replied_at is None or created_at > conversation.last_human_replied_at:
                        if conversation.awaiting_reply_since is None or created_at < conversation.awaiting_reply_since:
                            conversation.awaiting_reply_since = created_at
                if is_new_since_close and reopen_on_new_buyer_message(conversation, created_at):
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
                if (is_new_since_sync or is_new_since_close) and conversation.awaiting_reply_since is not None:
                    await dispatch_conversation(session, conversation.id, now=datetime.now(UTC))
        if conversation.last_message_at is None or message.created_at > conversation.last_message_at:
            conversation.last_message_id = message.id
            conversation.last_message_at = message.created_at
    await session.commit()
    return inserted, closed_at


async def _sync_conversation(
    session: AsyncSession, channel: ChannelAccount, client: TikTokReadClient, remote: TikTokConversation
) -> int:
    buyers = [participant for participant in remote.participants if participant.role == "BUYER"]
    if len(buyers) != 1:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 会话买家身份缺失或不唯一", 502)
    buyer = buyers[0]
    customer = await session.scalar(
        select(Customer).where(
            Customer.store_id == channel.store_id,
            Customer.platform == "tiktok",
            Customer.external_customer_id == buyer.im_user_id,
        )
    )
    if customer is None:
        customer = Customer(store_id=channel.store_id, platform="tiktok", external_customer_id=buyer.im_user_id)
        session.add(customer)
        await session.flush()
    if buyer.nickname:
        customer.name = buyer.nickname
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.store_id == channel.store_id,
            Conversation.external_conversation_id == remote.id,
        )
    )
    if conversation is None:
        conversation = Conversation(
            store_id=channel.store_id,
            customer_id=customer.id,
            platform="tiktok",
            external_conversation_id=remote.id,
            created_at=_platform_time(remote.create_time),
        )
        session.add(conversation)
        await session.flush()
    elif conversation.platform != "tiktok" or conversation.customer_id != customer.id:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 会话店铺或买家冲突", 502)

    latest_id = remote.latest_message.id if remote.latest_message else None
    if latest_id and conversation.metadata_json.get("tiktok_latest_message_id") == latest_id:
        await session.commit()
        return 0

    inserted = 0
    reopen_cutoff: datetime | None = None
    page_token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        page, next_token, _request_id = await client.get_conversation_messages(remote.id, page_token=page_token)
        page_inserted, reopen_cutoff = await _persist_page(
            session, channel, conversation, customer, buyer.im_user_id, page, reopen_cutoff
        )
        inserted += page_inserted
        if not next_token:
            break
        if next_token in seen_tokens:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 消息分页游标重复", 502)
        seen_tokens.add(next_token)
        page_token = next_token
    if latest_id:
        conversation.metadata_json = {**conversation.metadata_json, "tiktok_latest_message_id": latest_id}
    await session.commit()
    return inserted


async def sync_tiktok_channel(session: AsyncSession, channel: ChannelAccount, client: TikTokReadClient) -> SyncSummary:
    """同步全部列表页；逐会话提交使中断后可安全重跑。"""
    if channel.platform != "tiktok" or channel.status != "connected" or "seller.customer_service" not in channel.scopes:
        raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 客服渠道未授权", 403)
    conversations = 0
    messages = 0
    page_token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        page, next_token, _request_id = await client.get_conversations(page_token=page_token)
        for remote in page:
            messages += await _sync_conversation(session, channel, client, remote)
            conversations += 1
        if not next_token:
            break
        if next_token in seen_tokens:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 会话分页游标重复", 502)
        seen_tokens.add(next_token)
        page_token = next_token
    channel.last_sync_at = datetime.now(UTC)
    await session.commit()
    return SyncSummary(conversations=conversations, messages=messages)


async def process_tiktok_conversation_sync_cycle(session: AsyncSession, settings: Settings) -> int:
    """按现有渠道逐店铺同步；单店失败不会阻止其他授权店铺。"""
    if not settings.tiktok_conversation_sync_enabled:
        return 0
    channel_ids = (
        await session.scalars(
            select(ChannelAccount.id)
            .where(ChannelAccount.platform == "tiktok", ChannelAccount.status == "connected")
            .order_by(ChannelAccount.id)
        )
    ).all()
    completed = 0
    for channel_id in channel_ids:
        channel = await session.get(ChannelAccount, channel_id)
        if channel is None:
            continue
        if "seller.customer_service" not in channel.scopes:
            continue
        try:
            await sync_tiktok_channel(session, channel, TikTokReadClient(settings, channel))
            completed += 1
        except Exception as error:
            await session.rollback()
            # 平台异常链可能包含客户消息，日志只记录固定类别。
            logger.warning(
                "tiktok_conversation_sync_failed",
                extra={"event": "tiktok_conversation_sync_failed", "error_type": type(error).__name__},
            )
    return completed
