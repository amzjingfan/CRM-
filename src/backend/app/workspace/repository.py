"""工作台租户安全查询。"""

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.orders.models import Order


def scoped_conversation_query(store_ids: set[uuid.UUID]) -> Select[tuple[Conversation]]:
    """构造必须包含租户范围的会话查询。"""
    return select(Conversation).where(Conversation.store_id.in_(store_ids))


async def find_conversation(
    session: AsyncSession, session_id: uuid.UUID, store_ids: set[uuid.UUID], *, for_update: bool = False
) -> Conversation | None:
    """按资源 ID 与允许店铺集合联合查询。"""
    if not store_ids:
        return None
    query = scoped_conversation_query(store_ids).where(Conversation.id == session_id)
    result: Conversation | None = await session.scalar(query.with_for_update() if for_update else query)
    return result


async def list_conversations(
    session: AsyncSession,
    store_ids: set[uuid.UUID],
    user_id: uuid.UUID,
    filter_name: str,
    platform: str | None,
    store_id: uuid.UUID | None,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[Conversation, Customer, Message | None]], int]:
    """稳定分页查询会话和最后一条消息。"""
    if not store_ids:
        return [], 0
    conditions: list[ColumnElement[bool]] = [Conversation.store_id.in_(store_ids)]
    if filter_name == "unread":
        conditions.append(Conversation.unread_count > 0)
    elif filter_name == "mine":
        conditions.append(Conversation.assigned_user_id == user_id)
    elif filter_name == "starred":
        conditions.append(Conversation.is_starred.is_(True))
    if platform:
        conditions.append(Conversation.platform == platform)
    if store_id:
        conditions.append(Conversation.store_id == store_id)
    if filter_name == "closed":
        conditions.append(Conversation.status == "closed")
        if status:
            conditions.append(Conversation.status == status)
    elif status:
        conditions.append(Conversation.status == status)
    else:
        conditions.append(Conversation.status != "closed")
    total = await session.scalar(select(func.count()).select_from(Conversation).where(*conditions)) or 0
    rows = (
        await session.execute(
            select(Conversation, Customer, Message)
            .join(Customer, Customer.id == Conversation.customer_id)
            .outerjoin(Message, Message.id == Conversation.last_message_id)
            .where(*conditions)
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [(conversation, customer, message) for conversation, customer, message in rows], int(total)


async def list_messages(
    session: AsyncSession, conversation_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[Message], int]:
    """按创建时间正序分页消息，不修改未读数。"""
    total = (
        await session.scalar(
            select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
        )
        or 0
    )
    messages = list(
        (
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, Message.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return messages, int(total)


async def recent_orders(session: AsyncSession, customer_id: uuid.UUID) -> list[Order]:
    """返回客户最近五笔订单。"""
    return list(
        (
            await session.scalars(
                select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc()).limit(5)
            )
        ).all()
    )


async def find_order(session: AsyncSession, order_id: str, store_ids: set[uuid.UUID]) -> Order | None:
    """支持内部 UUID 或平台订单号，并始终限制店铺集合。"""
    if not store_ids:
        return None
    identifier: uuid.UUID | None
    try:
        identifier = uuid.UUID(order_id)
    except ValueError:
        identifier = None
    identity_condition = Order.external_order_id == order_id
    if identifier:
        identity_condition = or_(Order.id == identifier, identity_condition)
    result: Order | None = await session.scalar(select(Order).where(Order.store_id.in_(store_ids), identity_condition))
    return result
