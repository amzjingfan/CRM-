"""已认证坐席读取当前会话的自动建议预演结果。"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentTask
from app.auth.store_access import allowed_store_ids
from app.conversations.models import Conversation
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


class AutoPreviewView(BaseModel):
    task_id: uuid.UUID
    trigger_message_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    status: str
    mode: Literal["preview", "automation"] = "preview"
    state: Literal["waiting", "generating", "delayed", "review_required", "failed"] = "review_required"
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
            AgentTask.mode.in_(("preview", "automation")),
        )
        .order_by(AgentTask.created_at.desc(), AgentTask.id.desc())
        .limit(1)
    )
    if task is None or task.status in {"queued", "succeeded", "cancelled"}:
        return None
    state: Literal["waiting", "generating", "delayed", "review_required", "failed"] = "review_required"
    if task.status == "pending":
        state = "waiting"
    elif task.status == "processing":
        updated = task.updated_at.replace(tzinfo=UTC) if task.updated_at.tzinfo is None else task.updated_at
        # 只说明耗时超过正常生成预算，不伪造任务失败或取消仍有效的Worker。
        state = (
            "delayed"
            if (datetime.now(UTC) - updated).total_seconds() > get_settings().agent_debug_timeout_seconds
            else "generating"
        )
    elif task.status == "failed":
        state = "failed"
    return AutoPreviewView(
        task_id=task.id,
        trigger_message_id=task.trigger_message_id,
        agent_run_id=task.agent_run_id,
        status=task.status,
        mode="automation" if task.mode == "automation" else "preview",
        state=state,
        content=task.preview_content,
        processed_at=task.processed_at,
    )
