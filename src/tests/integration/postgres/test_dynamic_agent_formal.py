"""正式会话在隔离数据库上走多 Agent 新链路并保留人工审核。"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.core.schemas import AgentAction
from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.memory.models import AgentSessionMemory
from app.agents.orchestration.aggregator import ReviewedSuggestion
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.orchestration.service import DynamicRunResult
from app.agents.runtime.models import AgentRun
from app.agents.runtime.state import RunPhase
from app.agents.tools.loop import ToolObservation
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_formal_message_routes_two_agents_and_never_auto_sends(monkeypatch) -> None:
    assert TEST_DATABASE_URL is not None
    from app.agents.runtime import formal
    from app.chat import service as chat_service

    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="正式测试", code=f"formal-v2-{uuid.uuid4().hex}")
    settings = SimpleNamespace(
        agent_v2_formal_enabled=True,
        llm_enabled=True,
        embedding_enabled=True,
        real_tiktok_read_enabled=False,
        agent_debug_timeout_seconds=5,
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-chat",
    )
    monkeypatch.setattr(formal, "get_settings", lambda: settings)
    monkeypatch.setattr(formal, "validate_tool_model", lambda *_args: None)
    monkeypatch.setattr(chat_service, "get_settings", lambda: settings)
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
                content="订单和物流现在怎样？",
                status="received",
            )
            session.add(trigger)
            configs = []
            for code in ("order", "logistics"):
                config = AgentConfig(
                    store_id=store.id, name=f"{code} Agent", code=code, status="enabled", published_version=1
                )
                session.add(config)
                await session.flush()
                session.add(
                    AgentConfigVersion(
                        store_id=store.id,
                        agent_config_id=config.id,
                        version=1,
                        name=config.name,
                        code=code,
                        description=f"处理{code}问题",
                        agent_type="service",
                        model_provider="deepseek",
                        model_name="deepseek-chat",
                        prompt_sections={},
                        prompt_hash="hash",
                        tool_names=[],
                        file_ids=[],
                        ready_for_v2=True,
                    )
                )
                configs.append(config)
            await session.commit()
            route = RoutePlan(tuple(RoutedAgent(item.id, trigger.content) for item in configs), 2, 3, 2)
            fake_result = DynamicRunResult(
                phase=RunPhase.REVIEW_READY,
                route=route,
                specialists=tuple(
                    SpecialistResult(
                        item.id,
                        f"{item.code} 已核查",
                        observations=(
                            ToolObservation(f"call-{item.code}", "query_order", "succeeded", {"status": "shipped"}),
                        ),
                        input_tokens=4,
                        output_tokens=2,
                    )
                    for item in configs
                ),
                suggestion=ReviewedSuggestion(
                    "订单和物流信息已核查，请坐席复核。",
                    "human_review",
                    None,
                    tuple(item.id for item in configs),
                    (),
                    3,
                    2,
                ),
                reason_code=None,
            )
            executor = AsyncMock(return_value=fake_result)
            monkeypatch.setattr(formal, "execute_model_run", executor)
            result = await formal.run_formal_suggestion(
                session,
                conversation=conversation,
                trigger=trigger,
                trace_id="formal-trace",
                permissions={"orders.view"},
                runtime=None,
            )
            assert result.action == AgentAction.HUMAN_REVIEW
            assert result.draft_reply == "订单和物流信息已核查，请坐席复核。"
            assert result.send_performed is False
            assert len(executor.await_args.kwargs["agents"]) == 2
            assert executor.await_args.kwargs["snapshot"].trigger_message_id == trigger.id
            parent = await session.get(AgentRun, result.agent_run_id)
            assert parent is not None and parent.phase == "review_ready"
            assert parent.input_tokens == 14
            assert parent.output_tokens == 8
            children = (await session.scalars(select(AgentRun).where(AgentRun.parent_run_id == parent.id))).all()
            assert {item.agent_config_id for item in children} == {item.id for item in configs}
            assert all(item.input_tokens == 4 and item.output_tokens == 2 for item in children)
            memory = await session.scalar(
                select(AgentSessionMemory).where(AgentSessionMemory.conversation_id == conversation.id)
            )
            assert memory is not None and memory.revision == 1
            assert "订单和物流现在怎样？" in memory.summary
            assert [(fact["key"], fact["value"]) for fact in memory.facts_json] == [("query_order.status", "shipped")]
            second = Message(
                store_id=store.id,
                conversation_id=conversation.id,
                customer_id=customer.id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="那什么时候能送达？",
                status="received",
            )
            session.add(second)
            await session.commit()
            await formal.run_formal_suggestion(
                session,
                conversation=conversation,
                trigger=second,
                trace_id="formal-trace-2",
                permissions={"orders.view"},
                runtime=None,
            )
            assert "订单和物流现在怎样？" in executor.await_args.kwargs["memory_summary"]
            await session.refresh(memory)
            assert memory.revision == 2
            assert "那什么时候能送达？" in memory.summary
            third = Message(
                store_id=store.id,
                conversation_id=conversation.id,
                customer_id=customer.id,
                platform="tiktok",
                external_message_id=uuid.uuid4().hex,
                role="user",
                direction="inbound",
                content="请再确认一下订单",
                status="received",
            )
            session.add(third)
            await session.commit()
            through_chat = await chat_service.run_agent_for_message(
                session,
                configs[0],
                conversation,
                third,
                "formal-trace-3",
                {"orders.view"},
            )
            assert through_chat.draft_reply == result.draft_reply
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()
