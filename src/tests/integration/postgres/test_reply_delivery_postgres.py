"""隔离PostgreSQL验证交付计划行锁、跨请求恢复和消息边界。"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.delivery.batches import BatchRunner
from app.agents.delivery.contracts import ReplyBatchRequest
from app.agents.delivery.repository import SqlBatchStore
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.database.base import User
from app.stores.models import Store
from app.workspace.schemas import MessageView

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未提供隔离PostgreSQL")


@asynccontextmanager
async def database():
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, user_id, customer_id, conversation_id = (uuid.uuid4() for _ in range(4))
    try:
        async with sessions() as session:
            session.add_all(
                [
                    Store(id=store_id, name="合成交付店", code=f"batch-{store_id.hex}"),
                    User(
                        id=user_id, name="合成坐席", password_hash="unused", email=f"batch-{user_id.hex}@example.test"
                    ),
                ]
            )
            await session.flush()
            session.add(Customer(id=customer_id, store_id=store_id, name="合成买家"))
            await session.flush()
            session.add(
                Conversation(
                    id=conversation_id,
                    store_id=store_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_conversation_id=conversation_id.hex,
                )
            )
            await session.commit()
        yield sessions, store_id, user_id, conversation_id
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


def message(status):
    return MessageView(
        id=uuid.uuid4(),
        role="assistant",
        content="Reviewed",
        status=status,
        created_at=datetime.now(UTC),
        error_code=None,
        delivery_mode="mock",
    )


def plan():
    return ReplyBatchRequest(
        parts=[{"kind": "text", "content": "Latest update"}, {"kind": "logistics_card", "order_id": "600001"}],
        preview_only=False,
        confirmed=True,
    )


@pytest.mark.asyncio
async def test_concurrent_duplicate_claim_and_restart_never_resends_text():
    async with database() as (sessions, store_id, user_id, conversation_id):
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def send(part, key):
            calls.append((part.kind, key))
            if part.kind == "text":
                entered.set()
                await release.wait()
            return message("failed" if len(calls) == 2 else "sent")

        async def run():
            async with sessions() as session:
                store = SqlBatchStore(session, store_id, conversation_id, user_id)
                return await BatchRunner(store, send).run("scope", "key", plan())

        first = asyncio.create_task(run())
        await entered.wait()
        assert (await run()).status == "unknown"
        release.set()
        assert (await first).status == "partial"
        assert (await run()).status == "completed"
        assert [kind for kind, _ in calls] == ["text", "logistics_card", "logistics_card"]
        assert calls[1][1] != calls[2][1]
        assert (await run()).status == "completed"
        assert len(calls) == 3


@pytest.mark.asyncio
async def test_cancelled_owner_and_changed_body_remain_fail_closed_after_restart():
    from app.shared.exceptions.errors import AppError

    async with database() as (sessions, store_id, user_id, conversation_id):
        entered = asyncio.Event()
        calls = []

        async def send(part, key):
            calls.append(key)
            entered.set()
            await asyncio.Event().wait()

        async def run(payload):
            async with sessions() as session:
                return await BatchRunner(SqlBatchStore(session, store_id, conversation_id, user_id), send).run(
                    "scope", "key", payload
                )

        task = asyncio.create_task(run(plan()))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await run(plan())).status == "unknown"
        changed = plan().model_copy(update={"parts": [plan().parts[0]]})
        with pytest.raises(AppError):
            await run(changed)
        assert len(calls) == 1


@pytest.mark.asyncio
async def test_review_preview_accepts_actual_user_message_and_rejects_other_trigger(monkeypatch):
    from unittest.mock import AsyncMock

    from app.agents.delivery import service
    from app.shared.exceptions.errors import AppError

    async with database() as (sessions, store_id, user_id, conversation_id):
        monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={store_id}))
        monkeypatch.setattr(service, "current_permissions", AsyncMock(return_value={"workspace.reply"}))
        async with sessions() as session:
            conversation = await session.get(Conversation, conversation_id)
            trigger_id = uuid.uuid4()
            session.add(
                Message(
                    id=trigger_id,
                    store_id=store_id,
                    conversation_id=conversation_id,
                    customer_id=conversation.customer_id,
                    platform="tiktok",
                    external_message_id=trigger_id.hex,
                    role="user",
                    direction="inbound",
                    content="Where is my parcel?",
                    status="received",
                )
            )
            await session.commit()
            actor = await session.get(User, user_id)
            payload = ReplyBatchRequest(
                trigger_message_id=trigger_id, parts=[{"kind": "text", "content": "Your parcel is in transit."}]
            )
            result = await service.deliver_reviewed_batch(session, actor, conversation_id, payload, "preview")
            assert result.status == "previewed" and result.messages == []
            payload.trigger_message_id = uuid.uuid4()
            with pytest.raises(AppError) as raised:
                await service.deliver_reviewed_batch(session, actor, conversation_id, payload, "other")
            assert raised.value.status_code == 404


@pytest.mark.asyncio
async def test_old_completion_cannot_overwrite_new_attempt_in_postgres():
    async with database() as (sessions, store_id, user_id, conversation_id):
        async with sessions() as session:
            store = SqlBatchStore(session, store_id, conversation_id, user_id)
            await store.start("scope", "key", plan())
            first = await store.claim("scope", "key", 0)
            await store.finish("scope", "key", 0, first, message("failed"))
            second = await store.claim("scope", "key", 0)
            await store.finish("scope", "key", 0, first, message("failed"))
            assert await store.claim("scope", "key", 0) is None
            assert (await store.read("scope", "key"))["parts"][0]["status"] == "unknown"
            await store.finish("scope", "key", 0, second, message("sent"))
            assert (await store.read("scope", "key"))["parts"][0]["status"] == "sent"
