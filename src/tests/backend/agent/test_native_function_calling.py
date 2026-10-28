"""DeepSeek 原生 function calling 消息协议。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.core.errors import LLMErrorCode, LLMProviderError


@pytest.mark.asyncio
async def test_native_tool_call_schema_arguments_and_reasoning_roundtrip() -> None:
    from app.agents.providers.tool_calling import DeepSeekToolCallingProvider
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools

    executor = SimpleNamespace(execute=AsyncMock())
    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id="trusted",
        customer_id=None,
        permissions=frozenset({"orders.view"}),
        trace_id="trace",
    )
    tool = build_agent_tools(("query_logistics",), context=context, executor=executor)[0]
    sdk_call = SimpleNamespace(
        id="call_1",
        type="function",
        function=SimpleNamespace(name="query_logistics", arguments="{}"),
    )
    message = SimpleNamespace(content=None, reasoning_content="先查物流", tool_calls=[sdk_call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="tool_calls", message=message)],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    provider = DeepSeekToolCallingProvider(model_name="deepseek-v4-flash", client=client, thinking_enabled=True)
    result = await provider.complete(
        messages=({"role": "system", "content": "安全策略"}, {"role": "user", "content": "物流在哪"}),
        tools=(tool,),
        max_output_tokens=1024,
    )
    assert result.calls[0].name == "query_logistics"
    assert result.calls[0].arguments == {}
    assert result.assistant_message["reasoning_content"] == "先查物流"
    assert result.assistant_message["tool_calls"][0]["id"] == "call_1"
    kwargs = create.await_args.kwargs
    assert kwargs["tools"][0]["function"]["name"] == "query_logistics"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


@pytest.mark.asyncio
async def test_duplicate_or_nonobject_tool_arguments_fail_closed() -> None:
    from app.agents.providers.tool_calling import DeepSeekToolCallingProvider

    for arguments in ('{"a":1,"a":2}', "[1,2]"):
        sdk_call = SimpleNamespace(
            id="call_1", type="function", function=SimpleNamespace(name="query_order", arguments=arguments)
        )
        message = SimpleNamespace(content=None, reasoning_content=None, tool_calls=[sdk_call])
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason="tool_calls", message=message)], usage=None)
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        provider = DeepSeekToolCallingProvider(model_name="deepseek-v4-flash", client=client)
        with pytest.raises(LLMProviderError) as error:
            await provider.complete(
                messages=({"role": "user", "content": "查订单"},),
                tools=(),
                max_output_tokens=1024,
            )
        assert error.value.code == LLMErrorCode.LLM_OUTPUT_INVALID


@pytest.mark.asyncio
async def test_openai_native_tool_call_omits_deepseek_thinking_extension() -> None:
    from app.agents.providers.tool_calling import OpenAIToolCallingProvider

    message = SimpleNamespace(content="可供人工复核的建议", tool_calls=[])
    response = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=message)],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    provider = OpenAIToolCallingProvider(model_name="gpt-4.1-mini", client=client)
    result = await provider.complete(
        messages=({"role": "user", "content": "你好"},),
        tools=(),
        max_output_tokens=500,
    )
    assert result.content == "可供人工复核的建议"
    assert "extra_body" not in create.await_args.kwargs
    assert create.await_args.kwargs["store"] is False


@pytest.mark.asyncio
async def test_anthropic_native_tool_protocol_roundtrip() -> None:
    from app.agents.providers.anthropic_tool_calling import AnthropicToolCallingProvider
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools

    context = AgentToolContext(uuid.uuid4(), uuid.uuid4(), "trusted", None, frozenset({"orders.view"}), "trace")
    tool = build_agent_tools(("query_order",), context=context, executor=SimpleNamespace(execute=AsyncMock()))[0]
    response = SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", id="use_1", name="query_order", input={})],
        usage=SimpleNamespace(input_tokens=12, output_tokens=4),
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    provider = AnthropicToolCallingProvider(model_name="claude-sonnet", client=client)
    result = await provider.complete(
        messages=({"role": "system", "content": "安全"}, {"role": "user", "content": "查订单"}),
        tools=(tool,),
        max_output_tokens=500,
    )
    assert result.calls[0].name == "query_order"
    assert create.await_args.kwargs["tools"][0]["name"] == "query_order"
    continuation = (*result.assistant_message.items(),)
    assert continuation
    await provider.complete(
        messages=(
            {"role": "system", "content": "安全"},
            {"role": "user", "content": "查订单"},
            result.assistant_message,
            {"role": "tool", "tool_call_id": "use_1", "content": '{"status":"succeeded"}'},
        ),
        tools=(tool,),
        max_output_tokens=500,
    )
    sent = create.await_args.kwargs["messages"]
    assert sent[-2]["content"][0]["type"] == "tool_use"
    assert sent[-1]["content"][0]["tool_use_id"] == "use_1"
