"""隔离 PostgreSQL 上冻结 Agent 会话水位与店铺身份。"""

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_snapshot_excludes_messages_arriving_after_trigger_and_rejects_other_store() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="快照测试", code=f"snapshot-{uuid.uuid4().hex}")
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            customer = Customer(store_id=store.id, name="合成客户")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=uuid.uuid4().hex,
            )
            session.add(conversation)
            await session.flush()
            trigger = Message(
                store_id=store.id,
                conversation_id=conversation.id,
                customer_id=customer.id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="我的物流在哪",
                status="received",
            )
            session.add(trigger)
            await session.commit()

            from app.agents.runtime.snapshot import freeze_run_context

            snapshot = await freeze_run_context(
                session,
                store_id=store.id,
                conversation_id=conversation.id,
                trigger_message_id=trigger.id,
                published_agents=(),
                memory_revision=0,
            )
            late = Message(
                store_id=store.id,
                conversation_id=conversation.id,
                customer_id=customer.id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="后来发的新问题",
                status="received",
            )
            session.add(late)
            await session.commit()
            assert trigger.id in snapshot.message_ids
            assert late.id not in snapshot.message_ids
            assert snapshot.customer_id == customer.id
            assert len(snapshot.snapshot_hash) == 64

            with pytest.raises(AppError) as error:
                await freeze_run_context(
                    session,
                    store_id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    trigger_message_id=trigger.id,
                    published_agents=(),
                    memory_revision=0,
                )
            assert error.value.status_code == 404
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_debug_snapshot_without_conversation_has_isolated_ephemeral_identity() -> None:
    assert TEST_DATABASE_URL is not None
    from app.agents.runtime.snapshot import freeze_debug_context

    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        first = await freeze_debug_context(session, store_id=uuid.uuid4(), conversation_id=None, published_agents=())
        second = await freeze_debug_context(session, store_id=first.store_id, conversation_id=None, published_agents=())
    await engine.dispose()
    assert first.debug_without_conversation
    assert first.message_ids == ()
    assert first.customer_id != second.customer_id
    assert first.conversation_id != second.conversation_id
