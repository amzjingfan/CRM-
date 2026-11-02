"""接待账本、撤权、最早未答与发送前竞态的隔离 PostgreSQL 行为。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.agents.automation.authorization import authorize_delivery
from app.agents.automation.models import AutomationDelivery
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.reception.automation import (
    APPROVED_COPY,
    authorize_reception_delivery,
    collect_due_reception_deliveries,
    on_reception_inbound,
    on_reception_outbound,
)
from app.reception.models import ReceptionConversationState, ReceptionPolicy, ReceptionPolicyStore
from app.shared.config.settings import Settings
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


async def seed_reception(session):
    store_id, customer_id, actor_id, conversation_id = (uuid.uuid4() for _ in range(4))
    session.add_all(
        [
            Store(
                id=store_id,
                name="接待自动化合成店",
                code=f"rec_{store_id.hex}",
                status="active",
                timezone="UTC",
            ),
            User(
                id=actor_id,
                name="接待自动化测试管理员",
                login_name=f"r{actor_id.hex[:12]}",
                password_hash="test",
                status="active",
            ),
        ]
    )
    await session.flush()
    admin_role = await session.scalar(select(Role.id).where(Role.code == "admin"))
    assert admin_role is not None
    await session.execute(user_roles.insert().values(user_id=actor_id, role_id=admin_role, store_id=None))
    session.add(Customer(id=customer_id, store_id=store_id, platform="tiktok", external_customer_id=customer_id.hex))
    await session.flush()
    conversation = Conversation(
        id=conversation_id,
        store_id=store_id,
        customer_id=customer_id,
        platform="tiktok",
        external_conversation_id=conversation_id.hex,
        status="active",
    )
    session.add(conversation)
    policies = []
    for kind in ("welcome", "timeout"):
        policy = ReceptionPolicy(
            id=uuid.uuid4(),
            kind=kind,
            name=kind,
            content=APPROVED_COPY[kind][0],
            timeout_minutes=60 if kind == "timeout" else None,
            enabled=True,
            delivery_mode="auto",
            welcome_idle_hours=24,
            revision=1,
            created_at=datetime.now(UTC) - timedelta(days=7),
            updated_at=datetime.now(UTC) - timedelta(days=7),
            created_by=actor_id,
            authorized_by=actor_id,
            stores=[ReceptionPolicyStore(store_id=store_id)],
        )
        session.add(policy)
        policies.append(policy)
    await session.flush()
    return (
        conversation,
        policies,
        Settings(app_env="test").model_copy(
            update={"real_tiktok_automation_enabled": True, "auto_reply_enabled": True}
        ),
    )


@pytest_asyncio.fixture
async def reception_db():
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    conversation, policies, settings = await seed_reception(session)
                    yield session, conversation, policies, settings
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def receive(session, conversation, settings, at, *, content="Hello", language="en"):
    message = Message(
        id=uuid.uuid4(),
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        customer_id=conversation.customer_id,
        platform="tiktok",
        external_message_id=uuid.uuid4().hex,
        role="user",
        direction="inbound",
        content=content,
        language=language,
        status="received",
        created_at=at,
        sent_at=at,
    )
    session.add(message)
    await session.flush()
    rows = await on_reception_inbound(session, conversation, message, settings)
    await session.flush()
    return message, rows


@pytest.mark.asyncio
@pytest.mark.parametrize("master,automatic", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize("mode", ["auto", "preview"])
async def test_reception_inbound_and_current_authorizer_share_two_switch_gate(reception_db, master, automatic, mode):
    session, conversation, policies, settings = reception_db
    for policy in policies:
        policy.delivery_mode = mode
        policy.updated_at = datetime.now(UTC) - timedelta(days=7)
    settings = settings.model_copy(update={"real_tiktok_automation_enabled": master, "auto_reply_enabled": automatic})
    _, rows = await receive(session, conversation, settings, datetime.now(UTC) - timedelta(minutes=61))
    assert len(rows) == (2 if mode == "preview" or (master and automatic) else 0)
    for row in rows:
        assert await authorize_reception_delivery(session, row, settings)
        if mode == "auto":
            stopped = settings.model_copy(update={"auto_reply_enabled": False})
            assert not await authorize_reception_delivery(session, row, stopped)
            assert not await authorize_delivery(session, row, stopped, verify_remote=False)


@pytest.mark.asyncio
async def test_welcome_once_timeout_earliest_and_24h_new_segment(reception_db):
    session, conversation, _, settings = reception_db
    now = datetime.now(UTC) - timedelta(minutes=61)
    first, rows = await receive(session, conversation, settings, now)
    assert len(rows) == 2
    welcome = next(row for row in rows if row.source_kind == "welcome")
    timeout = next(row for row in rows if row.source_kind == "timeout")
    assert welcome.content == APPROVED_COPY["welcome"][1]
    assert timeout.not_before == now + timedelta(minutes=60)
    assert len(await collect_due_reception_deliveries(session, settings)) == 2
    assert await authorize_reception_delivery(session, timeout, settings)
    _, repeated = await receive(
        session, conversation, settings, now + timedelta(minutes=59), content="你好", language="zh-CN"
    )
    assert repeated == []
    assert timeout.trigger_message_id == first.id
    assert timeout.not_before == now + timedelta(minutes=60)
    _, next_segment = await receive(session, conversation, settings, now + timedelta(hours=25))
    assert len([row for row in next_segment if row.source_kind == "welcome"]) == 1
    assert not await authorize_reception_delivery(session, welcome, settings)


@pytest.mark.asyncio
async def test_preview_off_policy_revision_and_revocation_fail_closed(reception_db):
    session, conversation, policies, settings = reception_db
    policies[0].delivery_mode = "preview"
    policies[1].delivery_mode = "off"
    await session.flush()
    _, rows = await receive(session, conversation, settings, datetime.now(UTC))
    assert len(rows) == 1 and rows[0].mode == "preview"
    assert await authorize_reception_delivery(session, rows[0], settings)
    assert await authorize_delivery(session, rows[0], settings, require_external=False)
    assert not await authorize_delivery(session, rows[0], settings, require_external=True)
    policies[0].delivery_mode = "auto"
    policies[0].revision += 1
    await session.flush()
    assert not await authorize_reception_delivery(session, rows[0], settings)
    _, new_rows = await receive(session, conversation, settings, datetime.now(UTC) + timedelta(hours=25))
    assert len(new_rows) == 1
    assert await authorize_reception_delivery(session, new_rows[0], settings)
    await session.execute(delete(user_roles).where(user_roles.c.user_id == policies[0].created_by))
    assert not await authorize_reception_delivery(session, new_rows[0], settings)


@pytest.mark.asyncio
async def test_successful_reply_cancels_timeout_even_before_hook(reception_db):
    session, conversation, _, settings = reception_db
    at = datetime.now(UTC) - timedelta(minutes=61)
    _, rows = await receive(session, conversation, settings, at)
    timeout = next(row for row in rows if row.source_kind == "timeout")
    welcome = next(row for row in rows if row.source_kind == "welcome")
    for source, status in (("welcome", "sent"), ("agent", "unknown"), ("agent", "failed")):
        message = Message(
            id=uuid.uuid4(),
            store_id=conversation.store_id,
            conversation_id=conversation.id,
            platform="tiktok",
            external_message_id=uuid.uuid4().hex,
            role="system",
            direction="outbound",
            content="Synthetic reply",
            status=status,
            sent_at=at + timedelta(minutes=1),
            raw_payload={"automation_source_kind": source},
        )
        session.add(message)
        await session.flush()
        await on_reception_outbound(session, conversation, message)
        assert await authorize_reception_delivery(session, timeout, settings)
    message = Message(
        id=uuid.uuid4(),
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        platform="tiktok",
        external_message_id=uuid.uuid4().hex,
        role="agent",
        direction="outbound",
        content="Human wins race",
        status="sent",
        sent_at=at + timedelta(minutes=2),
    )
    session.add(message)
    await session.flush()
    assert not await authorize_reception_delivery(session, timeout, settings)
    assert not await authorize_reception_delivery(session, welcome, settings)
    state = await session.get(ReceptionConversationState, conversation.id)
    assert state.unanswered_since is None
    await receive(session, conversation, settings, datetime.now(UTC))
    count = (
        await session.scalars(
            select(AutomationDelivery).where(
                AutomationDelivery.conversation_id == conversation.id, AutomationDelivery.source_kind == "timeout"
            )
        )
    ).all()
    assert len(count) == 2


@pytest.mark.asyncio
async def test_unpersisted_or_duplicate_inbound_never_creates_extra_rows(reception_db):
    session, conversation, _, settings = reception_db
    message, rows = await receive(session, conversation, settings, datetime.now(UTC))
    assert len(rows) == 2
    assert await on_reception_inbound(session, conversation, message, settings) == []
    fake = Message(id=uuid.uuid4(), direction="inbound", role="user", status="received")
    assert await on_reception_inbound(session, conversation, fake, settings) == []
    count = (
        await session.scalars(select(AutomationDelivery).where(AutomationDelivery.conversation_id == conversation.id))
    ).all()
    assert len(count) == 2


@pytest.mark.asyncio
async def test_enabling_or_revising_timeout_only_arms_new_trusted_inbound(reception_db):
    session, conversation, policies, settings = reception_db
    timeout_policy = policies[1]
    timeout_policy.delivery_mode = "off"
    await session.flush()
    _, old_rows = await receive(session, conversation, settings, datetime.now(UTC) - timedelta(hours=2))
    assert all(row.source_kind != "timeout" for row in old_rows)
    timeout_policy.delivery_mode = "auto"
    timeout_policy.revision += 1
    await session.flush()
    now = datetime.now(UTC)
    first, rows = await receive(session, conversation, settings, now)
    timeout = next(row for row in rows if row.source_kind == "timeout")
    assert timeout.source_key == str(first.id)
    assert timeout.not_before == now + timedelta(hours=1)
    timeout_policy.revision += 1
    await session.flush()
    assert not await authorize_reception_delivery(session, timeout, settings)
    _, newer = await receive(session, conversation, settings, now + timedelta(minutes=1))
    assert len(newer) == 1 and newer[0].source_kind == "timeout"
    assert newer[0].not_before == now + timedelta(minutes=61)


@pytest.mark.asyncio
async def test_late_historical_webhook_does_not_advance_new_policy_segment(reception_db):
    session, conversation, policies, settings = reception_db
    cutover = datetime.now(UTC) - timedelta(minutes=1)
    for policy in policies:
        policy.updated_at = cutover
    await session.flush()
    _, historical = await receive(session, conversation, settings, cutover - timedelta(minutes=1))
    assert historical == []
    state = await session.get(ReceptionConversationState, conversation.id)
    assert state.last_activity_at is None
    _, current = await receive(session, conversation, settings, datetime.now(UTC))
    assert sorted(row.source_kind for row in current) == ["timeout", "welcome"]


@pytest.mark.asyncio
async def test_distinct_delayed_inbound_moves_one_pending_timeout_earlier(reception_db):
    session, conversation, _, settings = reception_db
    later_at = datetime.now(UTC) - timedelta(minutes=10)
    later, rows = await receive(session, conversation, settings, later_at)
    timeout = next(row for row in rows if row.source_kind == "timeout")
    original_delivery_id = timeout.id
    earlier_at = later_at - timedelta(minutes=50)
    earlier, changed = await receive(session, conversation, settings, earlier_at)
    assert [row.id for row in changed] == [original_delivery_id]
    state = await session.get(ReceptionConversationState, conversation.id)
    assert state.last_activity_at == later_at
    assert state.segment_id == later.id
    assert state.unanswered_since == earlier_at
    assert state.unanswered_message_id == earlier.id
    assert timeout.source_key == str(earlier.id)
    assert timeout.trigger_message_id == earlier.id
    assert timeout.not_before == earlier_at + timedelta(minutes=60)
    assert await authorize_reception_delivery(session, timeout, settings)
    assert await on_reception_inbound(session, conversation, later, settings) == []
    assert await on_reception_inbound(session, conversation, earlier, settings) == []
    timers = (
        await session.scalars(
            select(AutomationDelivery).where(
                AutomationDelivery.conversation_id == conversation.id,
                AutomationDelivery.source_kind == "timeout",
            )
        )
    ).all()
    assert [row.id for row in timers] == [original_delivery_id]


@pytest.mark.asyncio
@pytest.mark.parametrize("call_reply_hook", [False, True])
async def test_delayed_inbound_cannot_cross_intervening_successful_reply(reception_db, call_reply_hook):
    session, conversation, _, settings = reception_db
    later_at = datetime.now(UTC) - timedelta(minutes=10)
    later, rows = await receive(session, conversation, settings, later_at)
    timeout = next(row for row in rows if row.source_kind == "timeout")
    reply = Message(
        id=uuid.uuid4(),
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        platform="tiktok",
        external_message_id=uuid.uuid4().hex,
        role="agent",
        direction="outbound",
        content="Earlier question already answered",
        status="sent",
        sent_at=later_at - timedelta(minutes=25),
    )
    session.add(reply)
    await session.flush()
    if call_reply_hook:
        await on_reception_outbound(session, conversation, reply)
    _, changed = await receive(session, conversation, settings, later_at - timedelta(minutes=50))
    assert changed == []
    assert timeout.trigger_message_id == later.id
    assert timeout.not_before == later_at + timedelta(minutes=60)
    state = await session.get(ReceptionConversationState, conversation.id)
    assert state.unanswered_message_id == later.id
    assert state.unanswered_since == later_at


@pytest.mark.asyncio
async def test_delayed_inbound_does_not_revive_cycle_cleared_by_newer_reply(reception_db):
    session, conversation, _, settings = reception_db
    at = datetime.now(UTC) - timedelta(minutes=10)
    _, rows = await receive(session, conversation, settings, at)
    timeout = next(row for row in rows if row.source_kind == "timeout")
    reply = Message(
        id=uuid.uuid4(),
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        platform="tiktok",
        external_message_id=uuid.uuid4().hex,
        role="agent",
        direction="outbound",
        content="Answered",
        status="sent",
        sent_at=at + timedelta(minutes=1),
    )
    session.add(reply)
    await session.flush()
    await on_reception_outbound(session, conversation, reply)
    _, changed = await receive(session, conversation, settings, at - timedelta(minutes=50))
    assert changed == []
    state = await session.get(ReceptionConversationState, conversation.id)
    assert state.unanswered_since is None
    assert timeout.not_before == at + timedelta(minutes=60)


@pytest.mark.asyncio
async def test_two_sessions_process_same_inbound_once():
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    conversation_id = store_id = actor_id = None
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            conversation, policies, settings = await seed_reception(session)
            conversation_id, store_id, actor_id = conversation.id, conversation.store_id, policies[0].created_by
            trigger = Message(
                id=uuid.uuid4(),
                store_id=store_id,
                conversation_id=conversation_id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="Hello",
                language="en",
                status="received",
                created_at=datetime.now(UTC),
            )
            session.add(trigger)
            await session.commit()
            trigger_id = trigger.id

        async def process():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                conversation = await session.get(Conversation, conversation_id)
                message = await session.get(Message, trigger_id)
                assert conversation is not None and message is not None
                rows = await on_reception_inbound(session, conversation, message, settings)
                await session.commit()
                return len(rows)

        assert sorted(await asyncio.gather(process(), process())) == [0, 2]
        async with AsyncSession(engine) as session:
            rows = (
                await session.scalars(
                    select(AutomationDelivery).where(
                        AutomationDelivery.conversation_id == conversation_id,
                    )
                )
            ).all()
            assert sorted(row.source_kind for row in rows) == ["timeout", "welcome"]
    finally:
        if store_id is not None:
            async with AsyncSession(engine) as session:
                await session.execute(delete(ReceptionPolicy).where(ReceptionPolicy.created_by == actor_id))
                await session.execute(delete(Conversation).where(Conversation.id == conversation_id))
                await session.execute(delete(Customer).where(Customer.store_id == store_id))
                await session.execute(delete(Store).where(Store.id == store_id))
                await session.execute(delete(User).where(User.id == actor_id))
                await session.commit()
        await engine.dispose()
