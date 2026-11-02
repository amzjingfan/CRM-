"""自动资格来自复核事实；队列证明绑定正文、目标和授权。"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.orchestration.aggregator import ReviewedSuggestion
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutePlan
from app.agents.orchestration.service import DynamicRunResult
from app.agents.runtime.state import RunPhase


def reviewed_result():
    agent_id = uuid.uuid4()
    return DynamicRunResult(
        RunPhase.REVIEW_READY,
        RoutePlan((), 1, 0, 0),
        (
            SpecialistResult(
                agent_id,
                "Verified answer",
                verified_facts={"query_order.status": "paid"},
            ),
        ),
        ReviewedSuggestion("Verified answer", "human_review", None, (agent_id,), ()),
        None,
    )


def test_review_ready_has_explicit_payload_bound_eligibility():
    from app.agents.automation.eligibility import review_eligibility

    result = reviewed_result()
    proof = review_eligibility(result)
    assert proof["eligible"] is True
    assert proof["review_phase"] == "review_ready"
    changed = review_eligibility(replace(result, suggestion=replace(result.suggestion, content="Changed")))
    assert proof["content_hashes"] != changed["content_hashes"]


@pytest.mark.parametrize("reason", ["no_verified_evidence", "answer_not_grounded", "tool_permission_changed"])
def test_nonempty_human_draft_is_not_automatic_approval(reason):
    from app.agents.automation.eligibility import review_eligibility

    result = reviewed_result()
    result = replace(
        result,
        reason_code=reason,
        suggestion=replace(result.suggestion, reason_code=reason),
    )
    assert review_eligibility(result)["eligible"] is False


def test_review_required_phase_with_body_is_blocked():
    from app.agents.automation.eligibility import review_eligibility

    assert review_eligibility(replace(reviewed_result(), phase=RunPhase.REVIEW_REQUIRED))["eligible"] is False


def test_policy_defaults_off_and_broken_enabled_policy_is_not_accepted():
    from app.agents.automation.policy import policy_from_store

    assert policy_from_store(SimpleNamespace(metadata_json={})).mode == "off"
    with pytest.raises(ValueError):
        policy_from_store(SimpleNamespace(metadata_json={"agent_automation": {"mode": "auto", "revision": 1}}))


@pytest.mark.parametrize("master,automatic", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.asyncio
async def test_effective_global_gate_matches_agent_and_reception_views(monkeypatch, master, automatic):
    from app.agents.automation import policy
    from app.reception import service as reception
    from app.shared.config.settings import Settings

    settings = Settings(_env_file=None).model_copy(
        update={"real_tiktok_automation_enabled": master, "auto_reply_enabled": automatic}
    )
    monkeypatch.setattr(reception, "get_settings", lambda: settings)
    store = SimpleNamespace(id=uuid.uuid4(), metadata_json={})
    monkeypatch.setattr(policy, "authorized_store", AsyncMock(return_value=store))
    view = await policy.get_policy(object(), object(), store.id, settings)
    assert view.global_enabled is reception._policy_global_enabled() is (master and automatic)
    assert settings.tiktok_automation_effective_enabled is (master and automatic)


@pytest.mark.parametrize("master,automatic", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize("mode", ["preview", "auto"])
@pytest.mark.asyncio
async def test_inbound_auto_requires_both_switches_but_preview_remains_available(monkeypatch, master, automatic, mode):
    from app.agents.automation import service
    from app.shared.config.settings import Settings

    now, store_id, conversation_id = datetime.now(UTC), uuid.uuid4(), uuid.uuid4()
    store = SimpleNamespace(
        metadata_json={
            "agent_automation": {
                "mode": mode,
                "revision": 1,
                "authorized_by": str(uuid.uuid4()),
                "enabled_at": (now - timedelta(minutes=1)).isoformat(),
            }
        }
    )
    conversation = SimpleNamespace(
        id=conversation_id, store_id=store_id, metadata_json={}, platform="tiktok", status="active"
    )
    trigger = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=conversation_id,
        direction="inbound",
        role="user",
        created_at=now,
    )
    scheduled = []
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[store, None]), add=scheduled.append)
    monkeypatch.setattr(service, "find_enabled_config", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    settings = Settings(_env_file=None).model_copy(
        update={"real_tiktok_automation_enabled": master, "auto_reply_enabled": automatic}
    )
    assert await service.on_agent_inbound(session, conversation, trigger, settings)
    assert len(scheduled) == int(mode == "preview" or (master and automatic))


@pytest.mark.asyncio
async def test_worker_runner_cancels_auto_task_before_model_when_emergency_switch_closed():
    from app.agents.automation.runner import process_agent_task
    from app.shared.config.settings import Settings

    policy = {
        "mode": "auto",
        "revision": 1,
        "authorized_by": str(uuid.uuid4()),
        "enabled_at": datetime.now(UTC).isoformat(),
    }
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=SimpleNamespace(metadata_json={"agent_automation": policy})),
        get=AsyncMock(side_effect=AssertionError("must cancel before actor/model loading")),
        commit=AsyncMock(),
    )
    task = SimpleNamespace(store_id=uuid.uuid4(), trace_id="automation:1:owned")
    settings = Settings(_env_file=None).model_copy(
        update={"real_tiktok_automation_enabled": True, "auto_reply_enabled": False}
    )
    await process_agent_task(session, task, settings)
    assert task.status == "cancelled" and task.error_code == "AUTOMATION_POLICY_CHANGED"
    session.get.assert_not_awaited()


def test_payload_hash_binds_target_content_and_cards():
    from app.agents.automation.service import payload_hash

    values = {
        "store_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "content": "Reviewed",
        "message_type": "text",
        "card_order_id": None,
        "card_package_id": None,
    }
    original = payload_hash(**values)
    assert payload_hash(**{**values, "content": "Changed"}) != original
    assert payload_hash(**{**values, "conversation_id": uuid.uuid4()}) != original
    assert payload_hash(**{**values, "card_order_id": "123"}) != original


@pytest.mark.asyncio
async def test_enqueue_replays_identical_row_without_commit_and_rejects_mutation():
    from app.agents.automation.service import enqueue_delivery
    from app.shared.exceptions.errors import AppError

    session = SimpleNamespace(
        scalar=AsyncMock(return_value=None),
        add=lambda row: None,
        flush=AsyncMock(),
        commit=AsyncMock(),
    )
    values = {
        "store_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "source_kind": "agent",
        "source_key": "source",
        "content": "Reviewed",
        "authorized_by": uuid.uuid4(),
        "policy_revision": 2,
        "mode": "auto",
    }
    row = await enqueue_delivery(session, **values)
    session.scalar.return_value = row
    assert await enqueue_delivery(session, **values) is row
    with pytest.raises(AppError):
        await enqueue_delivery(session, **{**values, "content": "Changed"})
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_forged_context_without_persisted_delivery_cannot_send():
    from app.agents.automation.authorization import authorize_persisted_send
    from app.shared.config.settings import Settings
    from app.tools.contracts import (
        SendPlatformMessageArguments,
        ToolExecutionContext,
        ToolInvocation,
    )

    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key="automation:missing",
        arguments={},
        context=ToolExecutionContext(
            store_id=uuid.uuid4(),
            actor_type="agent",
            actor_id=uuid.uuid4(),
            permissions={"workspace.reply"},
            automation_delivery_id=uuid.uuid4(),
            automation_claim_token=uuid.uuid4(),
        ),
    )
    settings = Settings(_env_file=None).model_copy(update={"real_tiktok_automation_enabled": True})
    assert (
        await authorize_persisted_send(
            session,
            settings,
            invocation,
            SendPlatformMessageArguments(conversation_id=uuid.uuid4(), content="Nonempty"),
        )
        is None
    )


@pytest.mark.asyncio
async def test_expired_dispatch_is_unknown_and_never_reclaimed():
    from app.agents.automation.models import AutomationDelivery
    from app.agents.automation.service import recover_expired_deliveries

    row = AutomationDelivery(
        id=uuid.uuid4(),
        status="dispatching",
        claimed_until=datetime.now(UTC) - timedelta(seconds=1),
    )

    class Scalars:
        def all(self):
            return [row]

    session = SimpleNamespace(scalars=AsyncMock(return_value=Scalars()))
    await recover_expired_deliveries(session)
    assert row.status == "unknown"
    assert row.error_code == "AUTOMATION_RECEIPT_UNKNOWN"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "content",
        "target",
        "lease",
        "actor",
        "token",
        "status",
        "human_confirmed",
        "idempotency",
    ],
)
async def test_persisted_authorization_rejects_tampered_invocations(change, monkeypatch):
    from app.agents.automation import authorization
    from app.agents.automation.models import AutomationDelivery
    from app.tools.contracts import (
        SendPlatformMessageArguments,
        ToolExecutionContext,
        ToolInvocation,
    )

    store_id, conversation_id, actor_id, token = (uuid.uuid4() for _ in range(4))
    row = AutomationDelivery(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=conversation_id,
        content="Reviewed",
        message_type="text",
        source_kind="welcome",
        status="dispatching",
        claim_token=token,
        claimed_until=datetime.now(UTC) + timedelta(minutes=1),
        authorized_by=actor_id,
    )
    context = ToolExecutionContext(
        store_id=store_id,
        actor_id=actor_id,
        actor_type="job",
        automation_delivery_id=row.id,
        automation_claim_token=token,
    )
    args = SendPlatformMessageArguments(conversation_id=conversation_id, content="Reviewed")
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=f"automation:{row.id}",
        context=context,
        arguments={},
    )
    if change == "content":
        args.content = "Not reviewed"
    if change == "target":
        args.conversation_id = uuid.uuid4()
    if change == "lease":
        row.claimed_until = datetime.now(UTC) - timedelta(seconds=1)
    if change == "actor":
        context.actor_id = uuid.uuid4()
    if change == "token":
        context.automation_claim_token = uuid.uuid4()
    if change == "status":
        row.status = "unknown"
    if change == "human_confirmed":
        context.human_confirmed = True
    if change == "idempotency":
        invocation.idempotency_key = "other"
    check = AsyncMock(return_value=True)
    monkeypatch.setattr(authorization, "authorize_delivery", check)
    session = SimpleNamespace(scalar=AsyncMock(return_value=row))
    assert await authorization.authorize_persisted_send(session, SimpleNamespace(), invocation, args) is None
    check.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        None,
        "off",
        "revision",
        "revoked",
        "pause",
        "resumed",
        "human_reply",
        "backlog",
        "config_version",
        "no_review",
        "no_customer_approval",
        "window",
    ],
)
@pytest.mark.parametrize("master,automatic", [(True, True), (True, False), (False, True), (False, False)])
async def test_agent_delivery_revalidates_all_current_authorization(change, monkeypatch, master, automatic):
    from app.agents.automation import authorization
    from app.agents.automation.eligibility import content_hash
    from app.agents.automation.models import AutomationDelivery
    from app.agents.automation.service import payload_hash
    from app.agents.runtime.models import AgentRun
    from app.conversations.models import Conversation, Message
    from app.shared.database.base import User
    from app.stores.models import Store

    store_id, conversation_id, actor_id, customer_id, trigger_id, agent_id = (uuid.uuid4() for _ in range(6))
    now = datetime.now(UTC)
    conversation = Conversation(
        id=conversation_id,
        store_id=store_id,
        customer_id=customer_id,
        platform="tiktok",
        status="active",
        metadata_json={},
    )
    policy = {
        "mode": "auto",
        "revision": 1,
        "authorized_by": str(actor_id),
        "enabled_at": (now - timedelta(minutes=2)).isoformat(),
    }
    store = Store(id=store_id, status="active", metadata_json={"agent_automation": policy})
    trigger = Message(
        id=trigger_id,
        store_id=store_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        direction="inbound",
        role="user",
        created_at=now - timedelta(minutes=1),
    )
    proof = {
        "eligible": True,
        "review_version": "independent-evidence-privacy-v1",
        "content_hashes": [content_hash("Reviewed")],
        "required_permissions": ["orders.view"],
        "agent_versions": [[str(agent_id), 2]],
        "file_versions": [],
    }
    run = AgentRun(id=uuid.uuid4(), snapshot_ref={"automation_eligibility": proof})
    row = AutomationDelivery(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_id,
        agent_run_id=run.id,
        content="Reviewed",
        message_type="text",
        source_kind="agent",
        part_index=0,
        mode="auto",
        policy_revision=1,
        authorized_by=actor_id,
        authorization_json={"conversation_revision": 0},
        payload_hash=payload_hash(
            store_id=store_id,
            conversation_id=conversation_id,
            content="Reviewed",
            message_type="text",
            card_order_id=None,
            card_package_id=None,
        ),
    )
    if change == "off":
        policy["mode"] = "off"
    if change == "revision":
        policy["revision"] = 2
    if change == "pause":
        conversation.metadata_json = {"automation_paused": True}
    if change == "resumed":
        conversation.metadata_json = {"automation_revision": 2}
    if change == "human_reply":
        conversation.last_human_replied_at = now
    if change == "backlog":
        trigger.created_at = now - timedelta(days=1)
    if change == "no_review":
        proof["eligible"] = False
    actor = User(id=actor_id, status="active")
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[conversation, store, trigger, run] * 2),
        get=AsyncMock(return_value=actor),
        execute=AsyncMock(),
    )
    monkeypatch.setattr(
        authorization,
        "current_permissions",
        AsyncMock(
            return_value={
                "workspace.reply",
                "workspace.view",
                "agent.manage",
                "orders.view",
            }
            if change != "revoked"
            else {"workspace.view"}
        ),
    )
    monkeypatch.setattr(
        authorization,
        "list_enabled_agents",
        AsyncMock(return_value=[SimpleNamespace(id=agent_id, config_version=3 if change == "config_version" else 2)]),
    )
    monkeypatch.setattr(
        authorization,
        "current_customer_files",
        AsyncMock(return_value=change != "no_customer_approval"),
    )
    remote = AsyncMock(return_value=(True, True, change != "window"))
    monkeypatch.setattr(authorization, "verified_remote_window", remote)
    from app.shared.config.settings import Settings

    settings = Settings(_env_file=None).model_copy(
        update={"real_tiktok_automation_enabled": master, "auto_reply_enabled": automatic, "app_env": "test"}
    )
    assert await authorization.authorize_delivery(session, row, settings) is (change is None and master and automatic)
    if not (master and automatic):
        remote.assert_not_awaited()
    if change in {"pause", "off", "revoked", "revision"}:
        remote.assert_not_awaited()


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_fixed_third_round_requires_exact_approved_copy_and_completed_handover(
    language,
):
    from app.agents.automation.eligibility import review_eligibility
    from app.agents.orchestration.fallback import FIXED_FALLBACK

    result = reviewed_result()
    fallback = replace(
        result.specialists[0],
        successful_tools=("create_handoff_request", "add_internal_note"),
    )
    result = replace(
        result,
        phase=RunPhase.REVIEW_REQUIRED,
        specialists=(fallback,),
        reason_code="fallback_third_round",
        suggestion=replace(
            result.suggestion,
            content=FIXED_FALLBACK[language],
            reason_code="fallback_third_round",
            reply_language=language,
        ),
    )
    assert review_eligibility(result)["eligible"] is True
    assert (
        review_eligibility(
            replace(
                result,
                suggestion=replace(result.suggestion, content="Invented fallback"),
            )
        )["eligible"]
        is False
    )
    assert (
        review_eligibility(replace(result, specialists=(replace(fallback, successful_tools=()),)))["eligible"] is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [None, "package", "order", "index", "revoked_card"])
async def test_auto_card_is_bound_to_run_proof_and_current_buyer_order(change, monkeypatch):
    from app.agents.automation.authorization import authorize_agent_card
    from app.agents.automation.models import AutomationDelivery
    from app.workspace import service as workspace

    row = AutomationDelivery(
        conversation_id=uuid.uuid4(),
        part_index=1,
        message_type="logistics_card",
        card_order_id="123",
        card_package_id="456",
    )
    proof = {"cards": [[1, "123", "456"]]}
    cards = [SimpleNamespace(card=SimpleNamespace(order_id="123", package_id="456"))]
    if change == "package":
        row.card_package_id = "999"
    if change == "order":
        row.card_order_id = "999"
    if change == "index":
        row.part_index = 2
    if change == "revoked_card":
        cards = []
    monkeypatch.setattr(workspace, "get_logistics_card_preview", AsyncMock(return_value=cards))
    assert await authorize_agent_card(SimpleNamespace(), row, proof, SimpleNamespace()) is (change is None)


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt,status", [(3, "processing"), (3, "queued"), (1, "queued")])
async def test_process_one_stale_error_cannot_overwrite_replacement(attempt, status, monkeypatch):
    from contextlib import asynccontextmanager

    from app.agents.automation import runner
    from app.chat import worker

    claimed = SimpleNamespace(id=uuid.uuid4(), trace_id="old-attempt", attempt_count=1, status="processing")
    replacement = SimpleNamespace(
        id=claimed.id,
        trace_id="replacement",
        attempt_count=attempt,
        status=status,
        error_code=None,
        next_attempt_at=None,
        processed_at=None,
    )
    session = SimpleNamespace(rollback=AsyncMock(), get=AsyncMock(return_value=replacement), commit=AsyncMock())

    @asynccontextmanager
    async def sessions():
        yield session

    monkeypatch.setattr(worker, "session_factory", sessions)
    monkeypatch.setattr(runner, "process_one_delivery", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "claim_task", AsyncMock(return_value=claimed))
    monkeypatch.setattr(worker, "process_task", AsyncMock(side_effect=ValueError("expired-attempt")))
    assert await worker.process_one(SimpleNamespace(auto_reply_max_attempts=3)) is True
    assert replacement.status == status
    assert replacement.attempt_count == attempt
    assert replacement.error_code is replacement.next_attempt_at is replacement.processed_at is None
    session.commit.assert_not_awaited()
