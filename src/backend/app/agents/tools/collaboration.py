"""内部协作记录事务、幂等与授权读取。"""

import hashlib
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.runtime.snapshot import RunSnapshot
from app.agents.safety.input import prepare_untrusted_text
from app.agents.tools.access import current_permissions
from app.agents.tools.models import AgentCollaborationEntry
from app.audit.models import AuditLog
from app.conversations.models import Conversation
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


class CollaborationView(BaseModel):
    id: uuid.UUID
    kind: str
    content: str
    created_at: datetime
    agent_run_id: uuid.UUID
    is_ai_suggestion: Literal[True] = True
    send_performed: Literal[False] = False
    transfer_performed: Literal[False] = False
    model_config = {"from_attributes": True}


async def save_collaboration(
    session: AsyncSession,
    snapshot: RunSnapshot,
    run_id: uuid.UUID,
    tool_name: str,
    content: str,
    actor_id: uuid.UUID,
    trace_id: str,
) -> AgentCollaborationEntry:
    """调用方已校验当前权限；唯一约束处理并发重试，审计与写入同事务提交。"""
    text = prepare_untrusted_text(content, source="agent_draft").text
    kind = {"create_handoff_request": "handoff_request", "add_internal_note": "internal_note"}[tool_name]
    digest = hashlib.sha256(text.encode()).hexdigest()
    key = dict(
        store_id=snapshot.store_id,
        conversation_id=snapshot.conversation_id,
        agent_run_id=run_id,
        kind=kind,
        content_hash=digest,
    )
    row_id = await session.scalar(
        insert(AgentCollaborationEntry)
        .values(**key, id=uuid.uuid4(), customer_id=snapshot.customer_id, content=text, created_by=actor_id)
        .on_conflict_do_nothing(constraint="uq_agent_collaboration_replay")
        .returning(AgentCollaborationEntry.id)
    )
    if row_id is not None:
        session.add(
            AuditLog(
                store_id=snapshot.store_id,
                actor_type="agent",
                actor_id=None,
                action="agent.collaboration.create",
                resource_type="agent_collaboration",
                resource_id=row_id,
                request_id=trace_id,
                after_data={"kind": kind, "ai_suggestion": True},
                result="succeeded",
            )
        )
    row = await session.scalar(select(AgentCollaborationEntry).filter_by(**key))
    if row is None:
        raise AppError(ErrorCode.INTERNAL_ERROR, "内部记录未保存", 500)
    return row


async def list_collaboration(
    session: AsyncSession, user: User, conversation_id: uuid.UUID, offset: int = 0
) -> list[CollaborationView]:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    permissions = await current_permissions(session, user, conversation.store_id)
    if "workspace.view" not in permissions:
        raise AppError(ErrorCode.PERMISSION_DENIED, "无权读取内部协作记录", 403)
    rows = (
        await session.scalars(
            select(AgentCollaborationEntry)
            .where(
                AgentCollaborationEntry.store_id == conversation.store_id,
                AgentCollaborationEntry.conversation_id == conversation.id,
                AgentCollaborationEntry.customer_id == conversation.customer_id,
            )
            .order_by(AgentCollaborationEntry.created_at.desc(), AgentCollaborationEntry.id.desc())
            .offset(offset)
            .limit(20)
        )
    ).all()
    return [CollaborationView.model_validate(row) for row in rows]
