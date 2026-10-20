"""在隔离 PostgreSQL 上验证会话操作字段、店铺范围和列表过滤。"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation
from app.customers.models import Customer
from app.orders.models import Order, OrderItem
from app.stores.models import Store
from app.workspace import service as workspace_service
from app.workspace.repository import list_conversations

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
async def test_starred_and_closed_filters_are_scoped_and_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            monkeypatch.setattr(
                workspace_service,
                "allowed_store_ids",
                AsyncMock(return_value={store_id}),
            )
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


@pytest.mark.asyncio
async def test_unified_search_matches_related_orders_without_cross_store_leakage() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(name="Search scope", code=f"workspace-search-{uuid.uuid4().hex}")
    other_store = Store(name="Other search scope", code=f"other-search-{uuid.uuid4().hex}")
    store_ids: list[uuid.UUID] = []
    try:
        async with sessions() as session:
            session.add_all([store, other_store])
            await session.flush()
            store_ids = [store.id, other_store.id]
            alice = Customer(store_id=store.id, name="Alice Buyer")
            bob = Customer(store_id=store.id, name="Bob Buyer")
            outsider = Customer(store_id=other_store.id, name="Alice Outsider")
            session.add_all([alice, bob, outsider])
            await session.flush()
            now = datetime.now(UTC)
            first = Conversation(
                store_id=store.id,
                customer_id=alice.id,
                platform="tiktok",
                external_conversation_id=str(uuid.uuid4().int),
                last_message_at=now,
            )
            second = Conversation(
                store_id=store.id,
                customer_id=bob.id,
                platform="tiktok",
                external_conversation_id=str(uuid.uuid4().int),
                last_message_at=now - timedelta(minutes=1),
            )
            other = Conversation(
                store_id=other_store.id,
                customer_id=outsider.id,
                platform="tiktok",
                external_conversation_id=str(uuid.uuid4().int),
                last_message_at=now,
            )
            session.add_all([first, second, other])
            order = Order(
                store_id=store.id,
                customer_id=alice.id,
                platform="tiktok",
                external_order_id="ORDER-ALICE-2026",
                status="shipped",
                currency="USD",
                tracking_number="TRACK-ALICE-9",
            )
            second_order = Order(
                store_id=store.id,
                customer_id=bob.id,
                platform="tiktok",
                external_order_id="ORDER-BOB-2026",
                status="paid",
                currency="USD",
            )
            contaminated = Order(
                store_id=other_store.id,
                customer_id=bob.id,
                platform="tiktok",
                external_order_id="CROSS-STORE-SECRET",
                status="paid",
                currency="USD",
            )
            session.add_all([order, second_order, contaminated])
            await session.flush()
            session.add(
                OrderItem(
                    order_id=second_order.id,
                    product_name="Blue walking pad",
                    sku="SKU-BLUE",
                    quantity=1,
                    unit_price=Decimal("99.00"),
                    total_amount=Decimal("99.00"),
                    created_at=now,
                )
            )
            await session.commit()

            actor = uuid.uuid4()
            for scope, term, expected in (
                ("buyer", "alice", first.id),
                ("order", "ORDER-ALICE", first.id),
                ("tracking", "track-alice", first.id),
                ("product", "walking pad", second.id),
                ("product", "SKU-BLUE", second.id),
            ):
                rows, total = await list_conversations(
                    session,
                    {store.id},
                    actor,
                    "all",
                    "tiktok",
                    None,
                    None,
                    1,
                    30,
                    scope,
                    (term,),
                )
                assert total == 1
                assert [row[0].id for row in rows] == [expected]

            rows, total = await list_conversations(
                session,
                {store.id},
                actor,
                "all",
                None,
                None,
                None,
                2,
                1,
                "all",
                ("Alice", "walking pad"),
            )
            assert total == 2
            assert [row[0].id for row in rows] == [second.id]
            leaked, leaked_total = await list_conversations(
                session,
                {store.id},
                actor,
                "all",
                None,
                None,
                None,
                1,
                30,
                "order",
                ("CROSS-STORE-SECRET",),
            )
            assert leaked == [] and leaked_total == 0
            literal_wildcard, wildcard_total = await list_conversations(
                session,
                {store.id},
                actor,
                "all",
                None,
                None,
                None,
                1,
                30,
                "buyer",
                ("%",),
            )
            assert literal_wildcard == [] and wildcard_total == 0
    finally:
        if store_ids:
            async with sessions() as session:
                await session.execute(delete(Store).where(Store.id.in_(store_ids)))
                await session.commit()
        await engine.dispose()
