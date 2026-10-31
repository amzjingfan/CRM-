"""在同一数据库读事务内冻结会话、Agent 版本和知识文件水位。"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.repository import PublishedAgent
from app.agents.memory.models import AgentSessionMemory
from app.conversations.models import Conversation, Message
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.shared.exceptions.errors import AppError, ErrorCode


@dataclass(frozen=True, slots=True)
class FileVersionRef:
    file_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    store_id: uuid.UUID
    conversation_id: uuid.UUID
    customer_id: uuid.UUID
    trigger_message_id: uuid.UUID
    trigger_created_at: datetime
    message_ids: tuple[uuid.UUID, ...]
    published_agents: tuple[PublishedAgent, ...]
    file_versions: tuple[FileVersionRef, ...]
    memory_revision: int
    frozen_at: datetime
    snapshot_hash: str
    debug_without_conversation: bool = False

    def low_sensitive_reference(self) -> dict[str, object]:
        """运行日志只保存水位、版本引用和摘要，不复制消息正文。"""
        return {
            "trigger_message_id": str(self.trigger_message_id),
            "message_count": len(self.message_ids),
            "message_ids_sha256": hashlib.sha256(
                json.dumps([str(item) for item in self.message_ids]).encode("utf-8")
            ).hexdigest(),
            "agent_versions": [[str(item.id), item.config_version] for item in self.published_agents],
            "file_versions": [[str(item.file_id), item.version_number] for item in self.file_versions],
            "memory_revision": self.memory_revision,
            "snapshot_hash": self.snapshot_hash,
        }


async def freeze_run_context(
    session: AsyncSession,
    *,
    store_id: uuid.UUID,
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID,
    published_agents: tuple[PublishedAgent, ...],
    memory_revision: int,
) -> RunSnapshot:
    """触发后到达的消息不进入本次运行；外店 ID 始终返回不存在。"""
    if memory_revision < 0 or any(item.store_id != store_id for item in published_agents):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 快照范围无效", 422)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.store_id == store_id)
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    trigger = await session.scalar(
        select(Message).where(
            Message.id == trigger_message_id,
            Message.store_id == store_id,
            Message.conversation_id == conversation_id,
            Message.customer_id == conversation.customer_id,
            Message.direction == "inbound",
        )
    )
    if trigger is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "触发消息不存在", 404)
    message_ids = tuple(
        (
            await session.scalars(
                select(Message.id)
                .where(
                    Message.store_id == store_id,
                    Message.conversation_id == conversation_id,
                    or_(
                        Message.created_at < trigger.created_at,
                        and_(Message.created_at == trigger.created_at, Message.id <= trigger.id),
                    ),
                )
                .order_by(Message.created_at, Message.id)
            )
        ).all()
    )
    if trigger.id not in message_ids:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "触发消息水位已变化", 409)

    file_refs = await _approved_file_refs(session, store_id, published_agents)
    frozen_at = datetime.now(UTC)
    snapshot_data: dict[str, object] = {
        "store_id": str(store_id),
        "conversation_id": str(conversation_id),
        "customer_id": str(conversation.customer_id),
        "trigger_message_id": str(trigger.id),
        "message_ids": [str(item) for item in message_ids],
        "agent_versions": [
            [
                str(item.id),
                item.config_version,
                item.prompt_hash,
                item.model_provider,
                item.model_name,
                list(item.tool_names),
                list(item.file_ids),
                item.reply_profile.model_dump(mode="json") if item.reply_profile is not None else None,
            ]
            for item in published_agents
        ],
        "file_versions": [[str(item.file_id), str(item.version_id)] for item in file_refs],
        "memory_revision": memory_revision,
    }
    digest = hashlib.sha256(json.dumps(snapshot_data, sort_keys=True).encode("utf-8")).hexdigest()
    return RunSnapshot(
        store_id=store_id,
        conversation_id=conversation_id,
        customer_id=conversation.customer_id,
        trigger_message_id=trigger.id,
        trigger_created_at=trigger.created_at,
        message_ids=message_ids,
        published_agents=published_agents,
        file_versions=file_refs,
        memory_revision=memory_revision,
        frozen_at=frozen_at,
        snapshot_hash=digest,
    )


async def _approved_file_refs(
    session: AsyncSession, store_id: uuid.UUID, published_agents: tuple[PublishedAgent, ...]
) -> tuple[FileVersionRef, ...]:
    bound_ids = {uuid.UUID(item) for agent in published_agents for item in agent.file_ids}
    file_refs: tuple[FileVersionRef, ...] = ()
    if bound_ids:
        rows = (
            await session.execute(
                select(KnowledgeFile.id, KnowledgeFileVersion.id, KnowledgeFileVersion.version_number)
                .join(
                    KnowledgeFileVersion,
                    and_(
                        KnowledgeFileVersion.file_id == KnowledgeFile.id,
                        KnowledgeFileVersion.store_id == KnowledgeFile.store_id,
                        KnowledgeFileVersion.version_number == KnowledgeFile.active_version_number,
                    ),
                )
                .where(
                    KnowledgeFile.store_id == store_id,
                    KnowledgeFile.id.in_(bound_ids),
                    KnowledgeFile.archived_at.is_(None),
                    KnowledgeFile.deleted_at.is_(None),
                    KnowledgeFileVersion.status == "ready",
                    KnowledgeFileVersion.publication_approval == "approved_for_internal_review",
                    KnowledgeFileVersion.approved_by.is_not(None),
                    KnowledgeFileVersion.approved_at.is_not(None),
                )
                .order_by(KnowledgeFile.id)
            )
        ).all()
        file_refs = tuple(FileVersionRef(file_id=row[0], version_id=row[1], version_number=row[2]) for row in rows)
    return file_refs


async def freeze_debug_context(
    session: AsyncSession,
    *,
    store_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    published_agents: tuple[PublishedAgent, ...],
) -> RunSnapshot:
    """调试输入不写客户消息；无会话时使用一次性隔离身份，仍冻结文件审批版本。"""
    if any(agent.store_id != store_id for agent in published_agents):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 快照范围无效", 422)
    conversation = None
    message_ids: tuple[uuid.UUID, ...] = ()
    memory_revision = 0
    if conversation_id is not None:
        conversation = await session.scalar(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.store_id == store_id)
        )
        if conversation is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
        message_ids = tuple(
            (
                await session.scalars(
                    select(Message.id)
                    .where(
                        Message.store_id == store_id,
                        Message.conversation_id == conversation_id,
                    )
                    .order_by(Message.created_at, Message.id)
                )
            ).all()
        )
        memory_revision = (
            await session.scalar(
                select(AgentSessionMemory.revision).where(
                    AgentSessionMemory.store_id == store_id,
                    AgentSessionMemory.conversation_id == conversation_id,
                    AgentSessionMemory.customer_id == conversation.customer_id,
                )
            )
            or 0
        )
    customer_id = conversation.customer_id if conversation is not None else uuid.uuid4()
    scoped_conversation_id = conversation_id or uuid.uuid4()
    trigger_id = message_ids[-1] if message_ids else uuid.uuid4()
    file_refs = await _approved_file_refs(session, store_id, published_agents)
    frozen_at = datetime.now(UTC)
    snapshot_data: dict[str, object] = {
        "store_id": str(store_id),
        "conversation_id": str(scoped_conversation_id),
        "customer_id": str(customer_id),
        "trigger_message_id": str(trigger_id),
        "message_ids": [str(item) for item in message_ids],
        "agent_versions": [
            [
                str(item.id),
                item.config_version,
                item.prompt_hash,
                item.model_provider,
                item.model_name,
                list(item.tool_names),
                list(item.file_ids),
                item.reply_profile.model_dump(mode="json") if item.reply_profile is not None else None,
            ]
            for item in published_agents
        ],
        "file_versions": [[str(item.file_id), str(item.version_id)] for item in file_refs],
        "memory_revision": memory_revision,
        "debug_without_conversation": conversation is None,
    }
    digest = hashlib.sha256(json.dumps(snapshot_data, sort_keys=True).encode("utf-8")).hexdigest()
    return RunSnapshot(
        store_id=store_id,
        conversation_id=scoped_conversation_id,
        customer_id=customer_id,
        trigger_message_id=trigger_id,
        trigger_created_at=frozen_at,
        message_ids=message_ids,
        published_agents=published_agents,
        file_versions=file_refs,
        memory_revision=memory_revision,
        frozen_at=frozen_at,
        snapshot_hash=digest,
        debug_without_conversation=conversation is None,
    )
