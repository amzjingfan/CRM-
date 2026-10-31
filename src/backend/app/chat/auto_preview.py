"""已认证坐席读取当前会话的自动建议预演结果。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentTask
from app.auth.store_access import allowed_store_ids
from app.conversations.models import Conversation
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


class AutoPreviewView(BaseModel):
    task_id: uuid.UUID
    trigger_message_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    status: str
    content: str | None
    processed_at: datetime | None
    send_performed: Literal[False] = False


async def get_auto_preview(session: AsyncSession, user: User, conversation_id: uuid.UUID) -> AutoPreviewView | None:
    stores = await allowed_store_ids(session, user, "workspace.view")
    if not stores:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.store_id.in_(stores))
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    task = await session.scalar(
        select(AgentTask)
        .where(
            AgentTask.store_id == conversation.store_id,
            AgentTask.conversation_id == conversation.id,
            AgentTask.mode == "preview",
        )
        .order_by(AgentTask.created_at.desc(), AgentTask.id.desc())
        .limit(1)
    )
    if task is None:
        return None
    return AutoPreviewView(
        task_id=task.id,
        trigger_message_id=task.trigger_message_id,
        agent_run_id=task.agent_run_id,
        status=task.status,
        content=task.preview_content,
        processed_at=task.processed_at,
    )
