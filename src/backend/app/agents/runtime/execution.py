"""调试与正式会话共用的动态 Agent 模型、工具和知识执行入口。"""

import hashlib
import uuid
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.factory import SharedAgentRuntime
from app.agents.management.repository import PublishedAgent
from app.agents.memory.service import MemoryFact
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutedAgent
from app.agents.orchestration.service import DynamicRunResult, execute_dynamic_run
from app.agents.providers.factory import model_limits, tool_provider
from app.agents.rag.factory import build_bound_file_rag
from app.agents.rag.retriever import EvidenceBundle, revalidate_evidence
from app.agents.runtime.context import ContextBudgetExceeded, ModelLimits, build_context, count_tokens
from app.agents.runtime.models import AgentRun
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.runtime.state import RunPhase
from app.agents.runtime.worker import run_specialist
from app.agents.safety.input import prepare_untrusted_text
from app.agents.tools.access import current_permissions
from app.agents.tools.business import AgentBusinessExecutor
from app.agents.tools.catalog import AgentToolContext
from app.agents.tools.live_order import AgentDebugLiveOrderExecutor
from app.agents.tools.metadata import TOOL_METADATA
from app.conversations.models import Message
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.database.session import session_factory
from app.shared.exceptions.errors import AppError
from app.tools.executor import SqlAlchemyToolExecutor
from app.tools.models import ToolCall
from app.workspace.sidebar import SidebarOrder


def build_routing_context(
    question: str,
    history: tuple[str, ...],
    summary: str,
    limits: ModelLimits,
) -> tuple[str, int]:
    """先给目录、问题和协议保留容量，再以剩余空间选择历史，避免两次装满窗口。"""
    safe_question = prepare_untrusted_text(question, source="user_message").text
    base_tokens = count_tokens(safe_question) + 1024
    remaining = limits.input_limit - base_tokens
    if remaining < 512:
        raise ContextBudgetExceeded("router_question_over_budget")
    catalog_budget = min(4096, remaining - 256)
    context = build_context(
        literal_facts=(),
        evidence=(),
        recent_history=history,
        session_summary=summary,
        limits=limits,
        base_prompt_tokens=base_tokens + catalog_budget,
    )
    return context.rendered, catalog_budget


async def load_snapshot_history(session: AsyncSession, snapshot: RunSnapshot) -> tuple[str, ...]:
    """只读取冻结消息 ID 内的近期内容；稍后到达的消息不混入本轮。"""
    if not snapshot.message_ids:
        return ()
    rows = (
        await session.execute(
            select(Message.direction, Message.content)
            .where(
                Message.store_id == snapshot.store_id,
                Message.conversation_id == snapshot.conversation_id,
                Message.id.in_(snapshot.message_ids[-50:]),
            )
            .order_by(Message.created_at, Message.id)
        )
    ).all()
    history = []
    for direction, text in rows:
        try:
            history.append(f"{direction}: {prepare_untrusted_text(text, source='user_message').text}")
        except AppError:
            # 含不可传递个人信息的历史不成为模型上下文。
            continue
    return tuple(history)


async def finalize_result_evidence(
    result: DynamicRunResult, snapshot: RunSnapshot, user: User | None = None
) -> DynamicRunResult:
    """汇总和独立复核结束后，用新事务复查本次引用，撤权则隐藏整个候选。"""
    if not result.suggestion.citations and user is None:
        return result
    current_ids: set[str] = set()
    permission_changed = False
    async with session_factory() as final_session:
        if user is not None:
            required = {
                TOOL_METADATA[name].permission
                for specialist in result.specialists
                for name in specialist.successful_tools
                if name in TOOL_METADATA
            }
            required.update(
                TOOL_METADATA[key.partition(".")[0]].permission
                for specialist in result.specialists
                for key in specialist.verified_facts
                if key.partition(".")[0] in TOOL_METADATA
            )
            if result.suggestion.citations:
                required.add("knowledge.view")
            try:
                granted = await current_permissions(final_session, User(id=user.id), snapshot.store_id)
                permission_changed = not granted or not required <= granted
            except AppError:
                permission_changed = True
        for specialist in result.specialists:
            if permission_changed:
                break
            if not specialist.knowledge_hits:
                continue
            agent = next(item for item in snapshot.published_agents if item.id == specialist.agent_id)
            current = await revalidate_evidence(
                session=final_session,
                snapshot=snapshot,
                agent=agent,
                bundle=EvidenceBundle(specialist.knowledge_hits, 0),
            )
            current_ids.update(str(hit.chunk_id) for hit in current.hits)
    if not permission_changed and set(result.suggestion.citations) <= current_ids:
        return result
    reason = "tool_permission_changed" if permission_changed else "knowledge_approval_changed"
    return replace(
        result,
        phase=RunPhase.REVIEW_REQUIRED,
        reason_code=reason,
        suggestion=replace(result.suggestion, content=None, citations=(), reason_code=reason),
        specialists=tuple(
            replace(
                item,
                answer=None,
                citations=(),
                citation_details=(),
                knowledge_hits=(),
                reason_code=reason,
                verified_facts={} if permission_changed else item.verified_facts,
                observations=() if permission_changed else item.observations,
            )
            for item in result.specialists
        ),
    )


async def persist_dynamic_result(
    session: AsyncSession,
    *,
    run: AgentRun,
    result: DynamicRunResult,
    snapshot: RunSnapshot,
    agents: tuple[PublishedAgent, ...],
    mode: str,
    elapsed_ms: int,
) -> None:
    """父子运行仅留阶段、计数和配置版本，不复制用户或模型正文。"""
    run.status = "timeout" if result.phase.value == "timeout" else "succeeded"
    run.phase = result.phase.value
    run.error_code = result.reason_code
    run.output_summary = f"phase={result.phase.value};selected={len(result.route.selections)}"
    run.input_tokens = (
        result.route.input_tokens
        + result.suggestion.input_tokens
        + sum(item.input_tokens for item in result.specialists)
    )
    run.output_tokens = (
        result.route.output_tokens
        + result.suggestion.output_tokens
        + sum(item.output_tokens for item in result.specialists)
    )
    run.latency_ms = max(0, elapsed_ms)
    by_id = {agent.id: agent for agent in agents}
    for specialist in result.specialists:
        agent = by_id[specialist.agent_id]
        child = AgentRun(
            parent_run_id=run.id,
            store_id=snapshot.store_id,
            agent_config_id=agent.id,
            conversation_id=None if snapshot.debug_without_conversation else snapshot.conversation_id,
            trigger_message_id=None if mode == "debug" else snapshot.trigger_message_id,
            model_provider=agent.model_provider or "unconfigured",
            model_name=agent.model_name or "unconfigured",
            prompt_version=agent.prompt_hash,
            config_version=agent.config_version,
            action="human_review",
            status="succeeded" if specialist.answer is not None else "failed",
            phase="review_ready" if specialist.answer is not None else "review_required",
            input_summary=f"mode={mode}-v2-child",
            output_summary=f"tool_count={len(specialist.tool_events)};citation_count={len(specialist.citations)}",
            error_code=specialist.reason_code,
            input_tokens=specialist.input_tokens,
            output_tokens=specialist.output_tokens,
            trace_id=run.trace_id,
            snapshot_hash=snapshot.snapshot_hash,
        )
        session.add(child)
        await session.flush()
        for index, event in enumerate(specialist.tool_events):
            name = event.name if event.name in TOOL_METADATA else "unavailable_tool"
            digest = hashlib.sha256(f"{run.id}:{agent.id}:{index}:{event.call_id}:{name}".encode()).hexdigest()
            status = event.status if event.status in {"succeeded", "timeout", "unknown"} else "failed"
            # 只保留能力、阶段与配置关联，不复制模型参数、平台响应或正文。
            await session.execute(
                insert(ToolCall)
                .values(
                    id=uuid.uuid4(),
                    store_id=snapshot.store_id,
                    agent_run_id=child.id,
                    actor_type="agent",
                    tool_name=name,
                    idempotency_key=f"dynamic:{digest}",
                    request_hash=digest,
                    status=status,
                    input_summary={"mode": mode, "config_version": agent.config_version},
                    output_summary={"succeeded": status == "succeeded"},
                    error_code=None if status == "succeeded" else "DYNAMIC_TOOL_" + status.upper(),
                    trace_id=run.trace_id,
                    mocked=False,
                )
                .on_conflict_do_nothing(constraint="uq_tool_call_store_idempotency")
            )
    await session.commit()


async def execute_model_run(
    *,
    snapshot: RunSnapshot,
    question: str,
    agents: tuple[PublishedAgent, ...],
    run_id: uuid.UUID,
    permissions: set[str],
    trace_id: str,
    deadline: float,
    settings: Settings,
    runtime: SharedAgentRuntime | None,
    order_id: str | None,
    live_order: SidebarOrder | None,
    memory_summary: str,
    memory_facts: tuple[MemoryFact, ...] = (),
    user: User | None = None,
) -> DynamicRunResult:
    """每个子 Agent 独立数据库会话，所有模型和工具共享总截止时间。"""
    rag_service = build_bound_file_rag(settings, runtime) if any(agent.file_ids for agent in agents) else None
    assert settings.llm_primary_model is not None
    async with session_factory() as history_session:
        recent_history = await load_snapshot_history(history_session, snapshot)
    routing_context, catalog_budget = build_routing_context(
        question,
        recent_history,
        memory_summary,
        model_limits(settings, settings.llm_primary_provider, settings.llm_primary_model),
    )

    async def worker(selection: RoutedAgent) -> SpecialistResult:
        selected = next((agent for agent in agents if agent.id == selection.agent_id), None)
        if selected is None or selected.model_provider is None or selected.model_name is None:
            return SpecialistResult(selection.agent_id, None, reason_code="agent_model_unavailable")
        async with session_factory() as worker_session:
            executor = (
                AgentDebugLiveOrderExecutor(
                    worker_session,
                    snapshot.store_id,
                    live_order,
                    user=user,
                    conversation_id=None if snapshot.debug_without_conversation else snapshot.conversation_id,
                )
                if live_order is not None
                else SqlAlchemyToolExecutor(worker_session)
            )
            async with tool_provider(settings, selected.model_provider, selected.model_name) as provider:
                return await run_specialist(
                    snapshot=snapshot,
                    agent=selected,
                    selection=selection,
                    provider=provider,
                    executor=executor,
                    rag_service=rag_service,
                    session=worker_session,
                    tool_context=AgentToolContext(
                        store_id=snapshot.store_id,
                        agent_run_id=run_id,
                        order_id=order_id,
                        customer_id=None if snapshot.debug_without_conversation else snapshot.customer_id,
                        permissions=frozenset(permissions),
                        trace_id=trace_id,
                    ),
                    deadline=deadline,
                    model_limits=model_limits(settings, selected.model_provider, selected.model_name),
                    session_summary=memory_summary,
                    recent_history=recent_history,
                    session_facts=memory_facts,
                    business_executor=AgentBusinessExecutor(
                        worker_session, user, snapshot, run_id, frozenset(permissions), trace_id
                    )
                    if user
                    else None,
                )

    async with tool_provider(settings, settings.llm_primary_provider, settings.llm_primary_model) as provider:
        result = await execute_dynamic_run(
            question=question,
            snapshot=snapshot,
            router=provider,
            aggregator=provider,
            worker=worker,
            deadline=deadline,
            max_catalog_tokens=catalog_budget,
            routing_context=routing_context,
        )
    return await finalize_result_evidence(result, snapshot, user=user)
