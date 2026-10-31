"""子 Agent 从发布版本选择原生工具，回答只携带可信工具事实。"""

import time
import uuid
from datetime import UTC, datetime, timedelta
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.management.repository import PublishedAgent
from app.agents.memory.service import MemoryFact
from app.agents.orchestration.router import RoutedAgent
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.runtime.context import ModelLimits
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.runtime.worker import run_specialist
from app.agents.tools.catalog import AgentToolContext
from app.tools.contracts import ToolResult


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer,expected_reason",
    [
        ("物流仍在运输中。", None),
        ("Ship to 123 Main Street, New York, NY 10001", None),
        (None, "no_agent_answer"),
        (" ", "invalid_agent_answer"),
    ],
)
async def test_specialist_calls_configured_logistics_tool_without_regex_route(
    monkeypatch, answer, expected_reason
) -> None:
    store, conversation, customer, agent_id = (uuid.uuid4() for _ in range(4))
    sections = {key: "只按当前授权和证据处理。" for key, _ in SECTION_TITLES}
    prompt = compile_prompt(sections)
    agent = PublishedAgent(
        id=agent_id,
        store_id=store,
        config_version=2,
        name="物流助手",
        code="shipping",
        description="负责物流",
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType(sections),
        prompt_hash=prompt.content_sha256,
        tool_names=("query_logistics",),
        file_ids=(),
        ready_for_v2=True,
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(
        store_id=store,
        conversation_id=conversation,
        customer_id=customer,
        trigger_message_id=uuid.uuid4(),
        trigger_created_at=now,
        message_ids=(),
        published_agents=(agent,),
        file_versions=(),
        memory_revision=0,
        frozen_at=now,
        snapshot_hash="hash",
    )
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn(
                    None,
                    (FunctionCall("call_1", "query_logistics", {}),),
                    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1"}]},
                    10,
                    5,
                ),
                ToolTurn(answer, (), {"role": "assistant", "content": answer}, 10, 5),
            ]
        )
    )
    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolResult(
                tool_call_id=uuid.uuid4(),
                status="succeeded",
                data={"tracking_status": "in_transit"},
            )
        )
    )
    result = await run_specialist(
        snapshot=snapshot,
        agent=agent,
        selection=RoutedAgent(agent_id, "Where is the parcel?", "zh-CN"),
        provider=provider,
        executor=executor,
        rag_service=None,
        session=AsyncMock(),
        tool_context=AgentToolContext(
            store, uuid.uuid4(), "trusted-order", customer, frozenset({"orders.view"}), "trace"
        ),
        deadline=time.monotonic() + 5,
        model_limits=ModelLimits(8000, 1024, 256),
        customer_question="我的包裹在哪里",
    )
    assert result.reason_code == expected_reason
    assert result.answer == (answer if expected_reason is None else None)
    assert [(event.name, event.status) for event in result.tool_events] == [("query_logistics", "succeeded")]
    assert (result.input_tokens, result.output_tokens) == (20, 10)
    if expected_reason is None:
        assert result.verified_facts == {"query_logistics.tracking_status": "in_transit"}
        assert result.successful_tools == ("query_logistics",)
    else:
        assert not result.verified_facts
    assert executor.execute.await_count == 1
    first_call = provider.complete.await_args_list[0].kwargs
    import json

    question_data = json.loads(first_call["messages"][-1]["content"])
    assert question_data["question_language"] == "zh-CN"
    assert question_data["untrusted_question"] == "我的包裹在哪里"
    assert [tool.name for tool in first_call["tools"]] == ["query_logistics"]
    from app.agents.rag.search import RagRetrievalTimeout
    from app.agents.runtime import worker

    monkeypatch.setattr(worker, "run_tool_loop", AsyncMock(side_effect=RagRetrievalTimeout("RAG_RETRIEVAL_TIMEOUT")))
    timed_out = await run_specialist(
        snapshot=snapshot,
        agent=agent,
        selection=RoutedAgent(agent_id, "物流政策"),
        provider=provider,
        executor=executor,
        rag_service=None,
        session=AsyncMock(),
        tool_context=AgentToolContext(
            store, uuid.uuid4(), "trusted-order", customer, frozenset({"orders.view"}), "trace"
        ),
        deadline=time.monotonic() + 5,
        model_limits=ModelLimits(8000, 1024, 256),
    )
    assert timed_out.reason_code == "rag_retrieval_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("can_read_orders", [True, False])
async def test_specialist_context_preserves_authorized_fresh_fact_and_expires_old_fact(can_read_orders) -> None:
    store, conversation, customer, agent_id = (uuid.uuid4() for _ in range(4))
    sections = {key: "仅根据当前授权事实处理。" for key, _ in SECTION_TITLES}
    prompt = compile_prompt(sections)
    agent = PublishedAgent(
        id=agent_id,
        store_id=store,
        config_version=1,
        name="记忆助手",
        code="memory",
        description="会话上下文",
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections=MappingProxyType(sections),
        prompt_hash=prompt.content_sha256,
        tool_names=("query_order",),
        file_ids=(),
        ready_for_v2=True,
    )
    now = datetime.now(UTC)
    snapshot = RunSnapshot(store, conversation, customer, uuid.uuid4(), now, (), (agent,), (), 1, now, "memory-hash")
    provider = SimpleNamespace(
        complete=AsyncMock(
            return_value=ToolTurn(
                "已读取会话上下文。", (), {"role": "assistant", "content": "已读取会话上下文。"}, 4, 3
            )
        )
    )
    await run_specialist(
        snapshot=snapshot,
        agent=agent,
        selection=RoutedAgent(agent_id, "继续上次问题"),
        provider=provider,
        executor=SimpleNamespace(execute=AsyncMock()),
        rag_service=None,
        session=AsyncMock(),
        tool_context=AgentToolContext(
            store, uuid.uuid4(), None, customer, frozenset({"orders.view"}) if can_read_orders else frozenset(), "trace"
        ),
        deadline=time.monotonic() + 5,
        model_limits=ModelLimits(8000, 1024, 256),
        session_facts=(
            MemoryFact("query_order.status", "shipped", f"tool:{uuid.uuid4()}", now),
            MemoryFact("query_logistics.tracking_status", "delivered", f"tool:{uuid.uuid4()}", now - timedelta(days=1)),
        ),
    )
    messages = provider.complete.await_args.kwargs["messages"]
    assert ("query_order.status" in str(messages)) is can_read_orders
    assert ("shipped" in str(messages)) is can_read_orders
    assert "query_logistics.tracking_status" not in str(messages)
