"""模型自主选择多个配置工具，并把结果按调用 ID 回送。"""

import asyncio
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.tools.contracts import ToolResult


def final_turn(content="Your question is being handled."):
    return ToolTurn(content, (), {"role": "assistant", "content": content}, 2, 1)


def calling_turn(*names):
    return ToolTurn(
        None,
        tuple(FunctionCall(f"call_{name}", name, {}) for name in names),
        {"role": "assistant", "content": None},
        2,
        1,
    )


@pytest.mark.asyncio
async def test_required_workflow_feedback_leads_to_native_missing_calls_without_server_invocation():
    import json

    from langchain_core.tools import tool

    from app.agents.tools.loop import run_tool_loop

    called = []

    @tool
    async def query_conversation_messages() -> dict:
        """读取合成会话历史。"""
        called.append("history")
        return {"status": "succeeded"}

    @tool
    async def create_handoff_request() -> dict:
        """生成内部接管记录。"""
        called.append("handoff")
        return {"status": "succeeded"}

    @tool
    async def add_internal_note() -> dict:
        """生成内部备注。"""
        called.append("note")
        return {"status": "succeeded"}

    tools = (query_conversation_messages, create_handoff_request, add_internal_note)
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                calling_turn("query_conversation_messages"),
                final_turn(),
                calling_turn("create_handoff_request", "add_internal_note"),
                final_turn(),
            ]
        )
    )
    result = await run_tool_loop(
        provider=provider,
        messages=(),
        tools=tools,
        required_tools=frozenset(item.name for item in tools),
        deadline=time.monotonic() + 2,
        max_output_tokens=256,
    )
    assert result.reason_code is None and result.answer == final_turn().content
    assert called == ["history", "handoff", "note"]
    assert [item.status for item in result.events] == ["succeeded"] * 3
    feedback = json.loads(provider.complete.await_args_list[2].kwargs["messages"][-1]["content"])
    assert feedback["required_tools_missing"] == ["add_internal_note", "create_handoff_request"]
    assert (result.input_tokens, result.output_tokens) == (8, 4)
    assert all(call.kwargs["max_output_tokens"] == 256 for call in provider.complete.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["missing", "failed", "oversized"])
async def test_same_missing_required_set_stops_on_second_final_without_faking_success(outcome):
    from langchain_core.tools import tool

    from app.agents.tools.loop import run_tool_loop

    @tool
    async def required_step() -> dict:
        """合成必需内部步骤。"""
        return {"status": "failed"} if outcome == "failed" else {"status": "succeeded", "facts": {"text": "x" * 17000}}

    turns = (
        [final_turn(), final_turn()]
        if outcome == "missing"
        else [calling_turn("required_step"), final_turn(), final_turn()]
    )
    provider = SimpleNamespace(complete=AsyncMock(side_effect=turns))
    result = await run_tool_loop(
        provider=provider,
        messages=(),
        tools=(required_step,),
        required_tools=frozenset({"required_step"}),
        deadline=time.monotonic() + 2,
        max_output_tokens=256,
    )
    assert result.answer is None and result.reason_code == "required_tools_incomplete"
    assert provider.complete.await_count == len(turns)
    assert [item.status for item in result.events] == (
        [] if outcome == "missing" else ["failed" if outcome == "failed" else "tool_result_too_large"]
    )


@pytest.mark.asyncio
async def test_required_debug_preview_completes_without_saving_business_records(monkeypatch):
    from unittest.mock import Mock

    from app.agents.tools.business import AgentBusinessExecutor
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools
    from app.agents.tools.loop import run_tool_loop

    session = SimpleNamespace(add=Mock(), commit=AsyncMock(), rollback=AsyncMock())
    snapshot = SimpleNamespace(store_id=uuid.uuid4(), conversation_id=uuid.uuid4(), customer_id=uuid.uuid4())
    saved = AsyncMock()
    monkeypatch.setattr("app.agents.tools.collaboration.save_collaboration", saved)
    business = AgentBusinessExecutor(
        session,
        SimpleNamespace(id=uuid.uuid4()),
        snapshot,
        uuid.uuid4(),
        frozenset({"workspace.reply"}),
        "workflow-preview",
        preview_only=True,
    )
    monkeypatch.setattr(business, "authorize", AsyncMock(return_value=SimpleNamespace(platform="tiktok")))
    names = ("create_handoff_request", "add_internal_note")
    context = AgentToolContext(
        snapshot.store_id, uuid.uuid4(), None, snapshot.customer_id, frozenset({"workspace.reply"}), "workflow-preview"
    )
    tools = build_agent_tools(
        names, context=context, executor=SimpleNamespace(execute=AsyncMock()), business_executor=business
    )
    calls = tuple(FunctionCall(name, name, {"content": "Please review this question."}) for name in names)
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                final_turn(),
                ToolTurn(None, calls, {"role": "assistant", "content": None}, 2, 1),
                final_turn(),
            ]
        )
    )
    result = await run_tool_loop(
        provider=provider,
        messages=(),
        tools=tools,
        required_tools=frozenset(names),
        deadline=time.monotonic() + 2,
        max_output_tokens=256,
    )
    assert result.answer is not None and result.reason_code is None
    assert [item.status for item in result.events] == ["previewed", "previewed"]
    saved.assert_not_awaited()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_loop_executes_two_read_calls_and_keeps_write_as_proposal() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools
    from app.agents.tools.loop import run_tool_loop

    responses = [
        ToolTurn(
            content=None,
            calls=(
                FunctionCall(id="call_order", name="query_order", arguments={}),
                FunctionCall(id="call_logistics", name="query_logistics", arguments={}),
                FunctionCall(id="call_send", name="send_platform_message", arguments={}),
            ),
            assistant_message={"role": "assistant", "content": None, "tool_calls": [{"id": "call_order"}]},
            input_tokens=10,
            output_tokens=10,
        ),
        ToolTurn(
            content="订单已发货，物流仍在运输中，具体到达时间无法确认。",
            calls=(),
            assistant_message={"role": "assistant", "content": "订单已发货，物流仍在运输中，具体到达时间无法确认。"},
            input_tokens=10,
            output_tokens=10,
        ),
    ]
    provider = SimpleNamespace(complete=AsyncMock(side_effect=responses))
    executor = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"status": "shipped"}),
                ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"tracking_status": "in_transit"}),
            ]
        )
    )
    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id="trusted-order",
        customer_id=None,
        permissions=frozenset({"orders.view"}),
        trace_id="trace",
    )
    catalog = build_agent_tools(
        ("query_order", "query_logistics", "send_platform_message"), context=context, executor=executor
    )
    result = await run_tool_loop(
        provider=provider,
        messages=({"role": "system", "content": "safe"}, {"role": "user", "content": "物流在哪"}),
        tools=catalog,
        deadline=time.monotonic() + 10,
        max_output_tokens=1024,
    )
    assert result.answer is not None
    assert [event.name for event in result.events] == ["query_order", "query_logistics", "send_platform_message"]
    assert executor.execute.await_count == 2
    second_messages = provider.complete.await_args_list[1].kwargs["messages"]
    assert [item["tool_call_id"] for item in second_messages if item["role"] == "tool"] == [
        "call_order",
        "call_logistics",
        "call_send",
    ]
    assert "human_confirmation_required" in str(second_messages)
    assert result.observations[0].facts == {"status": "shipped"}
    assert result.observations[1].facts == {"tracking_status": "in_transit"}
    assert result.observations[2].facts == {}


@pytest.mark.asyncio
async def test_repeated_invalid_call_stops_without_executing() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools
    from app.agents.tools.loop import run_tool_loop

    invalid = ToolTurn(
        content=None,
        calls=(FunctionCall(id="call_1", name="query_order", arguments={"order_id": "forged"}),),
        assistant_message={"role": "assistant", "content": None, "tool_calls": [{"id": "call_1"}]},
        input_tokens=1,
        output_tokens=1,
    )
    provider = SimpleNamespace(complete=AsyncMock(return_value=invalid))
    executor = SimpleNamespace(execute=AsyncMock())
    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id="trusted",
        customer_id=None,
        permissions=frozenset({"orders.view"}),
        trace_id="trace",
    )
    catalog = build_agent_tools(("query_order",), context=context, executor=executor)
    result = await run_tool_loop(
        provider=provider,
        messages=({"role": "user", "content": "查订单"},),
        tools=catalog,
        deadline=time.monotonic() + 10,
        max_output_tokens=1024,
    )
    assert result.answer is None
    assert result.reason_code == "repeated_invalid_tool_call"
    executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_generation_failure_keeps_completed_tool_events_and_known_usage() -> None:
    from langchain_core.tools import tool

    from app.agents.core.errors import LLMErrorCode, LLMProviderError
    from app.agents.tools.loop import run_tool_loop

    @tool
    async def read_order() -> dict:
        """查询合成订单状态。"""
        return {"status": "succeeded", "facts": {"status": "shipped"}}

    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn(None, (FunctionCall("order", "read_order", {}),), {}, 10, 5),
                LLMProviderError(
                    LLMErrorCode.LLM_OUTPUT_INVALID, "模型输出未完成", retriable=False, output_failure_kind="unfinished"
                ),
            ]
        )
    )
    result = await run_tool_loop(
        provider=provider, messages=(), tools=(read_order,), deadline=time.monotonic() + 2, max_output_tokens=1024
    )
    assert result.answer is None
    assert result.reason_code == "llm_output_unfinished"
    assert [(event.name, event.status) for event in result.events] == [("read_order", "succeeded")]
    assert (result.input_tokens, result.output_tokens) == (10, 5)


@pytest.mark.asyncio
async def test_cancellation_keeps_completed_tool_progress_and_stops_provider() -> None:
    from langchain_core.tools import tool

    from app.agents.tools.loop import run_tool_loop

    called = asyncio.Event()
    cancelled = asyncio.Event()

    @tool
    async def read_order() -> dict:
        """读取合成订单状态。"""
        return {"status": "succeeded", "facts": {"status": "shipped"}}

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            if not any(item.get("role") == "tool" for item in messages):
                return ToolTurn(None, (FunctionCall("order", "read_order", {}),), {}, 10, 5)
            called.set()
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.set()

    task = asyncio.create_task(
        run_tool_loop(
            provider=Model(), messages=(), tools=(read_order,), deadline=time.monotonic() + 20, max_output_tokens=1024
        )
    )
    await called.wait()
    task.cancel()
    result = await task
    assert cancelled.is_set()
    assert result.reason_code == "cancelled"
    assert [(event.name, event.status) for event in result.events] == [("read_order", "succeeded")]
    assert (result.input_tokens, result.output_tokens) == (10, 5)


@pytest.mark.asyncio
async def test_timeout_carries_completed_tool_progress_to_the_worker(monkeypatch) -> None:
    from langchain_core.tools import tool

    from app.agents.tools import loop

    clock = [0.0]
    monkeypatch.setattr(loop, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    @tool
    async def read_order() -> dict:
        """读取合成订单状态。"""
        # 在工具成功后推进逻辑时钟，避免机器负载耗尽20ms而误测成工具自身超时。
        clock[0] = 2.0
        return {"status": "succeeded", "facts": {"status": "shipped"}}

    class Model:
        async def complete(self, *, messages, tools, max_output_tokens):
            if not any(item.get("role") == "tool" for item in messages):
                return ToolTurn(None, (FunctionCall("order", "read_order", {}),), {}, 10, 5)
            await asyncio.sleep(30)

    with pytest.raises(TimeoutError) as caught:
        await loop.run_tool_loop(
            provider=Model(), messages=(), tools=(read_order,), deadline=1.0, max_output_tokens=1024
        )
    partial = getattr(caught.value, "result", None)
    assert partial is not None
    assert [(event.name, event.status) for event in partial.events] == [("read_order", "succeeded")]
    assert (partial.input_tokens, partial.output_tokens) == (10, 5)


@pytest.mark.asyncio
async def test_shared_deadline_cancels_waiting_provider() -> None:
    from app.agents.tools.loop import run_tool_loop

    async def slow(**_: object) -> None:
        await asyncio.sleep(1)

    provider = SimpleNamespace(complete=slow)
    with pytest.raises(TimeoutError):
        await run_tool_loop(
            provider=provider,
            messages=({"role": "user", "content": "查订单"},),
            tools=(),
            deadline=time.monotonic() + 0.01,
            max_output_tokens=1024,
        )


@pytest.mark.asyncio
async def test_oversized_tool_result_is_not_treated_as_visible_grounding_evidence() -> None:
    from langchain_core.tools import tool

    from app.agents.tools.loop import run_tool_loop

    @tool
    async def large_result() -> dict:
        """返回需要分页的过大内容。"""
        return {"status": "succeeded", "facts": {"policy": "X" * 17000}}

    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn(
                    None, (FunctionCall("large", "large_result", {}),), {"role": "assistant", "content": None}, 1, 1
                ),
                ToolTurn("请缩小范围", (), {"role": "assistant", "content": "请缩小范围"}, 1, 1),
            ]
        )
    )
    result = await run_tool_loop(
        provider=provider, messages=(), tools=(large_result,), deadline=time.monotonic() + 2, max_output_tokens=100
    )
    assert result.events[0].status == "tool_result_too_large"
    assert result.observations[0].status == "tool_result_too_large"
    assert result.observations[0].facts == {}


@pytest.mark.asyncio
async def test_shared_deadline_cancels_waiting_business_tool() -> None:
    from langchain_core.tools import tool

    from app.agents.tools.loop import run_tool_loop

    cancelled = False

    @tool
    async def slow_read() -> dict:
        """模拟等待只读平台请求。"""
        nonlocal cancelled
        try:
            await asyncio.sleep(1)
        finally:
            cancelled = True
        return {"status": "succeeded"}

    provider = SimpleNamespace(
        complete=AsyncMock(
            return_value=ToolTurn(
                None, (FunctionCall("slow", "slow_read", {}),), {"role": "assistant", "content": None}, 1, 1
            )
        )
    )
    with pytest.raises(TimeoutError):
        await run_tool_loop(
            provider=provider, messages=(), tools=(slow_read,), deadline=time.monotonic() + 0.01, max_output_tokens=100
        )
    assert cancelled
