"""隔离数据库验证真实内部写入、幂等、当前权限和会话边界。"""

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未提供隔离 PostgreSQL")


@pytest.mark.asyncio
async def test_internal_notes_are_idempotent_scoped_and_never_send_or_transfer():
    from app.agents.runtime.models import AgentRun
    from app.agents.tools.business import AgentBusinessExecutor
    from app.agents.tools.collaboration import list_collaboration
    from app.agents.tools.models import AgentCollaborationEntry

    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, other_id, user_id, customer_id, conv_id, run_id = (uuid.uuid4() for _ in range(6))
    snapshot = SimpleNamespace(
        store_id=store_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        debug_without_conversation=False,
        message_ids=(),
    )
    try:
        async with sessions() as session:
            session.add_all(
                [
                    Store(id=store_id, name="合成工具店", code=f"tools-{store_id.hex}"),
                    Store(id=other_id, name="隔离店", code=f"tools-{other_id.hex}"),
                    User(
                        id=user_id, name="合成坐席", password_hash="unused", email=f"tools-{user_id.hex}@example.test"
                    ),
                ]
            )
            await session.flush()
            role = await session.scalar(select(Role).where(Role.code == "admin"))
            await session.execute(insert(user_roles).values(user_id=user_id, role_id=role.id, store_id=store_id))
            session.add(Customer(id=customer_id, store_id=store_id, name="合成买家"))
            await session.flush()
            session.add(
                Conversation(
                    id=conv_id,
                    store_id=store_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_conversation_id=conv_id.hex,
                    status="active",
                )
            )
            await session.flush()
            session.add(
                AgentRun(
                    id=run_id,
                    store_id=store_id,
                    conversation_id=conv_id,
                    status="running",
                    action="human_review",
                    model_provider="deepseek",
                    model_name="test-model",
                    prompt_version="test-tools",
                    trace_id="test",
                )
            )
            await session.commit()

        async def invoke():
            async with sessions() as session:
                user = await session.get(User, user_id)
                executor = AgentBusinessExecutor(
                    session, user, snapshot, run_id, frozenset({"workspace.reply", "workspace.view"}), "test-trace"
                )
                return await executor.invoke("create_handoff_request", {"content": "买家询问退款进度，请人工核实。"})

        results = await asyncio.gather(invoke(), invoke())
        assert all(item["status"] == "succeeded" for item in results)
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AgentCollaborationEntry)
                    .where(AgentCollaborationEntry.store_id == store_id)
                )
                == 1
            )
            user = await session.get(User, user_id)
            rows = await list_collaboration(session, user, conv_id)
            assert len(rows) == 1 and rows[0].is_ai_suggestion
            assert rows[0].kind == "handoff_request"
            conv = await session.get(Conversation, conv_id)
            assert conv.status == "active" and conv.assigned_user_id is None
            assert (
                await session.scalar(
                    select(func.count()).select_from(Message).where(Message.conversation_id == conv_id)
                )
                == 0
            )
            logs = (await session.scalars(select(AuditLog).where(AuditLog.store_id == store_id))).all()
            assert logs and "退款进度" not in str([log.after_data for log in logs])
            bad = SimpleNamespace(**{**vars(snapshot), "store_id": other_id})
            executor = AgentBusinessExecutor(session, user, bad, run_id, frozenset({"workspace.reply"}), "bad")
            assert (await executor.invoke("add_internal_note", {"content": "不允许跨店写入"}))["status"] != "succeeded"
            from app.agents.tools.access import tool_catalog
            from app.shared.exceptions.errors import AppError

            await session.refresh(user)
            view = await tool_catalog(session, user, store_id)
            assert len(view.groups) == 6 and len(view.tools) == 16
            with pytest.raises(AppError):
                await tool_catalog(session, user, other_id)
            first = Message(
                id=uuid.uuid4(),
                store_id=store_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="Earlier verified message",
                status="received",
            )
            late = Message(
                id=uuid.uuid4(),
                store_id=store_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="Arrived after freeze",
                status="received",
            )
            session.add_all([first, late])
            await session.commit()
            frozen = SimpleNamespace(**{**vars(snapshot), "message_ids": (first.id,)})
            executor = AgentBusinessExecutor(
                session, user, frozen, run_id, frozenset({"workspace.view", "workspace.reply"}), "read"
            )
            history = await executor.invoke("query_conversation_messages", {})
            assert history["status"] == "succeeded"
            assert "Earlier verified message" in str(history) and "Arrived after freeze" not in str(history)
            frozen.message_ids = (first.id, uuid.uuid4())
            history = await executor.invoke("query_conversation_messages", {})
            assert history["facts"]["next_offset"] is None
            profile = await executor.invoke("query_customer_profile", {})
            assert profile["status"] == "succeeded" and "phone" not in profile["facts"]
            note = await executor.invoke("add_internal_note", {"content": "AI 建议：请核实处理进度。"})
            assert note["status"] == "succeeded"
            rows = await list_collaboration(session, user, conv_id)
            assert {row.kind for row in rows} == {"handoff_request", "internal_note"}
            await session.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
            await session.commit()
            assert (await invoke())["status"] != "succeeded"
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_([store_id, other_id])))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
