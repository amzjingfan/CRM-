"""物流事件的原生工具绑定；模型只能提出通知，不能选择目标或执行投递。"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import cast

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.repository import PublishedAgent
from app.agents.rag.factory import build_bound_file_rag
from app.agents.rag.retriever import (
    EvidenceBundle,
    project_evidence_for_model,
    retrieve_bound_files,
    revalidate_evidence,
)
from app.agents.runtime.output import plain_text_answer, platform_character_count
from app.agents.runtime.snapshot import freeze_debug_context
from app.agents.tools.access import current_permissions
from app.agents.tools.business import AgentBusinessExecutor
from app.agents.tools.catalog import AgentToolContext, build_agent_tools
from app.agents.tools.live_order import AgentDebugLiveOrderExecutor
from app.agents.tools.loop import MAX_TOOL_RESULT_CHARS, ToolEvent, serialize_tool_result
from app.agents.tools.metadata import TOOL_METADATA
from app.audit.models import AuditLog
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.knowledge_base.schemas import KnowledgePublicationApproval
from app.orders.models import Order
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.tools.contracts import QueryLogisticsArguments, ToolInvocation, ToolResult
from app.tools.executor import ToolDispatchError, ToolDispatchOutcome
from app.workspace.sidebar import _live_order_view, _verified_sidebar_order

from .contracts import BoundLogisticsEvent, NotificationArguments

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NOTIFICATION_TOOLS = frozenset(
    name
    for name, metadata in TOOL_METADATA.items()
    if metadata.operation == "read" or name == "notify_logistics_update"
)
REQUIRED_EVENT_TOOLS = frozenset({"query_order", "query_logistics", "search_knowledge", "notify_logistics_update"})


@dataclass
class EventToolset:
    tools: tuple[BaseTool, ...]
    proposals: list[str]
    evidence: dict[str, object]
    citations: list[str]
    validate: Callable[[], Awaitable[bool]]
    audit: Callable[[tuple[ToolEvent, ...]], Awaitable[None]]
    required_names: frozenset[str] = field(default_factory=frozenset)
    file_versions: list[dict[str, object]] = field(default_factory=list)
    used_permissions: set[str] = field(default_factory=set)


def build_notification_proposal_tool(
    proposals: list[str], *, missing_tools: Callable[[], list[str]] | None = None
) -> BaseTool:
    @tool(
        "notify_logistics_update",
        args_schema=NotificationArguments,
        description=(
            "为本次已验证事件提出最新节点通知。先查询已配置订单、物流和绑定知识。"
            "若返回 missing_required_tools，成功调用 missing_tools 后重新提案。"
            "只收集候选，后续独立复核和现权校验通过才允许投递。"
        ),
    )
    async def propose(candidate_text: str) -> dict[str, object]:
        """提案不产生台账或平台写入，防止在生成循环中递归发送。"""
        # 模型草稿按输出规范化；隐私和事实必须由后续独立语义复核过滤，不能套用原始输入 DLP。
        candidate = plain_text_answer(candidate_text)
        if not candidate or platform_character_count(candidate) > 2000:
            raise ValueError("notification_candidate_invalid")
        if proposals:
            return {"status": "proposal_already_submitted"}
        missing = missing_tools() if missing_tools else []
        if missing:
            return {
                "status": "missing_required_tools",
                "missing_tools": missing,
                "next_action": "Call the missing tools successfully, then propose again. No proposal was saved.",
            }
        proposals.append(candidate)
        return {"status": "proposed", "requires_independent_review": True}

    return propose


def bind_notification_prerequisites(
    read_tools: tuple[BaseTool, ...], proposals: list[str], required_names: frozenset[str]
) -> tuple[BaseTool, ...]:
    """只观察模型实际调用成功且可展示的结果，让提案反馈缺失依据而不替模型路由。"""
    completed: set[str] = set()

    def track(selected: BaseTool) -> BaseTool:
        @tool(selected.name, args_schema=selected.args_schema, description=selected.description)
        async def invoke(**arguments: object) -> object:
            result = await selected.ainvoke(arguments)
            if (
                isinstance(result, dict)
                and result.get("status", "succeeded") in {"succeeded", "retrieved", "no_hits", "no_knowledge_bound"}
                and len(serialize_tool_result(result)) <= MAX_TOOL_RESULT_CHARS
            ):
                completed.add(selected.name)
            return result

        return invoke

    required_reads = required_names - {"notify_logistics_update"}
    return (
        *(track(selected) if selected.name in required_reads else selected for selected in read_tools),
        build_notification_proposal_tool(proposals, missing_tools=lambda: sorted(required_reads - completed)),
    )


class EventOrderExecutor(AgentDebugLiveOrderExecutor):
    """保留统一执行器审计与 Schema，物流查询只返回此包裹的当前官方节点。"""

    event: BoundLogisticsEvent
    actor: User
    agent: PublishedAgent

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        from .authorization import bound_agent

        permissions = await current_permissions(self.session, self.actor, self.event.scope.store_id)
        if await bound_agent(self.session, self.event.scope.store_id, self.agent.id) != self.agent:
            raise ValueError("notification_agent_changed")
        # 事件运行不创建普通 AgentRun；工具记录仍保存真实授权人、事件 trace 和唯一调用键。
        invocation = invocation.model_copy(
            update={
                "context": invocation.context.model_copy(
                    update={
                        "actor_type": "job",
                        "actor_id": self.actor.id,
                        "agent_run_id": None,
                        "permissions": permissions,
                    }
                )
            }
        )
        result = await super().execute(invocation)
        await self.session.commit()
        return result

    async def _query_logistics(
        self, invocation: ToolInvocation, arguments: QueryLogisticsArguments
    ) -> ToolDispatchOutcome:
        from .integration import read_verified_observations

        if not self._matches(invocation, arguments.order_id):
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        source = await read_verified_observations(
            self.session,
            self.actor,
            self.event.scope.store_id,
            self.event.scope.conversation_id,
            self.event.scope.order_id,
            None,
        )
        current = next((item for item in source.observations if item.scope == self.event.scope), None)
        if current is None or current.latest.fingerprint != self.event.event.fingerprint:
            raise ToolDispatchError("LOGISTICS_EVENT_CHANGED")
        latest = current.latest
        return ToolDispatchOutcome(
            status="succeeded",
            data={
                "order_id": str(self.order.id),
                "external_order_id": self.order.external_order_id,
                "tracking_number": None,
                "tracking_status": latest.status,
                "latest_tracking_description": latest.description,
                "latest_tracking_at": latest.occurred_at.isoformat(),
                "shipped_at": None,
                "delivered_at": None,
            },
            output_summary={"order_id": str(self.order.id), "has_tracking_event": True},
        )


class EventBusinessExecutor(AgentBusinessExecutor):
    """额外只读能力沿用会话业务边界，并记录实际使用权限供通知投递前复查。"""

    used_permissions: set[str]

    async def invoke(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        if TOOL_METADATA[name].operation != "read":
            return {"status": "permission_denied"}
        result = await super().invoke(name, arguments)
        if result.get("status") in {"succeeded", "selection_required"}:
            self.used_permissions.add(TOOL_METADATA[name].permission)
        return result


def notification_toolsets(
    sessions: Sessions,
    settings: Settings,
    agent: PublishedAgent,
    actor_id: uuid.UUID,
    deadline: float,
    *,
    require_public_knowledge: bool = False,
) -> Callable[[BoundLogisticsEvent], AbstractAsyncContextManager[EventToolset]]:
    @asynccontextmanager
    async def open_tools(context: BoundLogisticsEvent) -> AsyncIterator[EventToolset]:
        from .authorization import NOTIFICATION_PERMISSIONS, bound_agent

        if (
            set(agent.tool_names) - NOTIFICATION_TOOLS
            or "notify_logistics_update" not in agent.tool_names
            or len(set(agent.tool_names)) != len(agent.tool_names)
        ):
            raise ValueError("notification_tool_configuration_invalid")
        async with sessions() as session:
            actor = await session.get(User, actor_id)
            if actor is None or actor.status != "active" or agent.store_id != context.scope.store_id:
                raise ValueError("notification_actor_unavailable")
            permissions = await current_permissions(session, actor, context.scope.store_id)
            if not NOTIFICATION_PERMISSIONS <= permissions:
                raise ValueError("notification_permission_denied")
            snapshot = await freeze_debug_context(
                session,
                store_id=context.scope.store_id,
                conversation_id=context.scope.conversation_id,
                published_agents=(agent,),
            )
            if snapshot.customer_id != context.scope.customer_id:
                raise ValueError("notification_customer_changed")
            local = await session.scalar(
                select(Order).where(
                    Order.id == context.scope.order_id,
                    Order.store_id == context.scope.store_id,
                    Order.customer_id == context.scope.customer_id,
                    Order.platform == "tiktok",
                )
            )
            if local is None:
                raise ValueError("notification_order_unavailable")
            _, _, remote = await _verified_sidebar_order(
                session, actor, context.scope.conversation_id, local.external_order_id
            )
            order = _live_order_view(remote).model_copy(update={"id": local.id})
            executor = EventOrderExecutor(session, context.scope.store_id, order)
            executor.event, executor.actor, executor.agent = context, actor, agent
            run_id = uuid.uuid4()
            business = EventBusinessExecutor(
                session, actor, snapshot, run_id, frozenset(permissions), context.idempotency_key
            )
            business.used_permissions = set()
            bundles: list[EvidenceBundle] = []
            evidence: dict[str, object] = {}
            citations: list[str] = []
            file_versions: list[dict[str, object]] = []
            rag = build_bound_file_rag(settings, None) if agent.file_ids else None

            async def search(query: str) -> dict[str, object]:
                if "knowledge.view" not in await current_permissions(session, actor, context.scope.store_id):
                    return {"status": "permission_denied", "hits": []}
                if rag is None:
                    return {"status": "no_knowledge_bound", "hits": []}
                bundle = await retrieve_bound_files(
                    session=session,
                    snapshot=snapshot,
                    agent=agent,
                    query=query,
                    deadline=deadline,
                    rag_service=rag,
                )
                business.used_permissions.add("knowledge.view")
                if require_public_knowledge:
                    bundle = EvidenceBundle(
                        tuple(
                            hit
                            for hit in bundle.hits
                            if hit.safety_metadata.publication_approval
                            == KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY
                        ),
                        bundle.excluded_file_count,
                    )
                projected = project_evidence_for_model(bundle)
                hits = cast(list[dict[str, object]], projected["hits"])
                while hits and len(serialize_tool_result(projected)) > MAX_TOOL_RESULT_CHARS:
                    hits.pop()
                if not hits and projected["status"] == "retrieved":
                    return {"status": "tool_result_too_large", "hits": []}
                visible = {str(hit["chunk_id"]) for hit in hits}
                bundles.append(
                    EvidenceBundle(
                        tuple(hit for hit in bundle.hits if str(hit.chunk_id) in visible), bundle.excluded_file_count
                    )
                )
                for hit in hits:
                    key = str(hit["chunk_id"])
                    evidence[key] = hit["content"]
                    if key not in citations:
                        citations.append(key)
                visible_versions = {
                    (hit.document_id, hit.document_version) for hit in bundle.hits if str(hit.chunk_id) in visible
                }
                for reference in snapshot.file_versions:
                    if (reference.file_id, reference.version_number) in visible_versions:
                        proof = {
                            "file_id": str(reference.file_id),
                            "version_id": str(reference.version_id),
                            "version_number": reference.version_number,
                        }
                        if proof not in file_versions:
                            file_versions.append(proof)
                return projected

            async def validate() -> bool:
                async with sessions() as current:
                    try:
                        granted = await current_permissions(current, User(id=actor_id), context.scope.store_id)
                        required = (
                            NOTIFICATION_PERMISSIONS
                            | business.used_permissions
                            | ({"knowledge.view"} if citations else set())
                        )
                        if (
                            not required <= granted
                            or await bound_agent(current, context.scope.store_id, agent.id) != agent
                        ):
                            return False
                        for bundle in bundles:
                            checked = await revalidate_evidence(
                                session=current, snapshot=snapshot, agent=agent, bundle=bundle
                            )
                            if checked.hits != bundle.hits:
                                return False
                            if require_public_knowledge and checked.hits:
                                wanted = {(hit.document_id, hit.document_version) for hit in checked.hits}
                                rows = await current.execute(
                                    select(KnowledgeFile.id, KnowledgeFileVersion.version_number)
                                    .join(KnowledgeFileVersion, KnowledgeFileVersion.file_id == KnowledgeFile.id)
                                    .where(
                                        KnowledgeFile.store_id == context.scope.store_id,
                                        KnowledgeFileVersion.store_id == context.scope.store_id,
                                        KnowledgeFile.id.in_({key[0] for key in wanted}),
                                        KnowledgeFileVersion.version_number == KnowledgeFile.active_version_number,
                                        KnowledgeFileVersion.publication_approval
                                        == KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY.value,
                                        KnowledgeFileVersion.status == "ready",
                                        KnowledgeFileVersion.approved_by.is_not(None),
                                        KnowledgeFileVersion.approved_at.is_not(None),
                                        KnowledgeFile.archived_at.is_(None),
                                        KnowledgeFile.deleted_at.is_(None),
                                    )
                                )
                                if not wanted <= set(rows.all()):
                                    return False
                        return True
                    except Exception:
                        return False

            async def audit(events: tuple[ToolEvent, ...]) -> None:
                # 包括检索、提案及失败调用，每个真实模型选择单独落低敏审计；不保存参数或正文。
                async with sessions() as audit_session:
                    for item in events:
                        audit_session.add(
                            AuditLog(
                                store_id=context.scope.store_id,
                                actor_type="job",
                                actor_id=actor_id,
                                action="logistics.notification.tool",
                                resource_type="order",
                                resource_id=context.scope.order_id,
                                after_data={
                                    "tool_name": item.name if item.name in NOTIFICATION_TOOLS else "unavailable",
                                    "status": item.status,
                                    "event_key": context.idempotency_key,
                                    "citation_count": len(citations),
                                },
                                result="succeeded"
                                if item.status
                                in {"succeeded", "retrieved", "no_hits", "no_knowledge_bound", "proposed"}
                                else "failed",
                            )
                        )
                    await audit_session.commit()

            tool_context = AgentToolContext(
                context.scope.store_id,
                run_id,
                str(local.id),
                context.scope.customer_id,
                frozenset(permissions),
                context.idempotency_key,
            )
            event_tools = build_agent_tools(
                tuple(name for name in agent.tool_names if name in {"query_order", "query_logistics"}),
                context=tool_context,
                executor=executor,
            )
            optional_tools = build_agent_tools(
                tuple(
                    name
                    for name in agent.tool_names
                    if name
                    not in {
                        "notify_logistics_update",
                        "query_order",
                        "query_logistics",
                    }
                ),
                context=tool_context,
                executor=executor,
                business_executor=business,
                knowledge_search=search if agent.file_ids else None,
            )
            proposals: list[str] = []
            required_names = (frozenset(agent.tool_names) & REQUIRED_EVENT_TOOLS) | (
                {"search_knowledge"} if agent.file_ids else set()
            )
            yield EventToolset(
                tools=bind_notification_prerequisites((*event_tools, *optional_tools), proposals, required_names),
                proposals=proposals,
                evidence=evidence,
                citations=citations,
                validate=validate,
                audit=audit,
                required_names=required_names,
                file_versions=file_versions,
                used_permissions=business.used_permissions,
            )
            await session.commit()

    return open_tools
