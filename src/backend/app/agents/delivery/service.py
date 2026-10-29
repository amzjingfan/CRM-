"""工作台交付入口：当前会话授权、原消息绑定和已有人工发送工具链。"""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.delivery.batches import BatchRunner
from app.agents.delivery.contracts import CardPart, ReplyBatchRequest, ReplyBatchView, ReplyPart, TextPart
from app.agents.delivery.repository import SqlBatchStore
from app.agents.tools.access import current_permissions
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.conversations.models import Message
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace.delivery_errors import DeliveryNotStarted
from app.workspace.repository import find_conversation
from app.workspace.schemas import MessageView


async def deliver_reviewed_batch(
    session: AsyncSession, user: User, session_id: uuid.UUID, payload: ReplyBatchRequest, key: str
) -> ReplyBatchView:
    from app.workspace import service as workspace

    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, user))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.status == "closed":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请重新打开", 409)
    permissions = await current_permissions(session, user, conversation.store_id)
    if "workspace.reply" not in permissions:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有回复权限", 403)
    if payload.trigger_message_id:
        trigger = await session.scalar(
            select(Message.id).where(
                Message.id == payload.trigger_message_id,
                Message.store_id == conversation.store_id,
                Message.conversation_id == conversation.id,
                Message.role == "user",
                Message.direction == "inbound",
            )
        )
        if trigger is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "原始买家消息不存在", 404)
    for part in payload.parts:
        if isinstance(part, CardPart):
            if "orders.view" not in permissions:
                raise AppError(ErrorCode.PERMISSION_DENIED, "没有订单查看权限", 403)
            cards = await workspace.get_logistics_card_preview(session, user, session_id, part.order_id)
            if not any(item.card.package_id == part.package_id for item in cards):
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "包裹不属于当前买家的订单", 404)

    async def send(part: ReplyPart, attempt_key: str) -> MessageView:
        try:
            current = await current_permissions(session, user, conversation.store_id)
        except AppError as error:
            raise DeliveryNotStarted(error.code, error.message, error.status_code) from error
        if "workspace.reply" not in current or (isinstance(part, CardPart) and "orders.view" not in current):
            raise DeliveryNotStarted(ErrorCode.PERMISSION_DENIED, "发送权限已撤销", 403)
        if isinstance(part, TextPart):
            return await workspace.send_agent_message(
                session, user, session_id, part.content, attempt_key, confirmed=payload.confirmed
            )
        return await workspace.send_agent_logistics_card(
            session, user, session_id, part.order_id, part.package_id, attempt_key, confirmed=payload.confirmed
        )

    scope = hashlib.sha256(f"{conversation.store_id}:{session_id}:{user.id}".encode()).hexdigest()
    store = SqlBatchStore(session, conversation.store_id, session_id, user.id)
    result = await BatchRunner(store, send).run(scope, key, payload)
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.reply_batch.preview" if payload.preview_only else "agent.reply_batch.deliver",
            resource_type="agent_reply_batch",
            resource_id=result.id,
            result=result.status,
            after_data={"part_count": len(payload.parts), "preview_only": payload.preview_only},
        )
    )
    await session.commit()
    return result
