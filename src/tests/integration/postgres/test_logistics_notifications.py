"""隔离 PostgreSQL 验证通知行锁、现权、jobs 与零外发预演。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.shared.database.models  # noqa: F401
from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import legacy_safe_sections
from app.agents.tools.logistics_updates import (
    LogisticsObservation,
    LogisticsScope,
    LogisticsUpdateService,
    ReviewDecision,
    TrackingEvent,
)
from app.agents.tools.logistics_updates.authorization import authorize_event, authorize_persisted_send
from app.agents.tools.logistics_updates.integration import VerifiedLogisticsSource
from app.agents.tools.logistics_updates.models import (
    LogisticsNotification,
    LogisticsNotificationPolicy,
    LogisticsOrderScan,
)
from app.agents.tools.logistics_updates.repository import SqlAlchemyLogisticsRepository
from app.agents.tools.logistics_updates.worker import claim_due_scan, finish_scan, process_logistics_notification_cycle
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.schemas import SendMessageResult
from app.orders.models import Order
from app.shared.config.settings import Settings
from app.shared.database.base import Role, User, user_roles
from app.stores.models import ChannelAccount, Store
from app.tools.contracts import SendPlatformMessageArguments, ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未提供隔离 PostgreSQL")


def _settings(*, external: bool = False, enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        **{
            "APP_ENV": "development",
            "LLM_ENABLED": True,
            "LLM_PRIMARY_PROVIDER": "openai",
            "LLM_PRIMARY_MODEL": "synthetic",
            "LOGISTICS_NOTIFICATIONS_ENABLED": enabled,
            "REAL_TIKTOK_LOGISTICS_NOTIFICATIONS_ENABLED": external,
            "REAL_TIKTOK_READ_ENABLED": True,
            "REAL_TIKTOK_MESSAGE_WRITE_ENABLED": external,
            "TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID": "710688832392260838",
            "TIKTOK_APP_KEY": "unit-test-app-key",
            "TIKTOK_SERVICE_ID": "unit-test-service-id",
            "TIKTOK_APP_SECRET": "unit-test-app-secret-value",
            "TIKTOK_OAUTH_REDIRECT_URI": "https://example.com/v1/integrations/tiktok/oauth/callback",
            "TIKTOK_CREDENTIAL_ENCRYPTION_KEY": "unit-test-encryption-key-with-at-least-32-characters",
            "TIKTOK_EGRESS_IP": "203.0.113.10",
            "TIKTOK_EGRESS_PROXY_URL": "socks5h://127.0.0.1:1080",
            "TIKTOK_REQUIRED_SCOPES": (
                "seller.authorization.info,seller.order.info,seller.customer_service,seller.logistics"
            ),
        },
    )


@pytest.fixture
async def shop(monkeypatch):
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, other_store, user_id, customer_id, conv_id, order_id, agent_id = (uuid.uuid4() for _ in range(7))
    now = datetime.now(UTC)
    compiled = compile_prompt(legacy_safe_sections())
    async with sessions() as session:
        session.add_all(
            [
                Store(id=store_id, name="合成物流店", code=f"logistics-{store_id.hex}"),
                Store(id=other_store, name="合成隔离店", code=f"logistics-{other_store.hex}"),
                User(id=user_id, name="合成授权坐席", password_hash="unused", email=f"{user_id.hex}@example.test"),
            ]
        )
        await session.flush()
        role = await session.scalar(select(Role).where(Role.code == "admin"))
        await session.execute(insert(user_roles).values(user_id=user_id, role_id=role.id, store_id=store_id))
        session.add(Customer(id=customer_id, store_id=store_id, platform="tiktok", external_customer_id="991100"))
        await session.flush()
        session.add_all(
            [
                Conversation(
                    id=conv_id,
                    store_id=store_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_conversation_id="710688832392260838",
                    status="active",
                ),
                Order(
                    id=order_id,
                    store_id=store_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_order_id="771100",
                    status="IN_TRANSIT",
                    currency="USD",
                ),
                AgentConfig(
                    id=agent_id,
                    store_id=store_id,
                    name="合成物流Agent",
                    code=f"logistics-{agent_id.hex}",
                    status="enabled",
                    published_version=1,
                    enabled_tools=["notify_logistics_update"],
                ),
                ChannelAccount(
                    store_id=store_id,
                    platform="tiktok",
                    external_store_id=store_id.hex,
                    display_name="合成渠道",
                    access_token_ref="synthetic-unused",
                    status="connected",
                    scopes=["seller.order.info", "seller.customer_service", "seller.logistics"],
                    token_expires_at=now + timedelta(days=1),
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                AgentConfigVersion(
                    store_id=store_id,
                    agent_config_id=agent_id,
                    version=1,
                    name="合成物流Agent",
                    code=f"logistics-{agent_id.hex}",
                    agent_type="service",
                    model_provider="openai",
                    model_name="synthetic",
                    prompt_sections=dict(compiled.sections),
                    prompt_hash=compiled.content_sha256,
                    tool_names=["notify_logistics_update"],
                    file_ids=[],
                    ready_for_v2=True,
                ),
                LogisticsNotificationPolicy(
                    store_id=store_id,
                    agent_id=agent_id,
                    authorized_by=user_id,
                    enabled=True,
                    mode="preview",
                    enabled_at=now - timedelta(hours=1),
                    revision=1,
                ),
            ]
        )
        await session.commit()
    scope = LogisticsScope(
        store_id=store_id,
        customer_id=customer_id,
        conversation_id=conv_id,
        order_id=order_id,
        package_id="verified-package",
    )

    async def remote_window(*args, **kwargs):
        return True, True, True

    monkeypatch.setattr("app.agents.tools.logistics_updates.authorization.verified_remote_window", remote_window)
    result = SimpleNamespace(
        sessions=sessions,
        store_id=store_id,
        other_store=other_store,
        user_id=user_id,
        agent_id=agent_id,
        scope=scope,
        now=now,
    )
    try:
        yield result
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_([store_id, other_store])))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


def _observation(shop, offset: int, *, first: str = "baseline"):
    return LogisticsObservation(
        scope=shop.scope,
        buyer_language="en",
        first_observation=first,
        events=(
            TrackingEvent(
                occurred_at=shop.now - timedelta(minutes=10) + timedelta(seconds=offset),
                status="in_transit",
                description=f"Hub {offset}",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_postgres_concurrent_observation_and_review_claim_produce_one_preview(shop):
    from app.agents.tools.logistics_updates import DeliveryReceipt

    repo = SqlAlchemyLogisticsRepository(shop.sessions)
    assert (await repo.record(_observation(shop, 0))).status == "baseline"
    observations = await asyncio.gather(*(repo.record(_observation(shop, 1)) for _ in range(8)))
    assert sum(result.status == "pending" for result in observations) == 1
    event = next(result.context for result in observations if result.context is not None)
    previews = []

    async def authorize(context):
        async with shop.sessions() as session:
            return await authorize_event(session, _settings(), context)

    async def review(context, text):
        await asyncio.sleep(0)
        return ReviewDecision(status="approved", text=text)

    async def preview(notification):
        previews.append(notification)
        return DeliveryReceipt(status="succeeded")

    service = LogisticsUpdateService(
        repository=repo,
        authorize=authorize,
        review=review,
        generate=AsyncGeneratorNotCalled,
        delivery=SimpleNamespace(preview=preview),
    )
    results = await asyncio.gather(*(service.notify(event, "Your parcel arrived at the hub.") for _ in range(8)))
    assert any(result.status == "previewed" for result in results)
    assert len(previews) == 1
    async with shop.sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == shop.store_id))
            == 0
        )


async def AsyncGeneratorNotCalled(context):
    raise AssertionError("test supplies a candidate and must not invoke generation")


@pytest.mark.asyncio
async def test_executor_job_notification_uses_ledger_without_forged_human_and_revocation_blocks_next(shop, monkeypatch):
    settings = _settings(external=True)
    async with shop.sessions() as session:
        policy = await session.get(LogisticsNotificationPolicy, shop.store_id)
        policy.mode = "external"
        await session.commit()
    repo = SqlAlchemyLogisticsRepository(shop.sessions)
    await repo.record(_observation(shop, 0))
    recorded = await repo.record(_observation(shop, 1))
    token = await repo.claim(recorded.context)
    assert token is not None
    assert await repo.prepare(recorded.context, "Your parcel arrived.", "external", claim_token=token)
    sent = []

    class LocalAdapter:
        real_writes = True

        async def send_message(self, channel, command):
            assert not command.human_confirmed and command.logistics_notification_authorized
            sent.append(command)
            return SendMessageResult(status="sent", mock=False, external_message_id=str(uuid.uuid4().int))

    monkeypatch.setattr("app.tools.executor.get_settings", lambda: settings)
    monkeypatch.setattr("app.tools.executor.get_message_adapter", lambda platform: LocalAdapter())

    def invocation(context):
        return ToolInvocation(
            tool_name="send_platform_message",
            idempotency_key=context.idempotency_key,
            arguments={"conversation_id": str(shop.scope.conversation_id), "content": "Your parcel arrived."},
            context=ToolExecutionContext(
                store_id=shop.store_id,
                actor_type="job",
                actor_id=shop.user_id,
                permissions={"workspace.reply"},
                human_confirmed=False,
                logistics_notification_key=context.idempotency_key,
            ),
        )

    async with shop.sessions() as session:
        forged = SendPlatformMessageArguments(conversation_id=shop.scope.conversation_id, content="Injected promise")
        assert not await authorize_persisted_send(session, settings, invocation(recorded.context), forged)
    async with shop.sessions() as session:
        result = await SqlAlchemyToolExecutor(session).execute(invocation(recorded.context))
        assert result.status == "succeeded" and not result.mocked
    async with shop.sessions() as session:
        replay = await SqlAlchemyToolExecutor(session).execute(invocation(recorded.context))
        assert replay.status == "succeeded" and replay.replayed
    assert len(sent) == 1
    second = await repo.record(_observation(shop, 2))
    token = await repo.claim(second.context)
    assert token is not None
    assert await repo.prepare(second.context, "Your parcel arrived.", "external", claim_token=token)
    async with shop.sessions() as session:
        policy = await session.get(LogisticsNotificationPolicy, shop.store_id)
        policy.enabled = False
        await session.commit()
    async with shop.sessions() as session:
        blocked = await SqlAlchemyToolExecutor(session).execute(invocation(second.context))
        assert blocked.status == "failed" and blocked.error_code == "TOOL_LOGISTICS_NOTIFICATION_NOT_AUTHORIZED"
        assert (
            await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == shop.store_id))
            == 1
        )
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_postgres_scan_claim_is_per_order_eight_hours_and_failure_backs_off(shop):
    settings = _settings()
    claims = await asyncio.gather(*(claim_due_scan(shop.sessions, settings) for _ in range(8)))
    claimed = [claim for claim in claims if claim is not None]
    assert len(claimed) == 1
    async with shop.sessions() as session:
        row = await session.get(LogisticsOrderScan, (shop.store_id, shop.scope.order_id))
        assert row.next_poll_at >= shop.now + timedelta(hours=8)
    await finish_scan(shop.sessions, settings, claimed[0], "observation_unavailable")
    async with shop.sessions() as session:
        row = await session.get(LogisticsOrderScan, (shop.store_id, shop.scope.order_id))
        assert row.failure_count == 1 and row.next_poll_at >= shop.now + timedelta(hours=16)
        assert row.claim_token is None


@pytest.mark.asyncio
async def test_jobs_cycle_persists_reviewed_preview_without_outbound_messages(shop, monkeypatch):
    from app.agents.tools.logistics_updates import ReviewDecision

    async def source(*args, **kwargs):
        return VerifiedLogisticsSource((_observation(shop, 1, first="notify"),), "Where is my parcel?")

    class LocalModel:
        input_tokens = 4
        output_tokens = 5

        def __init__(self, *args):
            pass

        async def generate(self, context):
            return "Your parcel arrived at the hub."

        async def review(self, context, text):
            return ReviewDecision(status="approved", text=text)

    monkeypatch.setattr("app.agents.tools.logistics_updates.worker.read_verified_observations", source)
    monkeypatch.setattr("app.agents.tools.logistics_updates.worker.NativeNotificationModel", LocalModel)
    assert await process_logistics_notification_cycle(shop.sessions, _settings())
    async with shop.sessions() as session:
        row = await session.scalar(select(LogisticsNotification).where(LogisticsNotification.store_id == shop.store_id))
        assert row.state == "previewed" and row.reviewed_text == "Your parcel arrived at the hub."
        assert (
            await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == shop.store_id))
            == 0
        )


@pytest.mark.asyncio
async def test_manual_preview_works_with_background_off_without_consuming_ledger_and_invalidates_changed_policy(
    shop, monkeypatch
):
    from app.agents.tools.logistics_updates.integration import ManualLogisticsPreviewRequest, manual_preview

    async def source(*args, **kwargs):
        return VerifiedLogisticsSource((_observation(shop, 1),), "Where is my parcel?")

    changed = False

    class LocalModel:
        input_tokens = 2
        output_tokens = 3

        def __init__(self, *args):
            pass

        async def generate(self, context):
            return "Your parcel arrived."

        async def review(self, context, text):
            if changed:
                async with shop.sessions() as session:
                    policy = await session.get(LogisticsNotificationPolicy, shop.store_id)
                    policy.revision += 1
                    await session.commit()
            return ReviewDecision(status="approved", text=text)

    async def window(*args, **kwargs):
        return True, True, True

    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.read_verified_observations", source)
    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.NativeNotificationModel", LocalModel)
    monkeypatch.setattr("app.agents.tools.logistics_updates.integration.verified_remote_window", window)
    payload = ManualLogisticsPreviewRequest(
        store_id=shop.store_id, conversation_id=shop.scope.conversation_id, order_id=shop.scope.order_id
    )
    settings = _settings(enabled=False)
    async with shop.sessions() as session:
        user = await session.get(User, shop.user_id)
        result = await manual_preview(session, user, payload, settings)
        assert result.status == "previewed" and result.preview_text == "Your parcel arrived."
        assert not settings.logistics_notifications_enabled
        assert (
            await session.scalar(
                select(func.count())
                .select_from(LogisticsNotification)
                .where(LogisticsNotification.store_id == shop.store_id)
            )
            == 0
        )
        assert (
            await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == shop.store_id))
            == 0
        )
    changed = True
    async with shop.sessions() as session:
        user = await session.get(User, shop.user_id)
        result = await manual_preview(session, user, payload, settings)
        assert result.status == "blocked" and result.preview_text is None


@pytest.mark.asyncio
async def test_policy_http_requires_csrf_rechecks_store_and_rejects_stale_revision(shop):
    import httpx
    from fastapi import FastAPI

    from app.agents.tools.logistics_updates.http import router
    from app.auth.dependencies import get_current_user
    from app.shared.database.session import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/agents")

    async def db():
        async with shop.sessions() as session:
            yield session

    async def current_user():
        async with shop.sessions() as session:
            return await session.get(User, shop.user_id)

    from app.shared.exceptions.errors import AppError

    @app.exception_handler(AppError)
    async def app_error(request, error):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=error.status_code, content={"code": error.code.value})

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_current_user] = current_user
    payload = {"enabled": False, "agent_id": str(shop.agent_id), "mode": "preview", "expected_revision": 1}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        path = f"/agents/logistics-notifications/policy?store_id={shop.store_id}"
        assert (await client.patch(path, json=payload)).status_code == 403
        assert (
            await client.get(f"/agents/logistics-notifications/policy?store_id={shop.other_store}")
        ).status_code == 404
        accepted = await client.patch(path, json=payload, headers={"Authorization": "Bearer synthetic-test"})
        assert accepted.status_code == 200 and accepted.json()["data"]["revision"] == 2
        assert (
            await client.patch(path, json=payload, headers={"Authorization": "Bearer synthetic-test"})
        ).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("crash_state", ["pending", "expired_reviewing"])
async def test_worker_recovers_crashed_notification_before_eight_hour_poll_without_refetching_tracking(
    shop,
    monkeypatch,
    crash_state,
):
    repo = SqlAlchemyLogisticsRepository(shop.sessions)
    await repo.record(_observation(shop, 0))
    event = await repo.record(_observation(shop, 1))
    if crash_state == "expired_reviewing":
        assert await repo.claim(event.context) is not None
        async with shop.sessions() as session:
            notification = await session.get(LogisticsNotification, event.context.idempotency_key)
            notification.review_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
    # 模拟观察事务提交后进程退出；上一次官方订单扫描仍在八小时窗口内。
    scan = await claim_due_scan(shop.sessions, _settings())
    await finish_scan(shop.sessions, _settings(), scan, None)
    async with shop.sessions() as session:
        session.add(
            Message(
                store_id=shop.store_id,
                conversation_id=shop.scope.conversation_id,
                customer_id=shop.scope.customer_id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="Where is my parcel?",
                message_type="text",
                status="received",
            )
        )
        await session.commit()
        next_poll = (await session.get(LogisticsOrderScan, (shop.store_id, shop.scope.order_id))).next_poll_at

    class LocalModel:
        input_tokens = 2
        output_tokens = 3

        def __init__(self, *args):
            pass

        async def generate(self, context):
            return "Recovered latest logistics update."

        async def review(self, context, text):
            return ReviewDecision(status="approved", text=text)

    async def forbidden_refetch(*args, **kwargs):
        raise AssertionError("recovery must not refetch tracking inside eight-hour polling interval")

    monkeypatch.setattr("app.agents.tools.logistics_updates.worker.NativeNotificationModel", LocalModel)
    monkeypatch.setattr("app.agents.tools.logistics_updates.worker.read_verified_observations", forbidden_refetch)
    assert await process_logistics_notification_cycle(shop.sessions, _settings())
    row = await repo.get(event.context)
    assert row.state == "previewed" and row.reviewed_text == "Recovered latest logistics update."
    async with shop.sessions() as session:
        assert (await session.get(LogisticsOrderScan, (shop.store_id, shop.scope.order_id))).next_poll_at == next_poll
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.store_id == shop.store_id, Message.direction == "outbound")
            )
            == 0
        )


@pytest.mark.asyncio
async def test_postgres_expired_review_lease_has_one_new_owner_and_rejects_stale_preparation_and_finish(shop):
    repo = SqlAlchemyLogisticsRepository(shop.sessions)
    await repo.record(_observation(shop, 0))
    event = await repo.record(_observation(shop, 1))
    original = await repo.claim(event.context)
    assert original is not None
    assert await repo.claim(event.context) is None
    async with shop.sessions() as session:
        row = await session.get(LogisticsNotification, event.context.idempotency_key)
        row.review_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    claims = await asyncio.gather(*(repo.claim(event.context) for _ in range(8)))
    owners = [token for token in claims if token is not None]
    assert len(owners) == 1 and owners[0] != original
    current = owners[0]
    assert not await repo.prepare(event.context, "Stale owner body", "preview", claim_token=original)
    await repo.finish(event.context, "blocked", "stale_owner", claim_token=original)
    row = await repo.get(event.context)
    assert row.state == "reviewing" and row.review_claim_token == current
    assert await repo.prepare(event.context, "Current owner body", "preview", claim_token=current)
    # unknown 即使 review lease 已过期也不可领取，更不能被旧 owner 记成失败。
    async with shop.sessions() as session:
        persisted = await session.get(LogisticsNotification, event.context.idempotency_key)
        persisted.review_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    assert await repo.claim(event.context) is None
    await repo.finish(event.context, "failed", "stale_owner", claim_token=original)
    assert (await repo.get(event.context)).state == "unknown"
    await repo.finish(event.context, "previewed", claim_token=current)
    row = await repo.get(event.context)
    assert row.state == "previewed" and row.reviewed_text == "Current owner body"


@pytest.mark.asyncio
async def test_worker_unknown_only_reconciles_without_model_delivery_or_early_tracking_poll(shop, monkeypatch):
    repo = SqlAlchemyLogisticsRepository(shop.sessions)
    await repo.record(_observation(shop, 0))
    event = await repo.record(_observation(shop, 1))
    token = await repo.claim(event.context)
    assert token is not None
    assert await repo.prepare(event.context, "Original reviewed body", "external", claim_token=token)
    scan = await claim_due_scan(shop.sessions, _settings())
    await finish_scan(shop.sessions, _settings(), scan, None)

    def forbidden_model(*args, **kwargs):
        raise AssertionError("unknown must never be generated or delivered again")

    async def forbidden_tracking(*args, **kwargs):
        raise AssertionError("unknown recovery must not refetch tracking")

    monkeypatch.setattr("app.agents.tools.logistics_updates.worker.NativeNotificationModel", forbidden_model)
    monkeypatch.setattr("app.agents.tools.logistics_updates.worker.read_verified_observations", forbidden_tracking)
    assert not await process_logistics_notification_cycle(shop.sessions, _settings())
    row = await repo.get(event.context)
    assert row.state == "unknown" and row.reviewed_text == "Original reviewed body"
