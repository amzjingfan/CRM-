"""物流通知接线只使用合成会话、配置和本地端口。"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError


def test_notification_flags_are_independent_closed_by_default_and_poll_floor_is_eight_hours() -> None:
    from app.shared.config.settings import Settings

    settings = Settings(_env_file=None)
    assert not settings.logistics_notifications_enabled
    assert not settings.real_tiktok_logistics_notifications_enabled
    assert settings.logistics_notification_poll_seconds >= 8 * 3600
    with pytest.raises(ValidationError):
        Settings(_env_file=None, LOGISTICS_NOTIFICATION_POLL_SECONDS=60)


@pytest.mark.asyncio
async def test_catalog_registers_notification_but_normal_question_has_no_event_authority() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool
    from app.agents.tools.metadata import TOOL_METADATA

    metadata = TOOL_METADATA["notify_logistics_update"]
    assert metadata.category == "orders"
    context = AgentToolContext(uuid.uuid4(), uuid.uuid4(), None, uuid.uuid4(), frozenset(), "synthetic")
    tools = build_agent_tools(
        (metadata.name,),
        context=context,
        executor=SimpleNamespace(execute=AsyncMock()),
        business_executor=SimpleNamespace(invoke=AsyncMock()),
    )
    assert (await invoke_selected_tool(tools[0], {"candidate_text": "Latest parcel update"}))[
        "status"
    ] == "context_unavailable"
    for extra in ({"confirmed": True}, {"logistics_notification_key": "forged"}, {"order_id": "other"}):
        with pytest.raises(ValidationError):
            await invoke_selected_tool(tools[0], {"candidate_text": "Latest parcel update", **extra})


def test_only_official_order_and_event_times_after_cutoff_allow_first_notification() -> None:
    from app.agents.tools.logistics_updates.worker import first_observation_mode

    cutoff = datetime(2026, 10, 29, tzinfo=UTC)
    new = cutoff + timedelta(seconds=1)
    assert first_observation_mode(cutoff, new, new) == "notify"
    assert first_observation_mode(cutoff, cutoff - timedelta(days=1), new) == "baseline"
    assert first_observation_mode(cutoff, None, new) == "baseline"
    assert first_observation_mode(cutoff, new, None) == "baseline"


def test_notification_policy_rejects_untrusted_authorizer_and_cutoff_fields() -> None:
    from app.agents.tools.logistics_updates.policy import LogisticsPolicyUpdate

    payload = {"enabled": True, "agent_id": str(uuid.uuid4()), "mode": "preview", "expected_revision": 0}
    assert LogisticsPolicyUpdate.model_validate(payload).mode == "preview"
    for field in ("authorized_by", "enabled_at", "global_enabled"):
        with pytest.raises(ValidationError):
            LogisticsPolicyUpdate.model_validate({**payload, field: "forged"})


@pytest.mark.asyncio
async def test_global_closed_worker_does_not_open_database_or_network() -> None:
    from app.agents.tools.logistics_updates.worker import process_logistics_notification_cycle
    from app.shared.config.settings import Settings

    sessions = AsyncMock(side_effect=AssertionError("closed worker must remain idle"))
    assert not await process_logistics_notification_cycle(sessions, Settings(_env_file=None))
    sessions.assert_not_called()


@pytest.mark.asyncio
async def test_native_notification_generation_and_real_independent_review_keep_language_context_and_usage(
    monkeypatch,
) -> None:
    import json
    from contextlib import asynccontextmanager

    from app.agents.prompts.compiler import compile_prompt
    from app.agents.prompts.sections import legacy_safe_sections
    from app.agents.providers.tool_calling import FunctionCall, ToolTurn
    from app.agents.tools.logistics_updates import BoundLogisticsEvent, LogisticsScope, TrackingEvent
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel
    from app.shared.config.settings import Settings

    calls = []

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            calls.append((messages, tools))
            if not tools:
                return ToolTurn("Your parcel arrived at the hub at 10:00 UTC.", (), {}, 7, 9)
            payload = json.loads(messages[-1]["content"])
            review = FunctionCall(
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
            )
            return ToolTurn(None, (review,), {}, 11, 13)

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield Model()

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    compiled = compile_prompt(legacy_safe_sections())
    agent = SimpleNamespace(
        model_provider="openai",
        model_name="synthetic",
        prompt_hash=compiled.content_sha256,
        prompt_sections=compiled.sections,
    )
    model = NativeNotificationModel(Settings(_env_file=None, LLM_ENABLED=True), agent, "Where is my parcel?")
    context = BoundLogisticsEvent(
        scope=LogisticsScope(
            store_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            package_id="synthetic-package",
        ),
        buyer_language="en",
        event=TrackingEvent(
            occurred_at=datetime(2026, 10, 29, 10, tzinfo=UTC), status="in_transit", description="Arrived at the hub"
        ),
    )
    candidate = await model.generate(context)
    decision = await model.review(context, candidate)
    assert decision.status == "approved" and decision.text == "Your parcel arrived at the hub at 10:00 UTC."
    assert model.input_tokens == 18 and model.output_tokens == 22
    assert len(calls) == 2 and calls[0][1] == () and calls[1][1][0].name == "review_answer_evidence"
    assert "Where is my parcel?" in calls[0][0][-1]["content"]
    assert str(context.scope.order_id) not in str(calls)


@pytest.mark.asyncio
async def test_persisted_notification_authority_requires_exact_ledger_scope_text_and_current_grant(monkeypatch) -> None:
    from app.agents.tools.logistics_updates import (
        AuthorizationSnapshot,
        BoundLogisticsEvent,
        LogisticsScope,
        TrackingEvent,
    )
    from app.agents.tools.logistics_updates.authorization import authorize_persisted_send
    from app.tools.contracts import SendPlatformMessageArguments, ToolExecutionContext, ToolInvocation

    scope = LogisticsScope(
        store_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        package_id="synthetic-package",
    )
    context = BoundLogisticsEvent(
        scope=scope,
        buyer_language="en",
        event=TrackingEvent(occurred_at=datetime.now(UTC), status="in_transit", description="Arrived"),
    )
    actor = uuid.uuid4()
    row = SimpleNamespace(
        mode="external",
        state="unknown",
        reviewed_text="Arrived",
        context_json=context.model_dump(mode="json"),
        customer_id=scope.customer_id,
        order_id=scope.order_id,
        conversation_id=scope.conversation_id,
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=row), get=AsyncMock(return_value=SimpleNamespace(authorized_by=actor))
    )
    snapshot = AuthorizationSnapshot(
        global_enabled=True,
        store_enabled=True,
        tool_bound=True,
        grant_active=True,
        identity_verified=True,
        conversation_valid=True,
        send_window_valid=True,
        scope_available=True,
    )
    authorize = AsyncMock(return_value=snapshot)
    monkeypatch.setattr("app.agents.tools.logistics_updates.authorization.authorize_event", authorize)
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=context.idempotency_key,
        arguments={},
        context=ToolExecutionContext(
            store_id=scope.store_id,
            actor_type="job",
            actor_id=actor,
            logistics_notification_key=context.idempotency_key,
            human_confirmed=False,
        ),
    )
    arguments = SendPlatformMessageArguments(conversation_id=scope.conversation_id, content="Arrived")
    assert await authorize_persisted_send(session, object(), invocation, arguments)
    for changed in (
        arguments.model_copy(update={"content": "Injected promise"}),
        arguments.model_copy(update={"conversation_id": uuid.uuid4()}),
        arguments.model_copy(update={"message_type": "logistics_card"}),
    ):
        assert not await authorize_persisted_send(session, object(), invocation, changed)
    row.state = "pending"
    assert not await authorize_persisted_send(session, object(), invocation, arguments)
    row.state = "unknown"
    authorize.return_value = snapshot.model_copy(update={"grant_active": False})
    assert not await authorize_persisted_send(session, object(), invocation, arguments)


@pytest.mark.asyncio
async def test_official_window_and_buyer_identity_must_both_be_current(monkeypatch) -> None:
    from app.agents.tools.logistics_updates.authorization import verified_remote_window

    remote = SimpleNamespace(
        id="123",
        can_send_message=True,
        participants=[SimpleNamespace(role="BUYER", im_user_id="buyer", user_id="order-buyer")],
    )
    customer = SimpleNamespace(external_customer_id="buyer")
    channel = SimpleNamespace(
        token_expires_at=datetime.now(UTC) + timedelta(days=1),
        authorization_status=None,
        authorization_expires_at=None,
        seller_authorization=None,
        scopes=["seller.order.info", "seller.customer_service", "seller.logistics"],
    )
    conversation = SimpleNamespace(customer_id=uuid.uuid4(), store_id=uuid.uuid4(), external_conversation_id="123")

    class Client:
        def __init__(self, *args):
            pass

        async def get_conversation(self, conversation_id):
            return remote

    monkeypatch.setattr("app.agents.tools.logistics_updates.authorization.TikTokReadClient", Client)

    async def read():
        return await verified_remote_window(
            SimpleNamespace(scalar=AsyncMock(side_effect=[customer, channel])), object(), conversation
        )

    assert await read() == (True, True, True)
    remote.can_send_message = False
    assert await read() == (True, True, False)
    remote.can_send_message = True
    remote.participants[0].im_user_id = "other-buyer"
    assert await read() == (True, False, False)


@pytest.mark.asyncio
async def test_failed_native_generation_keeps_provider_reported_numeric_usage(monkeypatch) -> None:
    from contextlib import asynccontextmanager

    from app.agents.core.errors import LLMErrorCode, LLMProviderError
    from app.agents.prompts.compiler import compile_prompt
    from app.agents.prompts.sections import legacy_safe_sections
    from app.agents.tools.logistics_updates.integration import NativeNotificationModel
    from app.shared.config.settings import Settings

    class FailedModel:
        async def complete(self, **kwargs):
            error = LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "synthetic invalid output", retriable=False)
            error.input_tokens, error.output_tokens = 5, 3
            raise error

    @asynccontextmanager
    async def provider(*args, **kwargs):
        yield FailedModel()

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.tool_provider", provider)
    compiled = compile_prompt(legacy_safe_sections())
    model = NativeNotificationModel(
        Settings(_env_file=None, LLM_ENABLED=True),
        SimpleNamespace(
            model_provider="openai",
            model_name="synthetic",
            prompt_hash=compiled.content_sha256,
            prompt_sections=compiled.sections,
        ),
        "Where is my parcel?",
    )
    monkeypatch.setattr(model, "evidence", lambda context: {})
    with pytest.raises(LLMProviderError):
        await model.generate(SimpleNamespace(buyer_language="en"))
    assert model.input_tokens == 5 and model.output_tokens == 3
