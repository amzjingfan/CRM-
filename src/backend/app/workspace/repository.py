"""工作台租户安全查询。"""

import uuid

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.orders.models import Order, OrderItem


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
    search_scope: str = "all",
    search_terms: tuple[str, ...] = (),
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
    if search_terms:
        conditions.append(or_(*(_search_term_condition(search_scope, term) for term in search_terms)))
    total = (
        await session.scalar(
            select(func.count())
            .select_from(Conversation)
            .join(Customer, and_(Customer.id == Conversation.customer_id, Customer.store_id == Conversation.store_id))
            .where(*conditions)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(Conversation, Customer, Message)
            .join(Customer, and_(Customer.id == Conversation.customer_id, Customer.store_id == Conversation.store_id))
            .outerjoin(
                Message,
                and_(
                    Message.id == Conversation.last_message_id,
                    Message.conversation_id == Conversation.id,
                    Message.store_id == Conversation.store_id,
                ),
            )
            .where(*conditions)
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [(conversation, customer, message) for conversation, customer, message in rows], int(total)


async def unread_message_total(session: AsyncSession, store_ids: set[uuid.UUID]) -> int:
    """汇总当前坐席可访问且未关闭会话的未读消息数，不受列表分页和搜索影响。"""
    if not store_ids:
        return 0
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(Conversation.unread_count), 0)).where(
                Conversation.store_id.in_(store_ids), Conversation.status != "closed"
            )
        )
        or 0
    )


def _search_term_condition(scope: str, term: str) -> ColumnElement[bool]:
    """把买家、订单、物流和商品匹配约束到同一店铺、平台及买家。"""
    escaped = term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"

    def matches(column: InstrumentedAttribute[str] | InstrumentedAttribute[str | None]) -> ColumnElement[bool]:
        return func.lower(column).like(pattern, escape="\\")

    buyer = matches(Customer.name)
    order_scope = (
        Order.store_id == Conversation.store_id,
        Order.customer_id == Conversation.customer_id,
        Order.platform == Conversation.platform,
    )
    order_number = select(Order.id).where(*order_scope, matches(Order.external_order_id)).exists()
    tracking = select(Order.id).where(*order_scope, matches(Order.tracking_number)).exists()
    product = (
        select(OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            *order_scope,
            or_(matches(OrderItem.product_name), matches(OrderItem.product_id), matches(OrderItem.sku)),
        )
        .exists()
    )
    if scope == "buyer":
        return buyer
    if scope == "order":
        return order_number
    if scope == "tracking":
        return tracking
    if scope == "product":
        return product
    preview = (
        select(Message.id)
        .where(
            Message.id == Conversation.last_message_id,
            Message.conversation_id == Conversation.id,
            Message.store_id == Conversation.store_id,
            matches(Message.content),
        )
        .correlate(Conversation)
        .exists()
    )
    return or_(buyer, order_number, tracking, product, preview)


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
