"""真实数据库阻止并发旧草稿覆盖，并只读取冻结消息水位。"""

import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management import config_service
from app.agents.management.config_models import AgentConfig
from app.agents.management.schemas import AgentConfigUpdate
from app.agents.runtime.execution import load_snapshot_history
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未提供隔离 PostgreSQL")


@pytest.mark.asyncio
async def test_two_stale_draft_writers_cannot_both_commit(monkeypatch) -> None:
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="并发草稿测试", code=uuid.uuid4().hex)
    config = AgentConfig(id=uuid.uuid4(), store_id=store.id, name="旧名", code="draft", draft_revision=1)
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            session.add(config)
            await session.commit()
        monkeypatch.setattr(config_service, "allowed_store_ids", AsyncMock(return_value={store.id}))
        original = config_service.get_config
        ready = asyncio.Event()
        readers = 0

        async def both_read_before_lock(session, user, config_id, *, permission_code):
            nonlocal readers
            assert permission_code == "agent.manage"
            item = await original(session, user, config_id, permission_code=permission_code)
            readers += 1
            if readers == 2:
                ready.set()
            await ready.wait()
            return item

        monkeypatch.setattr(config_service, "get_config", both_read_before_lock)

        async def writer(name):
            async with sessions() as session:
                return await config_service.update_config(
                    session,
                    SimpleNamespace(id=uuid.uuid4()),
                    config.id,
                    AgentConfigUpdate(name=name, expected_revision=1),
                )

        results = await asyncio.wait_for(asyncio.gather(writer("新名甲"), writer("新名乙"), return_exceptions=True), 5)
        assert sum(isinstance(item, AppError) and item.status_code == 409 for item in results) == 1
        assert sum(not isinstance(item, BaseException) for item in results) == 1
        async with sessions() as session:
            saved = await session.scalar(select(AgentConfig).where(AgentConfig.id == config.id))
            assert saved.draft_revision == 2
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_history_excludes_messages_arriving_after_frozen_ids() -> None:
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="冻结历史测试", code=uuid.uuid4().hex)
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            customer = Customer(store_id=store.id, name="合成买家")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id, customer_id=customer.id, platform="tiktok", external_conversation_id=uuid.uuid4().hex
            )
            session.add(conversation)
            await session.flush()
            messages = [
                Message(
                    store_id=store.id,
                    conversation_id=conversation.id,
                    customer_id=customer.id,
                    platform="tiktok",
                    external_message_id=uuid.uuid4().hex,
                    role="user",
                    direction="inbound",
                    content=text,
                    status="received",
                )
                for text in ("之前问的是包裹", "稍后新增的消息")
            ]
            session.add_all(messages)
            await session.commit()
            history = await load_snapshot_history(
                session,
                SimpleNamespace(store_id=store.id, conversation_id=conversation.id, message_ids=(messages[0].id,)),
            )
            assert history == ("inbound: 之前问的是包裹",)
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()
