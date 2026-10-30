"""自动派单只在合格店铺和在线客服之间执行。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation
from app.customers.models import Customer
from app.reception_assignment.dispatch import dispatch_conversation, dispatch_queued, requeue_offline_auto_assignments
from app.reception_assignment.models import ReceptionAgentConfig, ReceptionStoreConfig
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store
from app.users.models import Department, department_members, department_stores

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
async def test_dispatch_respects_default_off_presence_and_manual_owner() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    store_id, department_id, agent_id, backup_id, customer_id = (uuid.uuid4() for _ in range(5))
    try:
        async with sessions() as session:
            agent_role_id = await session.scalar(select(Role.id).where(Role.code == "agent"))
            assert agent_role_id is not None
            session.add_all(
                [
                    Store(id=store_id, name="派单测试店铺", code=f"dispatch_{store_id.hex}", status="active"),
                    Department(id=department_id, name=f"客服部 {department_id.hex}"),
                    User(id=agent_id, login_name=f"a{agent_id.hex[:12]}", name="测试客服", password_hash="test"),
                    User(id=backup_id, login_name=f"b{backup_id.hex[:12]}", name="备用客服", password_hash="test"),
                ]
            )
            await session.flush()
            session.add(
                Customer(id=customer_id, store_id=store_id, platform="tiktok", external_customer_id=customer_id.hex)
            )
            await session.flush()
            await session.execute(department_stores.insert().values(department_id=department_id, store_id=store_id))
            await session.execute(department_members.insert().values(department_id=department_id, user_id=agent_id))
            await session.execute(department_members.insert().values(department_id=department_id, user_id=backup_id))
            await session.execute(
                user_roles.insert().values(user_id=agent_id, role_id=agent_role_id, store_id=store_id)
            )
            await session.execute(
                user_roles.insert().values(user_id=backup_id, role_id=agent_role_id, store_id=store_id)
            )
            store_config = ReceptionStoreConfig(store_id=store_id, department_id=department_id)
            agent_config = ReceptionAgentConfig(store_id=store_id, user_id=agent_id, auto_enabled=True)
            backup_config = ReceptionAgentConfig(store_id=store_id, user_id=backup_id, auto_enabled=True)
            conversation = Conversation(
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id=f"dispatch_{uuid.uuid4().hex}",
                awaiting_reply_since=now,
            )
            session.add_all([store_config, agent_config, backup_config, conversation])
            await session.flush()

            assert await dispatch_conversation(session, conversation.id, now=now) is None
            assert conversation.assigned_user_id is None
            assert conversation.assignment_wait_reason == "disabled"
            store_config.enabled = True
            await session.flush()
            assert await dispatch_conversation(session, conversation.id, now=now) is None
            assert conversation.assignment_wait_reason == "no_online_agent"
            agent_config.last_heartbeat_at = now - timedelta(minutes=2)
            await session.flush()
            assert await dispatch_conversation(session, conversation.id, now=now) is None

            agent_config.last_heartbeat_at = now
            await session.flush()
            assert await dispatch_conversation(session, conversation.id, now=now) == agent_id
            assert conversation.assigned_user_id == agent_id
            assert conversation.assignment_source == "auto"
            assert conversation.assignment_wait_reason is None

            conversation.assignment_source = "manual"
            assert await dispatch_conversation(session, conversation.id, now=now) == agent_id
            assert conversation.assignment_source == "manual"
            queued = Conversation(
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id=f"queue_{uuid.uuid4().hex}",
                awaiting_reply_since=now,
            )
            session.add(queued)
            agent_config.capacity = 1
            await session.flush()
            assert await dispatch_conversation(session, queued.id, now=now) is None
            assert queued.assignment_wait_reason == "all_at_capacity"
            agent_config.capacity = 20
            agent_config.accepting = False
            await session.flush()
            assert await dispatch_conversation(session, queued.id, now=now) is None
            assert queued.assignment_wait_reason == "no_online_agent"
            assert await dispatch_queued(session, now=now) == 0
            assert queued.next_assignment_attempt_at == now + timedelta(seconds=30)
            agent_config.accepting = True
            agent_config.last_heartbeat_at = now + timedelta(seconds=31)
            await session.flush()
            assert await dispatch_queued(session, now=now + timedelta(seconds=10)) == 0
            assert await dispatch_queued(session, now=now + timedelta(seconds=31)) == 1
            assert queued.assigned_user_id == agent_id
            assert queued.assignment_wait_reason is None
            backup_config.last_heartbeat_at = now + timedelta(minutes=3)
            assert await requeue_offline_auto_assignments(session, now=now + timedelta(minutes=3)) == 1
            assert queued.assigned_user_id == backup_id
            assert queued.assignment_source == "auto"
            assert conversation.assigned_user_id == agent_id
            assert conversation.assignment_source == "manual"
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_dispatch_respects_one_agent_capacity() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    store_id, department_id, agent_id, customer_id = (uuid.uuid4() for _ in range(4))
    try:
        async with sessions() as session:
            role_id = await session.scalar(select(Role.id).where(Role.code == "agent"))
            assert role_id is not None
            session.add_all(
                [
                    Store(id=store_id, name="并发派单店铺", code=f"capacity_{store_id.hex}", status="active"),
                    Department(id=department_id, name=f"客服部 {department_id.hex}"),
                    User(id=agent_id, login_name=f"a{agent_id.hex[:12]}", name="唯一客服", password_hash="test"),
                ]
            )
            await session.flush()
            session.add(Customer(id=customer_id, store_id=store_id, platform="tiktok"))
            await session.flush()
            await session.execute(department_stores.insert().values(department_id=department_id, store_id=store_id))
            await session.execute(department_members.insert().values(department_id=department_id, user_id=agent_id))
            await session.execute(user_roles.insert().values(user_id=agent_id, role_id=role_id, store_id=store_id))
            session.add_all(
                [
                    ReceptionStoreConfig(store_id=store_id, department_id=department_id, enabled=True),
                    ReceptionAgentConfig(
                        store_id=store_id, user_id=agent_id, auto_enabled=True, capacity=1, last_heartbeat_at=now
                    ),
                ]
            )
            conversation_ids = [uuid.uuid4(), uuid.uuid4()]
            session.add_all(
                Conversation(
                    id=conversation_id,
                    store_id=store_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_conversation_id=f"capacity_{conversation_id.hex}",
                    awaiting_reply_since=now,
                )
                for conversation_id in conversation_ids
            )
            await session.commit()

        async def assign(conversation_id: uuid.UUID) -> uuid.UUID | None:
            async with sessions() as session:
                result = await dispatch_conversation(session, conversation_id, now=now)
                await session.commit()
                return result

        results = await asyncio.gather(*(assign(conversation_id) for conversation_id in conversation_ids))
        assert results.count(agent_id) == 1
        assert results.count(None) == 1
        async with sessions() as session:
            rows = (await session.scalars(select(Conversation).where(Conversation.id.in_(conversation_ids)))).all()
            assert sum(row.assigned_user_id == agent_id for row in rows) == 1
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(Department).where(Department.id == department_id))
            await session.execute(delete(User).where(User.id == agent_id))
            await session.commit()
        await engine.dispose()
