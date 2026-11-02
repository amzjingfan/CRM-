"""合成物流观察的基线、隔离、复核与不确定交付行为。"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError


def _scope(**changes: object):
    from app.agents.tools.logistics_updates import LogisticsScope

    return LogisticsScope(
        **{
            "store_id": uuid.UUID(int=1),
            "customer_id": uuid.UUID(int=2),
            "conversation_id": uuid.UUID(int=3),
            "order_id": uuid.UUID(int=4),
            "package_id": "synthetic-package",
            **changes,
        }
    )


def _observation(minutes: int, *, scope=None, descriptions: tuple[str, ...] = ()):
    from app.agents.tools.logistics_updates import LogisticsObservation, TrackingEvent

    moment = datetime(2026, 10, 29, tzinfo=UTC) + timedelta(minutes=minutes)
    descriptions = descriptions or (f"Arrived at hub {minutes}",)
    return LogisticsObservation(
        scope=scope or _scope(),
        buyer_language="en",
        events=tuple(
            TrackingEvent(occurred_at=moment + timedelta(seconds=index), status="in_transit", description=value)
            for index, value in enumerate(descriptions)
        ),
    )


class LocalDelivery:
    def __init__(self, status: str = "succeeded") -> None:
        self.status = status
        self.previews: list[object] = []
        self.sent: list[object] = []
        self.reconciled: list[str] = []

    async def preview(self, notification):
        from app.agents.tools.logistics_updates import DeliveryReceipt

        self.previews.append(notification)
        return DeliveryReceipt(status=self.status, reference="local-plan")

    async def deliver(self, notification):
        from app.agents.tools.logistics_updates import DeliveryReceipt

        self.sent.append(notification)
        await asyncio.sleep(0)
        return DeliveryReceipt(status=self.status, reference="synthetic-delivery")

    async def reconcile(self, notification):
        from app.agents.tools.logistics_updates import DeliveryReceipt

        self.reconciled.append(notification.idempotency_key)
        return DeliveryReceipt(status=self.status, reference="synthetic-reconciliation")


def _service(*, denial: str | None = None, mode: str = "preview", delivery=None, reviewer=None):
    from app.agents.tools.logistics_updates import (
        AuthorizationSnapshot,
        InMemoryLogisticsRepository,
        LogisticsUpdateService,
        ReviewDecision,
    )

    async def authorize(context):
        values = {
            name: True
            for name in (
                "global_enabled",
                "store_enabled",
                "tool_bound",
                "grant_active",
                "identity_verified",
                "conversation_valid",
                "send_window_valid",
                "scope_available",
            )
        }
        if denial:
            values[denial] = False
        return AuthorizationSnapshot(**values)

    async def review(context, text):
        return ReviewDecision(status="approved", text=text)

    async def generate(context):
        return f"Latest update: {context.event.description}."

    repo = InMemoryLogisticsRepository()
    delivery = delivery or LocalDelivery()
    service = LogisticsUpdateService(
        repository=repo,
        authorize=authorize,
        review=reviewer or review,
        generate=generate,
        delivery=delivery,
        mode=mode,
    )
    return service, repo, delivery


@pytest.mark.asyncio
async def test_first_observation_is_baseline_and_only_latest_new_node_is_previewed() -> None:
    service, _, delivery = _service()
    assert (await service.observe_and_notify(_observation(0))).status == "baseline"
    result = await service.observe_and_notify(
        _observation(1, descriptions=("Departed origin", "Arrived at destination hub"))
    )
    assert result.status == "previewed"
    assert len(delivery.previews) == 1
    prepared = delivery.previews[0]
    assert prepared.text == "Latest update: Arrived at destination hub."
    assert prepared.buyer_language == "en"
    assert prepared.scope == _scope()
    assert not delivery.sent


@pytest.mark.asyncio
async def test_trusted_new_order_can_notify_first_event_while_unknown_orders_default_to_baseline() -> None:
    service, _, delivery = _service()
    fresh = _observation(0).model_dump()
    fresh["first_observation"] = "notify"
    from app.agents.tools.logistics_updates import LogisticsObservation

    observed = LogisticsObservation.model_validate(fresh)
    assert (await service.observe_and_notify(observed)).status == "previewed"
    assert (await service.observe_and_notify(observed)).status == "ignored"
    assert len(delivery.previews) == 1


@pytest.mark.asyncio
async def test_duplicate_and_out_of_order_observations_do_not_repeat_notification() -> None:
    service, _, delivery = _service()
    await service.observe(_observation(5))
    await service.observe_and_notify(_observation(10))
    for observation in (_observation(10), _observation(7), _observation(1)):
        assert (await service.observe_and_notify(observation)).status == "ignored"
    assert len(delivery.previews) == 1


@pytest.mark.asyncio
async def test_pending_older_node_is_superseded_before_review() -> None:
    service, _, delivery = _service()
    await service.observe(_observation(0))
    old = await service.observe(_observation(1))
    latest = await service.observe(_observation(2))
    assert (await service.notify(old.context, "Old candidate")).status == "superseded"
    assert (await service.notify(latest.context, "Latest candidate")).status == "previewed"
    assert len(delivery.previews) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "denial",
    [
        "global_enabled",
        "store_enabled",
        "tool_bound",
        "grant_active",
        "identity_verified",
        "conversation_valid",
        "send_window_valid",
        "scope_available",
    ],
)
async def test_each_server_authorization_gate_blocks_delivery(denial: str) -> None:
    service, _, delivery = _service(denial=denial)
    await service.observe(_observation(0))
    result = await service.observe_and_notify(_observation(1))
    assert result.status == "blocked"
    assert result.reason == denial
    assert not delivery.previews and not delivery.sent


@pytest.mark.asyncio
async def test_revocation_during_review_is_rechecked_before_delivery() -> None:
    from app.agents.tools.logistics_updates import AuthorizationSnapshot, ReviewDecision

    service, _, delivery = _service()
    active = True

    async def authorize(context):
        return AuthorizationSnapshot(
            global_enabled=True,
            store_enabled=True,
            tool_bound=True,
            grant_active=active,
            identity_verified=True,
            conversation_valid=True,
            send_window_valid=True,
            scope_available=True,
        )

    async def review(context, text):
        nonlocal active
        active = False
        return ReviewDecision(status="approved", text=text)

    service.authorize = authorize
    service.review = review
    await service.observe(_observation(0))
    assert (await service.observe_and_notify(_observation(1))).reason == "grant_active"
    assert not delivery.previews


@pytest.mark.asyncio
async def test_rejected_or_invalid_review_never_becomes_a_delivery_plan() -> None:
    from app.agents.tools.logistics_updates import ReviewDecision

    async def reject(context, text):
        return ReviewDecision(status="rejected", reason="unsupported")

    service, _, delivery = _service(reviewer=reject)
    await service.observe(_observation(0))
    result = await service.observe_and_notify(_observation(1))
    assert result.status == "rejected" and result.reason == "unsupported"
    assert not delivery.previews


@pytest.mark.asyncio
async def test_tool_cannot_accept_ids_or_confirmation_and_without_event_only_blocks() -> None:
    from app.agents.tools.catalog import invoke_selected_tool
    from app.agents.tools.logistics_updates import build_notify_logistics_update_tool

    service, _, delivery = _service()
    selected = build_notify_logistics_update_tool(service, context=None)
    assert (await invoke_selected_tool(selected, {"candidate_text": "Update"}))["status"] == "context_unavailable"
    for key, value in (
        ("store_id", str(uuid.uuid4())),
        ("confirmed", True),
        ("order_id", "other"),
        ("first_observation", "notify"),
    ):
        with pytest.raises(ValidationError):
            await invoke_selected_tool(selected, {"candidate_text": "Update", key: value})
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    bound_tool = build_notify_logistics_update_tool(service, context=event.context)
    assert (await invoke_selected_tool(bound_tool, {"candidate_text": "Latest update: Arrived at hub 1."}))[
        "status"
    ] == "previewed"
    assert len(delivery.previews) == 1


@pytest.mark.asyncio
async def test_forged_store_customer_conversation_order_or_package_context_is_rejected() -> None:
    service, _, delivery = _service()
    await service.observe(_observation(0))
    result = await service.observe(_observation(1))
    for name, value in (
        ("store_id", uuid.UUID(int=9)),
        ("customer_id", uuid.UUID(int=9)),
        ("conversation_id", uuid.UUID(int=9)),
        ("order_id", uuid.UUID(int=9)),
        ("package_id", "other"),
    ):
        forged = result.context.model_copy(update={"scope": _scope(**{name: value})})
        assert (await service.notify(forged, "Update")).status == "context_unavailable"
    assert not delivery.previews


@pytest.mark.asyncio
async def test_concurrent_repeated_tools_claim_one_stable_notification() -> None:
    service, _, delivery = _service(mode="external")
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    results = await asyncio.gather(*(service.notify(event.context, "Latest update") for _ in range(12)))
    assert sum(item.status == "succeeded" for item in results) >= 1
    assert len(delivery.sent) == 1
    assert len({item.idempotency_key for item in delivery.sent}) == 1


@pytest.mark.asyncio
async def test_unknown_is_not_resent_and_reconciliation_preserves_stable_key() -> None:
    delivery = LocalDelivery(status="unknown")
    service, _, _ = _service(mode="external", delivery=delivery)
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    assert (await service.notify(event.context, "Latest update")).status == "unknown"
    key = delivery.sent[0].idempotency_key
    assert (await service.notify(event.context, "Retry")).status == "unknown"
    assert len(delivery.sent) == 1
    delivery.status = "succeeded"
    assert (await service.reconcile(event.context)).status == "succeeded"
    assert delivery.reconciled == [key]
    assert len(delivery.sent) == 1


@pytest.mark.asyncio
async def test_ambiguous_delivery_exception_is_unknown_without_leaking_message(caplog) -> None:
    class BrokenDelivery(LocalDelivery):
        async def deliver(self, notification):
            raise TimeoutError("private synthetic body must not be logged")

    service, _, _ = _service(mode="external", delivery=BrokenDelivery())
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    result = await service.notify(event.context, "Latest update")
    assert result.status == "unknown" and result.reason == "delivery_unknown"
    assert "private synthetic body" not in caplog.text


@pytest.mark.asyncio
async def test_generation_claim_prevents_tool_racing_the_same_notification() -> None:
    service, _, delivery = _service()
    entered, release = asyncio.Event(), asyncio.Event()
    generated_context = None

    async def generate(context):
        nonlocal generated_context
        generated_context = context
        entered.set()
        await release.wait()
        return "Latest update"

    service.generate = generate
    await service.observe(_observation(0))
    task = asyncio.create_task(service.observe_and_notify(_observation(1)))
    await entered.wait()
    raced = await service.notify(generated_context, "Duplicate from model")
    release.set()
    completed = await task
    assert raced.status == "reviewing"
    assert completed.status == "previewed"
    assert len(delivery.previews) == 1


@pytest.mark.asyncio
async def test_newer_event_arriving_during_review_supersedes_before_delivery() -> None:
    from app.agents.tools.logistics_updates import ReviewDecision

    service, _, delivery = _service()

    async def review(context, text):
        await service.observe(_observation(2))
        return ReviewDecision(status="approved", text=text)

    service.review = review
    await service.observe(_observation(0))
    assert (await service.observe_and_notify(_observation(1))).status == "superseded"
    assert not delivery.previews


@pytest.mark.asyncio
async def test_cancelled_delivery_stays_unknown_and_never_blindly_retries() -> None:
    entered = asyncio.Event()

    class PausedDelivery(LocalDelivery):
        async def deliver(self, notification):
            self.sent.append(notification)
            entered.set()
            await asyncio.Event().wait()

    service, _, delivery = _service(mode="external", delivery=PausedDelivery())
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    task = asyncio.create_task(service.notify(event.context, "Latest update"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await service.notify(event.context, "Repeat")).status == "unknown"
    assert len(delivery.sent) == 1


@pytest.mark.asyncio
async def test_failed_delivery_is_distinct_from_unknown_and_is_not_reissued_by_model() -> None:
    service, _, delivery = _service(mode="external", delivery=LocalDelivery(status="failed"))
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    assert (await service.notify(event.context, "Latest update")).status == "failed"
    assert (await service.notify(event.context, "Retry")).status == "failed"
    assert len(delivery.sent) == 1


def test_observations_require_aware_time_and_nonempty_verified_nodes() -> None:
    from app.agents.tools.logistics_updates import TrackingEvent

    with pytest.raises(ValidationError):
        TrackingEvent(occurred_at=datetime(2026, 10, 29), status="in_transit", description="Arrived")
    with pytest.raises(ValidationError):
        _observation(0, scope=_scope(package_id=""))


@pytest.mark.asyncio
async def test_expired_review_owner_cannot_prepare_or_overwrite_a_new_claim() -> None:
    from app.agents.tools.logistics_updates import InMemoryLogisticsRepository

    now = [datetime(2026, 10, 29, tzinfo=UTC)]
    repository = InMemoryLogisticsRepository(clock=lambda: now[0])
    await repository.record(_observation(0))
    event = await repository.record(_observation(1))
    first = await repository.claim(event.context)
    assert isinstance(first, uuid.UUID)
    assert await repository.claim(event.context) is None
    now[0] += timedelta(minutes=11)
    second = await repository.claim(event.context)
    assert second is not None and second != first
    assert not await repository.prepare(event.context, "Old owner", "preview", claim_token=first)
    await repository.finish(event.context, "blocked", "old_owner", claim_token=first)
    assert (await repository.get(event.context)).state == "reviewing"
    assert await repository.prepare(event.context, "Current owner", "preview", claim_token=second)
    assert await repository.claim(event.context) is None
    await repository.finish(event.context, "previewed", claim_token=second)
    await repository.finish(event.context, "failed", "old_owner", claim_token=first)
    row = await repository.get(event.context)
    assert row.state == "previewed" and row.reviewed_text == "Current owner"


@pytest.mark.asyncio
async def test_late_review_after_lease_recovery_cannot_replace_new_owner_preview() -> None:
    from app.agents.tools.logistics_updates import InMemoryLogisticsRepository, ReviewDecision

    now = [datetime(2026, 10, 29, tzinfo=UTC)]
    service, _, delivery = _service()
    service.repository = InMemoryLogisticsRepository(clock=lambda: now[0])
    entered, release = asyncio.Event(), asyncio.Event()

    async def review(context, text):
        if text == "Old owner":
            entered.set()
            await release.wait()
        return ReviewDecision(status="approved", text=text)

    service.review = review
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    old = asyncio.create_task(service.notify(event.context, "Old owner"))
    await entered.wait()
    now[0] += timedelta(minutes=11)
    assert (await service.notify(event.context, "Current owner")).status == "previewed"
    release.set()
    await old
    assert len(delivery.previews) == 1 and delivery.previews[0].text == "Current owner"


@pytest.mark.asyncio
async def test_sql_repository_persists_baseline_claim_and_unknown_across_service_recreation() -> None:
    """SQLite 真执行 SQL；生产 PostgreSQL 行锁并发由集成门禁另外验证。"""
    from contextlib import asynccontextmanager

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.agents.tools.logistics_updates.models import LogisticsNotification, LogisticsObservationRow
    from app.agents.tools.logistics_updates.proof import NotificationAuthorization, text_sha256
    from app.agents.tools.logistics_updates.repository import SqlAlchemyLogisticsRepository

    class AsyncFacade:
        def __init__(self, session):
            self.session = session

        async def scalar(self, statement):
            return self.session.scalar(statement)

        async def execute(self, statement):
            return self.session.execute(statement)

        def add(self, row):
            self.session.add(row)

        @asynccontextmanager
        async def begin(self):
            with self.session.begin():
                yield

    engine = create_engine("sqlite://")
    # 被引用的父表只用于 FK 元数据解析，本测试不创建或读取业务父表。
    import app.shared.database.models  # noqa: F401

    LogisticsObservationRow.__table__.create(engine)
    LogisticsNotification.__table__.create(engine)

    @asynccontextmanager
    async def sessions():
        with Session(engine) as session:
            yield AsyncFacade(session)

    def proof(context, text):
        return NotificationAuthorization(
            event_key=context.idempotency_key,
            text_sha256=text_sha256(text),
            policy_revision=1,
            authorized_by=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            agent_version=1,
            prompt_hash="0" * 64,
            file_versions=(),
            required_permissions=frozenset({"workspace.reply", "orders.view"}),
        )

    repo = SqlAlchemyLogisticsRepository(sessions, authorization=proof)
    delivery = LocalDelivery(status="unknown")
    service, _, _ = _service(mode="external", delivery=delivery)
    service.repository = repo
    await service.observe(_observation(0))
    event = await service.observe(_observation(1))
    assert (await service.notify(event.context, "Latest update")).status == "unknown"
    restarted, _, _ = _service(mode="external", delivery=delivery)
    restarted.repository = SqlAlchemyLogisticsRepository(sessions, authorization=proof)
    assert (await restarted.observe(_observation(0))).status == "ignored"
    assert (await restarted.notify(event.context, "Repeat")).status == "unknown"
    assert len(delivery.sent) == 1
    delivery.status = "succeeded"
    assert (await restarted.reconcile(event.context)).status == "succeeded"
    forged = event.context.model_copy(update={"scope": _scope(store_id=uuid.UUID(int=99))})
    assert (await restarted.notify(forged, "Cross store")).status == "context_unavailable"
    from app.agents.tools.logistics_updates import LogisticsObservation

    fresh = LogisticsObservation.model_validate(
        {
            **_observation(3, scope=_scope(order_id=uuid.UUID(int=6))).model_dump(),
            "first_observation": "notify",
        }
    )
    assert (await restarted.observe_and_notify(fresh)).status == "succeeded"
    assert len(delivery.sent) == 2
    engine.dispose()
