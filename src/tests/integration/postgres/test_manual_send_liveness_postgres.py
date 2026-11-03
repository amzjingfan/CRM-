"""人工发送区分平台前超时与平台结果未知，且不自动重放。"""

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.database import models as registered_models  # noqa: F401
from app.shared.database.base import Role, User, user_roles
from app.stores.models import ChannelAccount, Store
from app.tools import executor as executor_module
from app.tools.contracts import TOOL_DEFINITIONS, ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor
from app.tools.models import ToolCall

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_stage", ["conversation_lock", "after_pending_commit", "adapter_call"])
async def test_manual_send_timeout_tracks_actual_platform_boundary_without_automatic_replay(
    monkeypatch: pytest.MonkeyPatch,
    blocked_stage: str,
) -> None:
    """平台前锁等待可证明未发送；同键重放不得悄悄启动一次新发送。"""
    assert TEST_DATABASE_URL is not None
    target = make_url(TEST_DATABASE_URL)
    assert target.host == "127.0.0.1" and target.database == "crm_test" and target.username == "crm_test"
    assert not target.query
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, customer_id, conversation_id, actor_id = (uuid.uuid4() for _ in range(4))
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=f"manual-lock-{uuid.uuid4().hex}",
        arguments={"conversation_id": str(conversation_id), "content": "Synthetic approved reply"},
        context=ToolExecutionContext(
            store_id=store_id,
            actor_type="user",
            actor_id=actor_id,
            permissions={"workspace.reply"},
            human_confirmed=True,
        ),
    )
    definition = TOOL_DEFINITIONS["send_platform_message"]
    monkeypatch.setitem(TOOL_DEFINITIONS, "send_platform_message", definition.model_copy(update={"timeout_ms": 200}))

    adapter_started = False

    async def blocked_adapter(_channel: object, _command: object) -> None:
        nonlocal adapter_started
        adapter_started = True
        await asyncio.Event().wait()

    def adapter_for_stage(_platform: str) -> SimpleNamespace:
        if blocked_stage == "conversation_lock":
            raise AssertionError("会话锁尚未取得时不得进入平台适配器")
        return SimpleNamespace(real_writes=False, send_message=blocked_adapter)

    monkeypatch.setattr(executor_module, "get_message_adapter", adapter_for_stage)
    try:
        async with sessions() as setup:
            setup.add(Store(id=store_id, name="人工发送锁测试", code=f"manual-lock-{store_id.hex}"))
            setup.add(User(id=actor_id, name="合成客服", login_name=f"m{actor_id.hex[:12]}", password_hash="synthetic"))
            await setup.flush()
            role_id = await setup.scalar(select(Role.id).where(Role.code == "admin"))
            assert role_id is not None
            await setup.execute(user_roles.insert().values(user_id=actor_id, role_id=role_id, store_id=None))
            setup.add(
                ChannelAccount(
                    store_id=store_id,
                    platform="tiktok",
                    external_store_id=f"synthetic-{store_id.hex}",
                    display_name="合成店铺",
                    access_token_ref="unused-no-network",
                    status="connected",
                )
            )
            setup.add(Customer(id=customer_id, store_id=store_id, name="合成客户"))
            await setup.flush()
            setup.add(
                Conversation(
                    id=conversation_id,
                    store_id=store_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_conversation_id=f"synthetic-{conversation_id.hex}",
                    status="active",
                )
            )
            await setup.commit()
        async with sessions() as blocker, sessions() as sender:
            if blocked_stage == "conversation_lock":
                await blocker.scalar(select(Conversation).where(Conversation.id == conversation_id).with_for_update())
            if blocked_stage == "after_pending_commit":
                commit = sender.commit
                commits = 0

                async def block_after_pending_commit() -> None:
                    nonlocal commits
                    await commit()
                    commits += 1
                    if commits == 2:
                        await asyncio.Event().wait()

                monkeypatch.setattr(sender, "commit", block_after_pending_commit)
            result = await SqlAlchemyToolExecutor(sender).execute(invocation)
            expected_status = "unknown" if blocked_stage == "adapter_call" else "failed"
            expected_error = "TOOL_RESULT_UNKNOWN" if blocked_stage == "adapter_call" else "TOOL_TIMEOUT"
            assert result.status == expected_status and result.error_code == expected_error
            assert adapter_started is (blocked_stage == "adapter_call")
            persisted = await sender.get(ToolCall, result.tool_call_id)
            assert persisted is not None and persisted.status == expected_status
            expected_messages = 0 if blocked_stage == "conversation_lock" else 1
            assert (
                await sender.scalar(select(func.count(Message.id)).where(Message.store_id == store_id))
                == expected_messages
            )
            if expected_messages:
                message = await sender.scalar(select(Message).where(Message.store_id == store_id))
                assert (
                    message is not None and message.status == expected_status and message.error_code == expected_error
                )
            await blocker.rollback()
            replay = await SqlAlchemyToolExecutor(sender).execute(invocation)
            assert replay.replayed is True and replay.status == expected_status
            assert replay.tool_call_id == result.tool_call_id
            assert await sender.scalar(select(func.count(ToolCall.id)).where(ToolCall.store_id == store_id)) == 1
            assert (
                await sender.scalar(select(func.count(Message.id)).where(Message.store_id == store_id))
                == expected_messages
            )
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()
