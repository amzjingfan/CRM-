"""在隔离 PostgreSQL 上验证会话操作字段、店铺范围和列表过滤。"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation
from app.customers.models import Customer
from app.stores.models import Store
from app.workspace import service as workspace_service
from app.workspace.repository import list_conversations

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
async def test_starred_and_closed_filters_are_scoped_and_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(name="Workspace actions", code=f"workspace-actions-{uuid.uuid4().hex}")
    store_id = None
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            store_id = store.id
            customer = Customer(store_id=store_id, name="Synthetic buyer")
            session.add(customer)
            await session.flush()
            active = Conversation(
                store_id=store_id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=str(uuid.uuid4().int),
            )
            closed = Conversation(
                store_id=store_id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=str(uuid.uuid4().int),
            )
            session.add_all([active, closed])
            await session.commit()

            actor = SimpleNamespace(id=uuid.uuid4())
            monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
            await workspace_service.set_conversation_star(session, actor, active.id, True)
            await workspace_service.set_conversation_closed(session, actor, closed.id, True)

            all_rows, all_total = await list_conversations(
                session, {store_id}, actor.id, "all", None, None, None, 1, 20
            )
            starred_rows, starred_total = await list_conversations(
                session, {store_id}, actor.id, "starred", None, None, None, 1, 20
            )
            closed_rows, closed_total = await list_conversations(
                session, {store_id}, actor.id, "closed", None, None, None, 1, 20
            )
            conflicting_rows, conflicting_total = await list_conversations(
                session, {store_id}, actor.id, "closed", None, None, "active", 1, 20
            )
            assert (all_total, starred_total, closed_total) == (1, 1, 1)
            assert (conflicting_rows, conflicting_total) == ([], 0)
            assert [row[0].id for row in all_rows] == [active.id]
            assert [row[0].id for row in starred_rows] == [active.id]
            assert [row[0].id for row in closed_rows] == [closed.id]
            assert closed_rows[0][0].closed_at is not None
    finally:
        if store_id is not None:
            async with sessions() as session:
                await session.execute(delete(Store).where(Store.id == store_id))
                await session.commit()
        await engine.dispose()
