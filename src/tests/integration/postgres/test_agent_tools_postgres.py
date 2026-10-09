"""在真实 PostgreSQL 上验证 Agent 白名单工具的隔离、权限、幂等和审计。"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.models import AgentRun
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.schemas import SendMessageResult
from app.orders.models import Order
from app.stores.models import ChannelAccount, Store
from app.tools import executor as executor_module
from app.tools.contracts import ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor
from app.tools.models import ToolCall

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_real_send_stops_when_prior_send_was_interrupted_after_pending_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上次发送遗留 processing 时，新幂等键也不得再触发平台写入。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(name="Interrupted send", code=f"send-orphan-{uuid.uuid4().hex}")
    send_message = AsyncMock(return_value=SendMessageResult(external_message_id="123456789", status="sent", mock=False))
    monkeypatch.setattr(
        executor_module,
        "get_message_adapter",
        lambda _platform: SimpleNamespace(real_writes=True, send_message=send_message),
    )
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            store_id = store.id
            customer = Customer(store_id=store.id, name="受控测试客户")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=f"{uuid.uuid4().int}",
                status="active",
            )
            channel = ChannelAccount(
                store_id=store.id,
                platform="tiktok",
                external_store_id=f"shop-{uuid.uuid4().hex}",
                display_name="Test shop",
                access_token_ref="test-only",
                status="connected",
            )
            session.add_all([conversation, channel])
            await session.flush()
            session.add_all(
                [
                    Message(
                        store_id=store.id,
                        conversation_id=conversation.id,
                        customer_id=customer.id,
                        platform="tiktok",
                        external_message_id=f"pending-{uuid.uuid4()}",
                        idempotency_key="interrupted-send",
                        role="agent",
                        direction="outbound",
                        content="earlier approved text",
                        status="processing",
                        raw_payload={"delivery_mode": "unknown"},
                    ),
                    ToolCall(
                        store_id=store.id,
                        actor_type="user",
                        actor_id=uuid.uuid4(),
                        tool_name="send_platform_message",
                        idempotency_key="interrupted-send",
                        request_hash="0" * 64,
                        status="running",
                        input_summary={},
                    ),
                ]
            )
            await session.commit()

            result = await SqlAlchemyToolExecutor(session).execute(
                ToolInvocation(
                    tool_name="send_platform_message",
                    idempotency_key=f"next-send-{uuid.uuid4().hex}",
                    arguments={"conversation_id": str(conversation.id), "content": "next approved text"},
                    context=ToolExecutionContext(
                        store_id=store.id,
                        actor_type="user",
                        actor_id=uuid.uuid4(),
                        permissions={"workspace.reply"},
                        human_confirmed=True,
                    ),
                )
            )
            assert result.status == "failed"
            assert result.error_code == "TOOL_RECONCILIATION_REQUIRED"
            send_message.assert_not_awaited()
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_agent_query_tool_records_run_and_enforces_store_and_permission() -> None:
    """查询工具必须关联运行记录，且跨店铺和缺权限都失败关闭。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(name="Agent tools", code=f"agent-tools-{uuid.uuid4().hex}")
    other_store = Store(name="Other", code=f"agent-tools-other-{uuid.uuid4().hex}")
    try:
        async with sessions() as session:
            session.add_all([store, other_store])
            await session.flush()
            customer = Customer(store_id=store.id, name="测试客户")
            other_customer = Customer(store_id=other_store.id, name="其他店铺客户")
            session.add_all([customer, other_customer])
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=f"conv-{uuid.uuid4().hex}",
                status="active",
            )
            session.add(conversation)
            await session.flush()
            order = Order(
                store_id=store.id,
                customer_id=customer.id,
                platform="tiktok",
                external_order_id=f"ORDER-{uuid.uuid4().hex}",
                status="shipped",
                payment_status="paid",
                fulfillment_status="shipped",
                currency="USD",
                tracking_number="TRACKING-SENSITIVE",
                tracking_status="in_transit",
            )
            other_order = Order(
                store_id=other_store.id,
                customer_id=other_customer.id,
                platform="shopee",
                external_order_id=f"OTHER-{uuid.uuid4().hex}",
                status="shipped",
                currency="USD",
            )
            run = AgentRun(
                store_id=store.id,
                conversation_id=conversation.id,
                model_provider="test",
                model_name="test",
                action="human_review",
                status="running",
                trace_id="trace-agent-tools",
            )
            session.add_all([order, other_order, run])
            store_id = store.id
            other_store_id = other_store.id
            order_external_id = order.external_order_id
            other_order_external_id = other_order.external_order_id
            run_id = run.id
            await session.commit()

            executor = SqlAlchemyToolExecutor(session)
            context = ToolExecutionContext(
                store_id=store_id,
                actor_type="agent",
                permissions={"orders.view"},
                agent_run_id=run_id,
                trace_id="trace-agent-tools",
            )
            success = await executor.execute(
                ToolInvocation(
                    tool_name="query_logistics",
                    idempotency_key=f"query-ok-{uuid.uuid4().hex}",
                    arguments={"order_id": order_external_id},
                    context=context,
                )
            )
            cross_store = await executor.execute(
                ToolInvocation(
                    tool_name="query_order",
                    idempotency_key=f"query-cross-{uuid.uuid4().hex}",
                    arguments={"order_id": other_order_external_id},
                    context=context,
                )
            )
            denied = await executor.execute(
                ToolInvocation(
                    tool_name="query_order",
                    idempotency_key=f"query-denied-{uuid.uuid4().hex}",
                    arguments={"order_id": order_external_id},
                    context=context.model_copy(update={"permissions": set()}),
                )
            )

            assert success.status == "succeeded"
            assert success.data is not None and success.data["tracking_status"] == "in_transit"
            assert cross_store.status == "failed"
            assert cross_store.error_code == "TOOL_RESOURCE_NOT_FOUND"
            assert denied.status == "failed"
            assert denied.error_code == "TOOL_PERMISSION_DENIED"
            calls = list((await session.scalars(select(ToolCall).where(ToolCall.agent_run_id == run_id))).all())
            assert len(calls) == 3
            assert all(call.input_summary.get("tracking_number") is None for call in calls)
            assert all("TRACKING-SENSITIVE" not in str(call.output_summary) for call in calls)
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_({store_id, other_store_id})))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_agent_transfer_is_idempotent_and_appends_audit_log() -> None:
    """转人工重放不得重复变更或重复审计，并必须关联同一工具调用。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(name="Transfer", code=f"agent-transfer-{uuid.uuid4().hex}")
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            customer = Customer(store_id=store.id, name="转人工客户")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="amazon",
                external_conversation_id=f"transfer-{uuid.uuid4().hex}",
                status="active",
            )
            session.add(conversation)
            await session.commit()
            invocation = ToolInvocation(
                tool_name="transfer_to_human",
                idempotency_key=f"transfer-key-{uuid.uuid4().hex}",
                arguments={
                    "conversation_id": str(conversation.id),
                    "reason": "agent_safety_handoff",
                    "assign_to": None,
                },
                context=ToolExecutionContext(
                    store_id=store.id,
                    actor_type="agent",
                    permissions={"workspace.transfer"},
                    trace_id="trace-transfer",
                ),
            )
            executor = SqlAlchemyToolExecutor(session)

            first = await executor.execute(invocation)
            replay = await executor.execute(invocation)
            conflict = await executor.execute(
                invocation.model_copy(
                    update={
                        "arguments": {
                            **invocation.arguments,
                            "reason": "different_reason_must_conflict",
                        }
                    }
                )
            )
            await session.refresh(conversation)

            audit_count = await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.store_id == store.id,
                    AuditLog.action == "conversation.transfer",
                )
            )
            tool_count = await session.scalar(
                select(func.count()).select_from(ToolCall).where(ToolCall.store_id == store.id)
            )
            assert first.status == "succeeded"
            assert replay.status == "succeeded" and replay.replayed is True
            assert replay.tool_call_id == first.tool_call_id
            assert conflict.status == "failed"
            assert conflict.error_code == "TOOL_IDEMPOTENCY_CONFLICT"
            assert conflict.tool_call_id == first.tool_call_id
            assert conversation.status == "transferred"
            assert conversation.transfer_reason == "agent_safety_handoff"
            assert audit_count == 1
            assert tool_count == 1
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()
