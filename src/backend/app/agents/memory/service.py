"""记忆候选验证、作用域读取和乐观锁提交。"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory.models import AgentSessionMemory
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.safety.input import prepare_untrusted_text
from app.agents.tools.loop import ToolObservation
from app.audit.models import AuditLog
from app.conversations.models import Conversation
from app.shared.exceptions.errors import AppError, ErrorCode


@dataclass(frozen=True, slots=True)
class MemoryFact:
    key: str
    value: str
    source_ref: str
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    summary: str
    source_message_ids: tuple[uuid.UUID, ...]
    facts: tuple[MemoryFact, ...]


@dataclass(frozen=True, slots=True)
class SessionMemoryView:
    revision: int
    summary: str
    source_message_ids: tuple[uuid.UUID, ...]
    facts: tuple[MemoryFact, ...]


async def remember_session_question(
    session: AsyncSession,
    snapshot: RunSnapshot,
    prior: SessionMemoryView,
    question: str,
    observed_tools: tuple[tuple[uuid.UUID, ToolObservation], ...] = (),
) -> int:
    """保存三个已脱敏问题及本轮受控工具事实；模型文字不成为事实。"""
    if snapshot.debug_without_conversation or snapshot.trigger_message_id not in snapshot.message_ids:
        raise AppError(ErrorCode.VALIDATION_ERROR, "调试输入不能写入会话记忆", 422)
    safe_question = prepare_untrusted_text(question, source="user_message").text[:500]
    previous = [line for line in prior.summary.splitlines() if line.startswith("客户此前提问（未经核实）：")]
    lines = [*previous[-2:], f"客户此前提问（未经核实）：{safe_question}"]
    sources = (*prior.source_message_ids[-2:], snapshot.trigger_message_id)
    previous_tool_facts: dict[uuid.UUID, dict[str, str]] = {}
    merged_facts = {item.key: item for item in prior.facts}
    for fact in prior.facts:
        kind, _, raw_id = fact.source_ref.partition(":")
        if kind == "tool":
            previous_tool_facts.setdefault(uuid.UUID(raw_id), {})[fact.key] = fact.value
    for agent_id, observation in observed_tools:
        if observation.status != "succeeded":
            continue
        source_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{snapshot.snapshot_hash}:{agent_id}:{observation.call_id}")
        for key, value in observation.facts.items():
            if not isinstance(value, str | int | float | bool):
                continue
            fact_key = f"{observation.name}.{key}"
            fact_value = str(value)
            if len(fact_key) > 80 or len(fact_value) > 500:
                continue
            try:
                safe = prepare_untrusted_text(fact_value, source="tool_result")
            except AppError:
                continue
            if safe.redacted:
                continue
            previous_tool_facts.setdefault(source_id, {})[fact_key] = fact_value
            merged_facts[fact_key] = MemoryFact(
                key=fact_key,
                value=fact_value,
                source_ref=f"tool:{source_id}",
                observed_at=datetime.now(UTC),
            )
    proposal = propose_memory_update(
        snapshot,
        summary="\n".join(lines),
        source_message_ids=sources,
        facts=tuple(list(merged_facts.values())[-30:]),
        authorized_tool_call_ids=frozenset(previous_tool_facts),
        verified_tool_facts=previous_tool_facts,
    )
    return await commit_memory(session, snapshot, proposal, expected_revision=prior.revision)


def _fact_source_is_verified(
    fact: MemoryFact,
    snapshot: RunSnapshot,
    authorized_tool_call_ids: frozenset[uuid.UUID],
    verified_tool_facts: Mapping[uuid.UUID, Mapping[str, str]],
) -> bool:
    kind, separator, raw_id = fact.source_ref.partition(":")
    if not separator:
        return False
    try:
        source_id = uuid.UUID(raw_id)
    except ValueError:
        return False
    if kind == "message":
        return source_id in snapshot.message_ids and fact.key in {"buyer_preference", "requested_language"}
    if kind == "tool":
        return (
            source_id in authorized_tool_call_ids and verified_tool_facts.get(source_id, {}).get(fact.key) == fact.value
        )
    return False


def propose_memory_update(
    snapshot: RunSnapshot,
    *,
    summary: str,
    source_message_ids: tuple[uuid.UUID, ...],
    facts: tuple[MemoryFact, ...],
    authorized_tool_call_ids: frozenset[uuid.UUID],
    verified_tool_facts: Mapping[uuid.UUID, Mapping[str, str]] | None = None,
) -> MemoryProposal:
    """模型可提出候选；来源及脱敏均由服务端确定。政策不写成记忆。"""
    if not source_message_ids or any(item not in snapshot.message_ids for item in source_message_ids):
        raise AppError(ErrorCode.VALIDATION_ERROR, "记忆摘要来源不在当前会话快照", 422)
    safe_summary = prepare_untrusted_text(summary, source="session_summary")
    safe_facts = []
    for fact in facts:
        if not fact.key or len(fact.key) > 80 or not fact.value or len(fact.value) > 500:
            raise AppError(ErrorCode.VALIDATION_ERROR, "记忆事实字段无效", 422)
        if not _fact_source_is_verified(fact, snapshot, authorized_tool_call_ids, verified_tool_facts or {}):
            raise AppError(ErrorCode.VALIDATION_ERROR, "记忆事实缺少已核验来源", 422)
        safe_value = prepare_untrusted_text(fact.value, source="session_summary")
        if safe_value.redacted:
            raise AppError(ErrorCode.VALIDATION_ERROR, "记忆事实含个人资料", 422)
        safe_facts.append(fact)
    return MemoryProposal(
        summary=safe_summary.text,
        source_message_ids=tuple(dict.fromkeys(source_message_ids)),
        facts=tuple(safe_facts),
    )


async def load_memory(session: AsyncSession, snapshot: RunSnapshot) -> SessionMemoryView:
    """同一会话关闭再重开仍可读取，身份或版本变化则失败关闭。"""
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == snapshot.conversation_id,
            Conversation.store_id == snapshot.store_id,
            Conversation.customer_id == snapshot.customer_id,
        )
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话记忆范围不存在", 404)
    row = await session.scalar(
        select(AgentSessionMemory).where(
            AgentSessionMemory.store_id == snapshot.store_id,
            AgentSessionMemory.conversation_id == snapshot.conversation_id,
            AgentSessionMemory.customer_id == snapshot.customer_id,
        )
    )
    if row is None:
        if snapshot.memory_revision != 0:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话记忆版本已变化", 409)
        return SessionMemoryView(revision=0, summary="", source_message_ids=(), facts=())
    if row.revision != snapshot.memory_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话记忆版本已变化", 409)
    facts = tuple(
        MemoryFact(
            key=str(item["key"]),
            value=str(item["value"]),
            source_ref=str(item["source_ref"]),
            observed_at=datetime.fromisoformat(str(item["observed_at"])) if item.get("observed_at") else None,
        )
        for item in row.facts_json
    )
    return SessionMemoryView(
        revision=row.revision,
        summary=row.summary,
        source_message_ids=tuple(uuid.UUID(value) for value in row.summary_source_ids),
        facts=facts,
    )


async def commit_memory(
    session: AsyncSession,
    snapshot: RunSnapshot,
    proposal: MemoryProposal,
    *,
    expected_revision: int,
) -> int:
    """锁住当前会话，关闭时冻结写入；并发只允许预期 revision 成功。"""
    if expected_revision != snapshot.memory_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "记忆快照版本不匹配", 409)
    conversation = await session.scalar(
        select(Conversation)
        .where(
            Conversation.id == snapshot.conversation_id,
            Conversation.store_id == snapshot.store_id,
            Conversation.customer_id == snapshot.customer_id,
        )
        .with_for_update()
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话记忆范围不存在", 404)
    if conversation.status == "closed" or conversation.closed_at is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "已关闭会话的记忆只读", 409)
    row = await session.scalar(
        select(AgentSessionMemory)
        .where(
            AgentSessionMemory.store_id == snapshot.store_id,
            AgentSessionMemory.conversation_id == snapshot.conversation_id,
            AgentSessionMemory.customer_id == snapshot.customer_id,
        )
        .with_for_update()
    )
    current_revision = row.revision if row is not None else 0
    if current_revision != expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话记忆已更新", 409)
    if row is None:
        row = AgentSessionMemory(
            store_id=snapshot.store_id,
            conversation_id=snapshot.conversation_id,
            customer_id=snapshot.customer_id,
            revision=0,
        )
        session.add(row)
    row.revision = current_revision + 1
    row.summary = proposal.summary
    row.summary_source_ids = [str(item) for item in proposal.source_message_ids]
    row.facts_json = [
        {
            "key": fact.key,
            "value": fact.value,
            "source_ref": fact.source_ref,
            "observed_at": fact.observed_at.isoformat() if fact.observed_at is not None else None,
        }
        for fact in proposal.facts
    ]
    row.updated_at = datetime.now(UTC)
    session.add(
        AuditLog(
            store_id=snapshot.store_id,
            actor_type="agent",
            actor_id=None,
            action="agent.memory.update",
            resource_type="conversation",
            resource_id=snapshot.conversation_id,
            after_data={"revision": row.revision, "fact_count": len(proposal.facts)},
            result="succeeded",
        )
    )
    await session.commit()
    return row.revision
