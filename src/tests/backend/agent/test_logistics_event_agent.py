"""合成事件通过真实 @tool 循环，不依赖平台或模型网络。"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.tools import tool

from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import legacy_safe_sections
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.tools.logistics_updates.contracts import BoundLogisticsEvent, LogisticsScope, TrackingEvent
from app.shared.config.settings import Settings


def event(language="en"):
    return BoundLogisticsEvent(
        scope=LogisticsScope(
            store_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            package_id="synthetic-package",
        ),
        event=TrackingEvent(
            occurred_at=datetime(2026, 11, 2, 10, tzinfo=UTC),
            status="in_transit",
            description="Arrived at the latest hub",
        ),
        buyer_language=language,
    )


def published(context):
    prompt = compile_prompt(legacy_safe_sections())
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=context.scope.store_id,
        config_version=1,
        model_provider="openai",
        model_name="synthetic",
        prompt_hash=prompt.content_sha256,
        prompt_sections=prompt.sections,
        tool_names=("query_order", "query_logistics", "search_knowledge", "notify_logistics_update"),
        file_ids=(str(uuid.uuid4()),),
    )


def synthetic_toolset(context):
    from app.agents.tools.logistics_updates.event_agent import EventToolset, bind_notification_prerequisites

    proposals = []
    evidence = {}
    citations = []
    used_permissions = set()

    @tool
    async def query_order() -> dict:
        """Read this event's verified order."""
        return {"status": "succeeded", "facts": {"status": "IN_TRANSIT"}}

    @tool
    async def query_logistics() -> dict:
        """Read this event's latest verified logistics."""
        return {"status": "succeeded", "facts": {"latest_tracking_description": context.event.description}}

    @tool
    async def search_knowledge(query: str) -> dict:
        """Read only the approved bound synthetic file."""
        evidence["synthetic-chunk"] = "Latest hub means transit."
        citations.append("synthetic-chunk")
        used_permissions.add("knowledge.view")
        return {
            "status": "retrieved",
            "hits": [{"chunk_id": "synthetic-chunk", "content": "Latest hub means transit."}],
        }

    return EventToolset(
        tools=bind_notification_prerequisites(
            (query_order, query_logistics, search_knowledge), proposals, frozenset(published(context).tool_names)
        ),
        proposals=proposals,
        evidence=evidence,
        citations=citations,
        validate=AsyncMock(return_value=True),
        audit=AsyncMock(),
        used_permissions=used_permissions,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["query_order", "query_logistics", "search_knowledge"])
async def test_early_proposal_reports_missing_evidence_and_native_loop_can_complete_it(monkeypatch, missing):
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel

    context = event()
    toolset = synthetic_toolset(context)
    arguments = {
        "query_order": {},
        "query_logistics": {},
        "search_knowledge": {"query": "latest transit hub"},
        "notify_logistics_update": {"candidate_text": "Your parcel reached the latest hub."},
    }
    turns = 0

    class Provider:
        async def complete(self, *, messages, tools, max_output_tokens):
            nonlocal turns
            turns += 1
            if turns == 1:
                names = [name for name in arguments if name != missing]
            elif turns == 2:
                feedback = json.loads(messages[-1]["content"])
                assert feedback["status"] == "missing_required_tools"
                assert feedback["missing_tools"] == [missing]
                assert toolset.proposals == []
                if missing == "search_knowledge":
                    assert toolset.citations == [] and toolset.evidence == {}
                names = [missing, "notify_logistics_update"]
            else:
                assert turns == 3
                assert json.loads(messages[-1]["content"])["status"] == "proposed"
                return ToolTurn("Proposal prepared.", (), {"role": "assistant", "content": "Proposal prepared."}, 1, 1)
            return ToolTurn(
                None,
                tuple(FunctionCall(f"{turns}-{name}", name, arguments[name]) for name in names),
                {"role": "assistant", "content": None},
                1,
                1,
            )

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield Provider()

    @asynccontextmanager
    async def toolsets(bound):
        assert bound == context
        yield toolset

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    model = NativeNotificationModel(
        Settings(_env_file=None, LLM_ENABLED=True), published(context), "Where?", toolsets=toolsets
    )
    assert await model.generate(context) == arguments["notify_logistics_update"]["candidate_text"]
    assert model.citations == ("synthetic-chunk",)
    assert turns == 3
    assert [(item.name, item.status) for item in model.tool_events][-3:] == [
        ("notify_logistics_update", "missing_required_tools"),
        (missing, "retrieved" if missing == "search_knowledge" else "succeeded"),
        ("notify_logistics_update", "proposed"),
    ]
    assert toolset.audit.await_args.args[0] == model.tool_events


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["permission_denied", "selection_required", "exception", "oversized"])
async def test_proposal_does_not_accept_unsuccessful_or_hidden_prerequisite_results(failure):
    from app.agents.tools.catalog import invoke_selected_tool
    from app.agents.tools.logistics_updates.event_agent import bind_notification_prerequisites
    from app.agents.tools.loop import MAX_TOOL_RESULT_CHARS

    ready = False

    @tool
    async def search_knowledge(query: str) -> dict:
        """Actual selected read; failure does not complete its prerequisite."""
        if ready:
            return {"status": "retrieved", "hits": [{"chunk_id": "synthetic-chunk", "content": "Transit policy."}]}
        if failure == "exception":
            raise RuntimeError("synthetic retrieval failure")
        if failure == "oversized":
            return {"status": "retrieved", "hits": [{"content": "x" * MAX_TOOL_RESULT_CHARS}]}
        return {"status": failure, "hits": []}

    proposals = []
    read, propose = bind_notification_prerequisites(
        (search_knowledge,), proposals, frozenset({"search_knowledge", "notify_logistics_update"})
    )
    if failure == "exception":
        with pytest.raises(RuntimeError, match="synthetic retrieval failure"):
            await invoke_selected_tool(read, {"query": "transit"})
    else:
        await invoke_selected_tool(read, {"query": "transit"})
    rejected = await invoke_selected_tool(propose, {"candidate_text": "Your parcel is in transit."})
    assert rejected["status"] == "missing_required_tools" and rejected["missing_tools"] == ["search_knowledge"]
    assert proposals == []
    ready = True
    await invoke_selected_tool(read, {"query": "transit"})
    assert (await invoke_selected_tool(propose, {"candidate_text": "Your parcel is in transit."}))[
        "status"
    ] == "proposed"
    assert proposals == ["Your parcel is in transit."]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,text", [("en", "Your parcel reached the latest hub."), ("zh", "您的包裹已到达最新中转站。")]
)
@pytest.mark.parametrize("optional_read", [False, True])
async def test_event_uses_all_configured_native_tools_and_bound_evidence(monkeypatch, language, text, optional_read):
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel

    context = event(language)
    tools = synthetic_toolset(context)
    agent = published(context)
    file_version_id = uuid.uuid4()
    tools.file_versions = [{"file_id": agent.file_ids[0], "version_id": str(file_version_id), "version_number": 1}]
    if optional_read:

        @tool
        async def query_customer_profile() -> dict:
            """Optional buyer facts; unnecessary for this event."""
            raise AssertionError("the model did not request this optional tool")

        tools.tools = (*tools.tools, query_customer_profile)
        tools.required_names = frozenset(agent.tool_names)
        agent.tool_names = (*agent.tool_names, "query_customer_profile")
    calls = []

    class Provider:
        async def complete(self, *, messages, tools, max_output_tokens):
            calls.append((messages, tools))
            if tools[0].name == "review_answer_evidence":
                payload = json.loads(messages[-1]["content"])
                assert "synthetic-chunk" in str(payload["evidence"])
                return ToolTurn(
                    None,
                    (
                        FunctionCall(
                            "review",
                            "review_answer_evidence",
                            {
                                "supported": True,
                                "reason_code": "supported",
                                "privacy_reviewed": True,
                                "output_rewrite_required": False,
                                "redactions": [],
                                "evidence_ids": list(payload["evidence"]),
                            },
                        ),
                    ),
                    {},
                    2,
                    3,
                )
            if len(calls) == 1:
                return ToolTurn(
                    None,
                    tuple(
                        FunctionCall(str(i), name, arguments)
                        for i, (name, arguments) in enumerate(
                            [
                                ("query_order", {}),
                                ("query_logistics", {}),
                                ("search_knowledge", {"query": "meaning of latest hub"}),
                                ("notify_logistics_update", {"candidate_text": text}),
                            ]
                        )
                    ),
                    {"role": "assistant", "content": None},
                    5,
                    7,
                )
            return ToolTurn("Proposal prepared.", (), {"role": "assistant", "content": "Proposal prepared."}, 11, 13)

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield Provider()

    @asynccontextmanager
    async def toolsets(bound):
        assert bound == context
        yield tools

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    actor_id = uuid.uuid4()
    model = NativeNotificationModel(
        Settings(_env_file=None, LLM_ENABLED=True), agent, "Where is my parcel?", toolsets=toolsets, actor_id=actor_id
    )
    with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
        model.authorization_proof(context, text, policy_revision=7, authorized_by=actor_id)
    candidate = await model.generate(context)
    assert candidate == text
    with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
        model.authorization_proof(context, text, policy_revision=7, authorized_by=actor_id)
    assert (await model.review(context, candidate)).status == "approved"
    proof = model.authorization_proof(context, candidate, policy_revision=7, authorized_by=actor_id)
    from app.agents.tools.logistics_updates.proof import text_sha256

    assert proof.policy_revision == 7 and proof.authorized_by == actor_id
    assert (proof.agent_id, proof.agent_version, proof.prompt_hash) == (agent.id, 1, agent.prompt_hash)
    assert proof.text_sha256 == text_sha256(candidate) and proof.event_key == context.idempotency_key
    assert proof.required_permissions == frozenset({"workspace.reply", "orders.view", "knowledge.view"})
    assert proof.file_versions[0].version_id == file_version_id
    from app.agents.tools.logistics_updates.integration import build_notification_service

    policy = SimpleNamespace(revision=7, authorized_by=actor_id, mode="external")
    service = build_notification_service(AsyncMock(), model.settings, policy, model)
    policy.revision, policy.authorized_by, policy.mode = 8, uuid.uuid4(), "preview"
    assert service.repository.authorization(context, candidate) == proof
    for invalid_text, invalid_actor in [("Injected promise.", actor_id), (candidate, uuid.uuid4())]:
        with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
            model.authorization_proof(context, invalid_text, policy_revision=7, authorized_by=invalid_actor)
    assert model.citations == ("synthetic-chunk",)
    assert model.input_tokens == 18 and model.output_tokens == 23
    assert [item.name for item in tools.audit.await_args.args[0]] == [
        "query_order",
        "query_logistics",
        "search_knowledge",
        "notify_logistics_update",
    ]
    assert str(context.scope.order_id) not in str(calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["notify_logistics_update", "query_logistics", "query_order", "search_knowledge"])
async def test_plain_answer_cannot_replace_required_tool_evidence(monkeypatch, missing):
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel

    context = event()
    tools = synthetic_toolset(context)
    count = 0

    class Provider:
        async def complete(self, **kwargs):
            nonlocal count
            count += 1
            if count == 1:
                arguments = {
                    "search_knowledge": {"query": "hub"},
                    "notify_logistics_update": {"candidate_text": "Arrived."},
                }
                return ToolTurn(
                    None,
                    tuple(
                        FunctionCall(name, name, arguments.get(name, {}))
                        for name in published(context).tool_names
                        if name != missing
                    ),
                    {},
                    1,
                    1,
                )
            return ToolTurn("Arrived.", (), {}, 1, 1)

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield Provider()

    @asynccontextmanager
    async def toolsets(bound):
        yield tools

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    model = NativeNotificationModel(
        Settings(_env_file=None, LLM_ENABLED=True), published(context), "Where is my parcel?", toolsets=toolsets
    )
    with pytest.raises(ValueError, match="notification_required_tool_missing"):
        await model.generate(context)
    assert tools.audit.await_count == 1
    assert tools.proposals == []


@pytest.mark.asyncio
async def test_revoked_bound_evidence_blocks_independent_review(monkeypatch):
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel

    context = event()
    model = NativeNotificationModel(Settings(_env_file=None, LLM_ENABLED=True), published(context), "Where?")
    model.toolset = synthetic_toolset(context)
    model.toolset.validate.return_value = False
    decision = await model.review(context, "Your parcel arrived.")
    assert decision.status == "rejected"
    assert decision.reason == "notification_evidence_changed"


@pytest.mark.asyncio
async def test_true_validation_or_toolset_alone_cannot_mint_independent_review_proof(monkeypatch):
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel

    context, actor = event(), uuid.uuid4()
    provider = AsyncMock(side_effect=AssertionError("no verified generation means no independent review"))
    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    model = NativeNotificationModel(
        Settings(_env_file=None, LLM_ENABLED=True), published(context), "Where?", actor_id=actor
    )
    assert await model.revalidate() is True
    assert (await model.review(context, "Nonempty body")).status == "rejected"
    with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
        model.authorization_proof(context, "Nonempty body", policy_revision=1, authorized_by=actor)
    model.toolset = synthetic_toolset(context)
    assert await model.revalidate() is True
    assert (await model.review(context, "Nonempty body")).status == "rejected"
    with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
        model.authorization_proof(context, "Nonempty body", policy_revision=1, authorized_by=actor)
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_verifies_window_before_reading_buyer_orders(monkeypatch):
    from app.agents.tools.logistics_updates.discovery import synchronize_conversation_orders

    conversation = SimpleNamespace(store_id=uuid.uuid4(), id=uuid.uuid4(), customer_id=uuid.uuid4())
    read = AsyncMock(side_effect=AssertionError("ineligible conversation must not read orders"))
    monkeypatch.setattr(
        "app.agents.tools.logistics_updates.discovery.verified_remote_window",
        AsyncMock(return_value=(True, True, False)),
    )
    monkeypatch.setattr("app.agents.tools.logistics_updates.discovery.read_verified_buyer_orders", read)
    assert await synchronize_conversation_orders(object(), object(), conversation, object()) == 0
    read.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_only_persists_minimal_verified_order_scope(monkeypatch):
    from decimal import Decimal

    from app.agents.tools.logistics_updates.discovery import synchronize_conversation_orders

    conversation = SimpleNamespace(store_id=uuid.uuid4(), id=uuid.uuid4(), customer_id=uuid.uuid4())
    remote = SimpleNamespace(
        external_order_id="771100",
        status="IN_TRANSIT",
        payment_status="PAID",
        currency="USD",
        total_amount=Decimal("9.99"),
        ordered_at=datetime.now(UTC),
        tracking_number="private-tracking",
        shipping_address="private-address",
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: uuid.uuid4())))
    monkeypatch.setattr(
        "app.agents.tools.logistics_updates.discovery.verified_remote_window",
        AsyncMock(return_value=(True, True, True)),
    )
    monkeypatch.setattr(
        "app.agents.tools.logistics_updates.discovery.read_verified_buyer_orders", AsyncMock(return_value=(remote,))
    )
    assert await synchronize_conversation_orders(session, object(), conversation, object()) == 1
    statement = session.execute.await_args.args[0]
    parameters = statement.compile().params
    assert parameters["customer_id"] == conversation.customer_id
    assert parameters["store_id"] == conversation.store_id
    assert parameters["external_order_id"] == "771100"
    assert "private-address" not in str(parameters) and "private-tracking" not in str(parameters)
    assert "orders.customer_id IS NULL" in str(statement)
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    with pytest.raises(ValueError, match="verified_order_ownership_conflict"):
        await synchronize_conversation_orders(session, object(), conversation, object())


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [False, True])
async def test_logistics_tool_reads_current_official_package_and_rejects_changed_event(monkeypatch, changed):
    from app.agents.tools.logistics_updates.contracts import LogisticsObservation
    from app.agents.tools.logistics_updates.event_agent import EventOrderExecutor
    from app.tools.contracts import QueryLogisticsArguments, ToolExecutionContext, ToolInvocation
    from app.tools.executor import ToolDispatchError

    context = event()
    current = context.event.model_copy(update={"description": "A newer hub"}) if changed else context.event
    source = AsyncMock(
        return_value=SimpleNamespace(
            observations=(
                LogisticsObservation(
                    scope=context.scope,
                    buyer_language="en",
                    events=(current,),
                ),
            )
        )
    )
    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.read_verified_observations", source)
    order = SimpleNamespace(id=context.scope.order_id, external_order_id="771100")
    executor = EventOrderExecutor(object(), context.scope.store_id, order)
    executor.event, executor.actor = context, SimpleNamespace(id=uuid.uuid4())
    invocation = ToolInvocation(
        tool_name="query_logistics",
        idempotency_key="synthetic-read",
        arguments={},
        context=ToolExecutionContext(store_id=context.scope.store_id, actor_type="job"),
    )
    if changed:
        with pytest.raises(ToolDispatchError, match="LOGISTICS_EVENT_CHANGED"):
            await executor._query_logistics(invocation, QueryLogisticsArguments(order_id=str(order.id)))
    else:
        result = await executor._query_logistics(invocation, QueryLogisticsArguments(order_id=str(order.id)))
        assert result.data["latest_tracking_description"] == context.event.description
        assert result.data["latest_tracking_at"] == context.event.occurred_at.isoformat()
        assert "latest_tracking_description" not in result.output_summary
    assert source.await_args.args[2:5] == (
        context.scope.store_id,
        context.scope.conversation_id,
        context.scope.order_id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("external,public", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("customized", [False, True])
@pytest.mark.parametrize("bound_files", [False, True])
async def test_production_event_toolset_limits_rag_to_frozen_files_and_rechecks_approval(
    monkeypatch, external, public, customized, bound_files
):
    import time
    from decimal import Decimal
    from unittest.mock import Mock

    from app.agents.runtime.snapshot import FileVersionRef
    from app.agents.tools.catalog import invoke_selected_tool
    from app.agents.tools.logistics_updates.event_agent import notification_toolsets
    from app.agents.tools.loop import ToolEvent
    from app.conversations.models import Conversation
    from app.customers.models import Customer
    from app.knowledge_base.schemas import KnowledgePublicationApproval
    from app.workspace.sidebar import SidebarOrder

    context = event()
    agent = published(context)
    extras = ("query_customer_profile", "search_customer_orders", "query_conversation_messages") if customized else ()
    agent.tool_names = (*agent.tool_names, *extras)
    file_id = uuid.UUID(agent.file_ids[0])
    if not bound_files:
        agent.file_ids = ()
    chunk_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4(), status="active")
    local = SimpleNamespace(id=context.scope.order_id, external_order_id="771100")
    conversation = SimpleNamespace(id=context.scope.conversation_id, platform="tiktok")
    customer = SimpleNamespace(
        tags=["returning"], order_count=2, total_spend=Decimal("19.98"), last_seen_at=None, metadata_json={}
    )
    view = SidebarOrder(
        id=local.id,
        external_order_id=local.external_order_id,
        status="IN_TRANSIT",
        payment_status="PAID",
        currency="USD",
        total_amount=Decimal("9.99"),
        payment_breakdown={},
        ordered_at=datetime.now(UTC),
        tracking_number=None,
        tracking_status=None,
        items=[],
    )
    approved_rows = [(file_id, 1)]
    public_rows = [(file_id, 1)] if public else []

    def records(statement):
        values = statement.compile().params.values()
        rows = public_rows if "approved_for_public_reply" in values else approved_rows
        return SimpleNamespace(all=lambda: rows)

    async def scalar(statement):
        entity = statement.column_descriptions[0].get("entity")
        return customer if entity is Customer else conversation if entity is Conversation else local

    session = SimpleNamespace(
        get=AsyncMock(return_value=actor),
        scalar=AsyncMock(side_effect=scalar),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
        execute=AsyncMock(side_effect=records),
        add=Mock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    @asynccontextmanager
    async def sessions():
        yield session

    snapshot = SimpleNamespace(
        store_id=context.scope.store_id,
        customer_id=context.scope.customer_id,
        conversation_id=context.scope.conversation_id,
        debug_without_conversation=False,
        message_ids=(),
        file_versions=(FileVersionRef(file_id, uuid.uuid4(), 1),) if bound_files else (),
    )
    hit = SimpleNamespace(
        document_id=file_id,
        chunk_id=chunk_id,
        document_version=1,
        content="The latest hub is a transit checkpoint.",
        safety_metadata=SimpleNamespace(
            store_id=context.scope.store_id,
            publication_approval=KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY
            if public
            else KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        ),
    )
    other_hit = SimpleNamespace(
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_version=1,
        content="Unbound evidence",
        safety_metadata=hit.safety_metadata,
    )
    rag = SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(hits=[hit, other_hit])))
    granted = {"orders.view", "workspace.reply", "workspace.view", "knowledge.view"}
    permissions = AsyncMock(side_effect=lambda *args: granted)
    monkeypatch.setattr("app.agents.tools.logistics_updates.event_agent.current_permissions", permissions)
    monkeypatch.setattr("app.agents.tools.business.current_permissions", permissions)
    monkeypatch.setattr("app.agents.tools.business.get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(
        "app.agents.tools.business.search_sidebar_orders",
        AsyncMock(
            return_value=SimpleNamespace(
                items=[view],
                pagination=SimpleNamespace(total=1),
            )
        ),
    )
    monkeypatch.setattr("app.agents.tools.logistics_updates.authorization.bound_agent", AsyncMock(return_value=agent))
    monkeypatch.setattr(
        "app.agents.tools.logistics_updates.event_agent.freeze_debug_context", AsyncMock(return_value=snapshot)
    )
    monkeypatch.setattr(
        "app.agents.tools.logistics_updates.event_agent._verified_sidebar_order",
        AsyncMock(return_value=(None, None, object())),
    )
    monkeypatch.setattr("app.agents.tools.logistics_updates.event_agent._live_order_view", lambda remote: view)
    monkeypatch.setattr("app.agents.tools.logistics_updates.event_agent.build_bound_file_rag", lambda *args: rag)
    factory = notification_toolsets(
        sessions,
        Settings(_env_file=None),
        agent,
        actor.id,
        time.monotonic() + 30,
        require_public_knowledge=external,
    )
    async with factory(context) as tools:
        assert set(agent.tool_names) <= {item.name for item in tools.tools}
        assert not set(extras) & tools.required_names
        propose = next(item for item in tools.tools if item.name == "notify_logistics_update")
        incomplete = await invoke_selected_tool(propose, {"candidate_text": "Your parcel reached the latest hub."})
        assert incomplete["status"] == "missing_required_tools"
        assert incomplete["missing_tools"] == ["query_logistics", "query_order"] + (
            ["search_knowledge"] if bound_files else []
        )
        assert tools.proposals == [] and rag.retrieve.await_count == 0
        for name in extras:
            result = await invoke_selected_tool(next(item for item in tools.tools if item.name == name), {})
            assert result["status"] == "succeeded"
            assert result["source"] == "crm_local_snapshot"
            if name == "query_customer_profile":
                assert result["facts"]["tags"] == ["returning"]
            elif name == "search_customer_orders":
                assert result["facts"]["total"] == 1
            else:
                assert result["facts"]["frozen_message_count"] == 0
        if customized:
            from pydantic import ValidationError

            profile = next(item for item in tools.tools if item.name == "query_customer_profile")
            with pytest.raises(ValidationError):
                await invoke_selected_tool(profile, {"customer_id": str(uuid.uuid4())})
            granted.remove("workspace.view")
            assert not await tools.validate()
            rejected = await invoke_selected_tool(profile, {})
            assert rejected["status"] == "permission_denied" and rejected["error_code"] == "PERMISSION_DENIED"
            granted.add("workspace.view")
        selected = next(item for item in tools.tools if item.name == "search_knowledge")
        result = await invoke_selected_tool(selected, {"query": "latest transit hub"})
        used = bound_files and (not external or public)
        assert result["status"] == ("no_knowledge_bound" if not bound_files else "retrieved" if used else "no_hits")
        assert tools.citations == ([str(chunk_id)] if used else [])
        assert ("knowledge.view" in tools.used_permissions) is bound_files
        assert tools.file_versions == (
            [{"file_id": str(file_id), "version_id": str(snapshot.file_versions[0].version_id), "version_number": 1}]
            if used
            else []
        )
        if customized:
            assert "workspace.view" in tools.used_permissions
        if bound_files:
            assert rag.retrieve.await_args.kwargs["file_ids"] == (file_id,)
        else:
            rag.retrieve.assert_not_awaited()
        incomplete = await invoke_selected_tool(propose, {"candidate_text": "Your parcel reached the latest hub."})
        assert incomplete["status"] == "missing_required_tools"
        assert incomplete["missing_tools"] == ["query_logistics", "query_order"]
        assert tools.proposals == []
        if not bound_files:
            from app.agents.tools.loop import run_tool_loop
            from app.tools.contracts import ToolResult

            execute = AsyncMock(
                return_value=ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"status": "IN_TRANSIT"})
            )
            monkeypatch.setattr("app.agents.tools.logistics_updates.event_agent.EventOrderExecutor.execute", execute)
            provider = SimpleNamespace(
                complete=AsyncMock(
                    side_effect=[
                        ToolTurn(
                            None,
                            (
                                FunctionCall("order", "query_order", {}),
                                FunctionCall("logistics", "query_logistics", {}),
                                FunctionCall(
                                    "proposal",
                                    "notify_logistics_update",
                                    {"candidate_text": "Your parcel reached the latest hub."},
                                ),
                            ),
                            {"role": "assistant", "content": None},
                            3,
                            2,
                        ),
                        ToolTurn("Proposal ready.", (), {"role": "assistant", "content": "Proposal ready."}, 2, 1),
                    ]
                )
            )
            outcome = await run_tool_loop(
                provider=provider, messages=(), tools=tools.tools, deadline=time.monotonic() + 2, max_output_tokens=128
            )
            assert outcome.reason_code is None
            assert [(item.name, item.status) for item in outcome.events] == [
                ("query_order", "succeeded"),
                ("query_logistics", "succeeded"),
                ("notify_logistics_update", "proposed"),
            ]
            assert tools.required_names == frozenset({"query_order", "query_logistics", "notify_logistics_update"})
            assert tools.proposals == ["Your parcel reached the latest hub."]
            assert tools.citations == [] and tools.file_versions == []
            assert "search_knowledge" not in {item.name for item in outcome.events}
            assert execute.await_count == 2
            assert {item.name for item in tools.tools} == set(agent.tool_names)
            assert "search_store_coupons" not in {item.name for item in tools.tools}
        assert await tools.validate()
        if external and public and bound_files:
            public_rows.clear()
            assert not await tools.validate()
        else:
            approved_rows.clear()
            assert await tools.validate() is (not used)
        await tools.audit((ToolEvent("synthetic-call", "search_knowledge", "retrieved"),))
        log = session.add.call_args.args[0]
        assert log.action == "logistics.notification.tool"
        assert log.after_data["tool_name"] == "search_knowledge"
        assert "transit checkpoint" not in str(log.after_data)


@pytest.mark.asyncio
@pytest.mark.parametrize("write_name", ["add_internal_note", "send_coupon", "send_platform_message"])
async def test_event_runtime_rejects_configured_writes_before_opening_business_context(write_name):
    import time

    from app.agents.tools.logistics_updates.event_agent import notification_toolsets

    context = event()
    agent = published(context)
    agent.tool_names = (*agent.tool_names, write_name)
    sessions = AsyncMock(side_effect=AssertionError("write configuration must fail before opening a session"))
    factory = notification_toolsets(sessions, Settings(_env_file=None), agent, uuid.uuid4(), time.monotonic() + 30)
    with pytest.raises(ValueError, match="notification_tool_configuration_invalid"):
        async with factory(context):
            raise AssertionError("must not expose write tools")
    sessions.assert_not_called()


@pytest.mark.asyncio
async def test_external_delivery_rechecks_evidence_before_opening_send_executor():
    from app.agents.tools.logistics_updates.contracts import PreparedLogisticsNotification
    from app.agents.tools.logistics_updates.integration import SqlNotificationDelivery

    context = event()
    sessions = AsyncMock(side_effect=AssertionError("revoked evidence must not open a send session"))
    validate = AsyncMock(return_value=False)
    delivery = SqlNotificationDelivery(
        sessions,
        SimpleNamespace(logistics_notifications_enabled=True, real_tiktok_logistics_notifications_enabled=True),
        validate=validate,
    )
    prepared = PreparedLogisticsNotification(
        scope=context.scope,
        event=context.event,
        buyer_language=context.buyer_language,
        idempotency_key=context.idempotency_key,
        text="Your parcel reached the hub.",
    )
    assert (await delivery.deliver(prepared)).status == "failed"
    sessions.assert_not_called()
    validate.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome", ["safe", "redact", "unsupported", "no_evidence", "failed_review", "unsafe_rewrite", "empty_rewrite"]
)
async def test_model_draft_boundary_requires_real_semantic_review_before_proof(monkeypatch, outcome):
    from app.agents.core.security import evaluate_prompt_safety
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel
    from app.agents.tools.logistics_updates.proof import text_sha256

    safe = "您的包裹于 2026-11-02 10:00 UTC 到达 CedarHub 中转站，后续将沿运输渠道继续运送。"
    # 合成日期和运输渠道触发旧自由输入规则，不能因此跳过输出语义审查。
    assert evaluate_prompt_safety(safe).reason_code == "COMPLETE_ADDRESS_DETECTED"
    private = "收货地址：123 Fictional Road。"
    needs_rewrite = outcome in {"redact", "unsafe_rewrite", "empty_rewrite"}
    candidate = safe + private if needs_rewrite else safe
    raw_candidate = "**" + candidate + "**"
    context, actor = event("zh"), uuid.uuid4()
    tools = synthetic_toolset(context)
    phases = []
    reviews = []

    class Provider:
        async def complete(self, *, messages, tools, max_output_tokens):
            assert messages[-1]["role"] == "user" or phases == ["generate"]
            if tools and tools[0].name == "review_answer_evidence":
                phases.append("review")
                payload = json.loads(messages[-1]["content"])
                reviews.append(payload)
                assert payload["answer"] == (candidate if len(reviews) == 1 else safe)
                assert payload["evidence"] and payload["published_privacy_policies"]
                if outcome == "failed_review":
                    raise RuntimeError("synthetic independent review failure")
                redact = needs_rewrite and len(reviews) == 1
                supported = outcome != "unsupported" and not (outcome == "unsafe_rewrite" and len(reviews) == 2)
                args = {
                    "supported": supported,
                    "reason_code": "supported" if supported else "unsupported",
                    "privacy_reviewed": True,
                    "output_rewrite_required": False,
                    "redactions": [{"segment_id": "s2", "text": private}] if redact else [],
                    "evidence_ids": [] if outcome == "no_evidence" else list(payload["evidence"]),
                }
                return ToolTurn(None, (FunctionCall("review", "review_answer_evidence", args),), {}, 2, 3)
            if not tools:
                phases.append("rewrite")
                payload = json.loads(messages[-1]["content"])
                assert payload["filtered_answer"] == safe
                assert private not in str(messages) and "evidence" not in payload
                answer = "" if outcome == "empty_rewrite" else safe
                return ToolTurn(answer, (), {}, 2, 3)
            if not phases:
                phases.append("generate")
                calls = [
                    ("query_order", {}),
                    ("query_logistics", {}),
                    ("search_knowledge", {"query": "latest hub"}),
                    ("notify_logistics_update", {"candidate_text": raw_candidate}),
                ]
                return ToolTurn(
                    None,
                    tuple(FunctionCall(str(index), name, args) for index, (name, args) in enumerate(calls)),
                    {"role": "assistant", "content": None},
                    2,
                    3,
                )
            phases.append("generated")
            return ToolTurn("Proposal prepared.", (), {}, 2, 3)

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield Provider()

    @asynccontextmanager
    async def toolsets(bound):
        yield tools

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    model = NativeNotificationModel(
        Settings(_env_file=None, LLM_ENABLED=True),
        published(context),
        "包裹在哪里？",
        toolsets=toolsets,
        actor_id=actor,
    )
    generated = await model.generate(context)
    assert generated == candidate and tools.proposals == [candidate]
    with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
        model.authorization_proof(context, generated, policy_revision=1, authorized_by=actor)
    decision = await model.review(context, generated)
    assert reviews  # 必须走真实 review_final_answer，非空候选/validator 不能代替。
    if outcome in {"safe", "redact"}:
        assert decision.status == "approved" and decision.text == safe
        proof = model.authorization_proof(context, safe, policy_revision=1, authorized_by=actor)
        assert proof.text_sha256 == text_sha256(safe)
        assert phases == ["generate", "generated", "review"] + (["rewrite", "review"] if needs_rewrite else [])
        if needs_rewrite:
            with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
                model.authorization_proof(context, candidate, policy_revision=1, authorized_by=actor)
    else:
        assert decision.status == "rejected" and decision.text is None
        with pytest.raises(ValueError, match="notification_review_proof_unavailable"):
            model.authorization_proof(context, safe, policy_revision=1, authorized_by=actor)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate", ["", "   ", "---", "x" * 2001, "😀" * 1001], ids=["empty", "blank", "markdown_only", "long", "utf16"]
)
async def test_model_draft_boundary_rejects_empty_or_over_budget_proposals(candidate):
    from app.agents.tools.logistics_updates.event_agent import build_notification_proposal_tool

    proposals = []
    with pytest.raises(ValueError):
        await build_notification_proposal_tool(proposals).ainvoke({"candidate_text": candidate})
    assert proposals == []


@pytest.mark.parametrize("source", ["user_message", "knowledge_chunk", "tool_result"])
def test_model_draft_boundary_keeps_original_untrusted_input_guards(source):
    from app.agents.safety.input import prepare_untrusted_text
    from app.shared.exceptions.errors import AppError

    with pytest.raises(AppError):
        prepare_untrusted_text("收货地址：123 Fictional Road。", source=source)
    with pytest.raises(AppError):
        prepare_untrusted_text('{"address": "123 Fictional Road"}', source=source)
