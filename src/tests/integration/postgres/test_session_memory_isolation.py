"""会话记忆在隔离 PostgreSQL 中验证身份、关闭恢复和版本冲突。"""

import os
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_memory_scope_close_reopen_and_revision_conflict() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="记忆隔离", code=f"memory-{uuid.uuid4().hex}")
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
                content="请用中文回复",
                status="received",
            )
            session.add(trigger)
            await session.commit()

            from app.agents.memory.service import (
                commit_memory,
                load_memory,
                propose_memory_update,
                remember_session_question,
            )
            from app.agents.runtime.snapshot import freeze_run_context
            from app.agents.tools.loop import ToolObservation

            snapshot = await freeze_run_context(
                session,
                store_id=store.id,
                conversation_id=conversation.id,
                trigger_message_id=trigger.id,
                published_agents=(),
                memory_revision=0,
            )
            proposal = propose_memory_update(
                snapshot,
                summary="买家希望中文回复。",
                source_message_ids=(trigger.id,),
                facts=(),
                authorized_tool_call_ids=frozenset(),
            )
            assert await commit_memory(session, snapshot, proposal, expected_revision=0) == 1
            loaded = await load_memory(session, replace(snapshot, memory_revision=1))
            assert loaded.summary == "买家希望中文回复。"
            assert loaded.source_message_ids == (trigger.id,)
            assert (
                await remember_session_question(
                    session,
                    replace(snapshot, memory_revision=1),
                    loaded,
                    trigger.content,
                    ((uuid.uuid4(), ToolObservation("call-1", "query_order", "succeeded", {"status": "shipped"})),),
                )
                == 2
            )
            loaded = await load_memory(session, replace(snapshot, memory_revision=2))
            assert [(fact.key, fact.value) for fact in loaded.facts] == [("query_order.status", "shipped")]
            with pytest.raises(AppError) as stale:
                await commit_memory(session, snapshot, proposal, expected_revision=0)
            assert stale.value.status_code == 409

            conversation.status = "closed"
            await session.commit()
            closed_snapshot = replace(snapshot, memory_revision=2)
            assert (await load_memory(session, closed_snapshot)).revision == 2
            with pytest.raises(AppError) as closed:
                await commit_memory(session, closed_snapshot, proposal, expected_revision=2)
            assert closed.value.status_code == 409

            conversation.status = "active"
            await session.commit()
            assert "请用中文回复" in (await load_memory(session, closed_snapshot)).summary
            with pytest.raises(AppError) as foreign:
                await load_memory(session, replace(closed_snapshot, customer_id=uuid.uuid4()))
            assert foreign.value.status_code == 404
            with pytest.raises(AppError) as foreign_store:
                await load_memory(session, replace(closed_snapshot, store_id=uuid.uuid4()))
            assert foreign_store.value.status_code == 404

            other = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=uuid.uuid4().hex,
            )
            session.add(other)
            await session.commit()
            other_scope = replace(closed_snapshot, conversation_id=other.id, memory_revision=0)
            assert (await load_memory(session, other_scope)).revision == 0
            assert (await load_memory(session, other_scope)).summary == ""

            from app.agents.memory.models import AgentSessionMemory

            await session.delete(conversation)
            await session.commit()
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AgentSessionMemory)
                    .where(AgentSessionMemory.conversation_id == conversation.id)
                )
                == 0
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()
