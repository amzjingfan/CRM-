"""原生 SDK 流只透出类型化草稿，最终协议、预算和连接仍完整受控。"""

import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.providers.anthropic_tool_calling import AnthropicToolCallingProvider
from app.agents.providers.budget import BudgetedToolProvider
from app.agents.providers.tool_calling import DeepSeekToolCallingProvider, OpenAIToolCallingProvider, ToolTurn
from app.agents.runtime.context import ContextBudgetExceeded, ModelLimits


class SSEBody(httpx.AsyncByteStream):
    def __init__(self, events: list[dict | Exception], *, pause_after: int | None = None) -> None:
        self.events = events
        self.pause_after = pause_after
        self.release = asyncio.Event()
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for index, event in enumerate(self.events):
            if self.pause_after == index:
                await self.release.wait()
            if isinstance(event, Exception):
                raise event
            event_type = event.get("type")
            prefix = f"event: {event_type}\n" if event_type else ""
            yield f"{prefix}data: {json.dumps(event)}\n\n".encode()

    async def aclose(self) -> None:
        self.closed = True


def chat_chunk(*, delta: dict | None = None, finish: str | None = None, usage: bool = False) -> dict:
    return {
        "id": "synthetic-chat",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "synthetic-model",
        "choices": [] if usage else [{"index": 0, "delta": delta or {}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 17, "completion_tokens": 9, "total_tokens": 26} if usage else None,
    }


def tool_chunk(index: int, arguments: str, *, initial: bool = False) -> dict:
    result: dict = {"index": index, "function": {"arguments": arguments}}
    if initial:
        result.update(id=f"call-{index}", type="function")
        result["function"]["name"] = "submit_reply_parts" if index == 0 else "query_order"
    return result


def anthropic_events(*, stop: str = "end_turn", tool: bool = False) -> list[dict]:
    block = (
        {"type": "tool_use", "id": "use-1", "name": "submit_reply_parts", "input": {}}
        if tool
        else {"type": "text", "text": ""}
    )
    delta = (
        {"type": "input_json_delta", "partial_json": '{"parts":["已发货"]}'}
        if tool
        else {"type": "text_delta", "text": "已发货"}
    )
    return [
        {
            "type": "message_start",
            "message": {
                "id": "synthetic-message",
                "type": "message",
                "role": "assistant",
                "model": "synthetic-model",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 17, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": block},
        {"type": "content_block_delta", "index": 0, "delta": delta},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop, "stop_sequence": None},
            "usage": {"output_tokens": 9},
        },
        {"type": "message_stop"},
    ]


def sdk_provider(family: str, body: SSEBody):
    requests: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    if family == "anthropic":
        client = AsyncAnthropic(api_key="synthetic", http_client=http_client, max_retries=0)
        provider = AnthropicToolCallingProvider(model_name="synthetic-model", client=client)
    else:
        client = AsyncOpenAI(api_key="synthetic", http_client=http_client, max_retries=0)
        provider_type = DeepSeekToolCallingProvider if family == "deepseek" else OpenAIToolCallingProvider
        provider = provider_type(model_name="synthetic-model", client=client)
    return provider, client, requests


@pytest.mark.parametrize("family", ["deepseek", "openai", "anthropic"])
async def test_first_text_delta_precedes_final_turn_and_sdk_resource_closes(family) -> None:
    events = (
        anthropic_events()
        if family == "anthropic"
        else [
            chat_chunk(delta={"content": "已发货"}),
            chat_chunk(finish="stop"),
            chat_chunk(usage=True),
        ]
    )
    body = SSEBody(events, pause_after=3 if family == "anthropic" else 1)
    provider, client, requests = sdk_provider(family, body)
    deltas = []
    first = asyncio.Event()

    async def receive(delta) -> None:
        deltas.append(delta)
        first.set()

    try:
        task = asyncio.create_task(
            provider.complete_streaming(
                messages=({"role": "user", "content": "物流在哪"},), tools=(), max_output_tokens=128, on_delta=receive
            )
        )
        await asyncio.wait_for(first.wait(), 2)
        assert not task.done()
        assert [(item.kind, item.text) for item in deltas] == [("text", "已发货")]
        body.release.set()
        turn = await task
        assert turn.content == "已发货"
        assert turn.calls == ()
        assert (turn.input_tokens, turn.output_tokens) == (17, 9)
        assert body.closed
        assert requests[0]["stream"] is True
        assert requests[0]["max_tokens" if family != "openai" else "max_completion_tokens"] == 128
        if family == "openai":
            assert requests[0]["store"] is False
            assert "thinking" not in requests[0]
        if family != "anthropic":
            assert requests[0]["stream_options"] == {"include_usage": True}
    finally:
        body.release.set()
        await client.close()


async def test_chat_tools_merge_interleaved_chunks_and_never_emit_reasoning_as_text() -> None:
    body = SSEBody(
        [
            chat_chunk(delta={"reasoning_content": "private reasoning"}),
            chat_chunk(delta={"tool_calls": [tool_chunk(0, '{"parts":["', initial=True)]}),
            chat_chunk(delta={"tool_calls": [tool_chunk(1, "{", initial=True), tool_chunk(0, "已发货")]}),
            chat_chunk(delta={"tool_calls": [tool_chunk(0, '"]}'), tool_chunk(1, "}")]}),
            chat_chunk(finish="tool_calls"),
            chat_chunk(usage=True),
        ]
    )
    provider, client, _ = sdk_provider("deepseek", body)
    provider.thinking_enabled = True
    deltas = []

    async def receive(delta) -> None:
        deltas.append(delta)

    try:
        turn = await provider.complete_streaming(messages=(), tools=(), max_output_tokens=128, on_delta=receive)
        assert [(call.id, call.name, call.arguments) for call in turn.calls] == [
            ("call-0", "submit_reply_parts", {"parts": ["已发货"]}),
            ("call-1", "query_order", {}),
        ]
        assert turn.assistant_message["reasoning_content"] == "private reasoning"
        assert turn.assistant_message["tool_calls"][0]["function"]["arguments"] == '{"parts":["已发货"]}'
        assert all(item.kind == "tool_arguments" and item.text == "" for item in deltas)
        assert [(item.tool_index, item.tool_id, item.tool_name, item.arguments_delta) for item in deltas] == [
            (0, "call-0", "submit_reply_parts", '{"parts":["'),
            (1, "call-1", "query_order", "{"),
            (0, "call-0", "submit_reply_parts", "已发货"),
            (0, "call-0", "submit_reply_parts", '"]}'),
            (1, "call-1", "query_order", "}"),
        ]
    finally:
        await client.close()


async def test_anthropic_tool_json_is_typed_and_roundtrips_final_call() -> None:
    events = anthropic_events(stop="tool_use", tool=True)
    events[2]["delta"]["partial_json"] = '{"parts":['
    events.insert(
        3,
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '"已发货"]}'},
        },
    )
    provider, client, _ = sdk_provider("anthropic", SSEBody(events))
    deltas = []

    async def receive(delta) -> None:
        deltas.append(delta)

    try:
        turn = await provider.complete_streaming(
            messages=({"role": "user", "content": "物流在哪"},), tools=(), max_output_tokens=128, on_delta=receive
        )
        assert turn.content is None
        assert turn.calls[0].arguments == {"parts": ["已发货"]}
        assert [(item.kind, item.text, item.tool_id, item.tool_name, item.arguments_delta) for item in deltas] == [
            ("tool_arguments", "", "use-1", "submit_reply_parts", '{"parts":['),
            ("tool_arguments", "", "use-1", "submit_reply_parts", '"已发货"]}'),
        ]
    finally:
        await client.close()


@pytest.mark.parametrize("family", ["deepseek", "openai", "anthropic"])
@pytest.mark.parametrize("finish", ["length", "invalid", None])
async def test_unfinished_or_invalid_finish_fails_closed_with_known_usage(family, finish) -> None:
    events = (
        anthropic_events(stop="max_tokens" if finish == "length" else finish)
        if family == "anthropic"
        else [chat_chunk(delta={"content": "private answer"}), chat_chunk(finish=finish), chat_chunk(usage=True)]
    )
    body = SSEBody(events)
    provider, client, _ = sdk_provider(family, body)
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_streaming(
                messages=({"role": "user", "content": "test"},), tools=(), max_output_tokens=128, on_delta=AsyncMock()
            )
        assert caught.value.code == LLMErrorCode.LLM_OUTPUT_INVALID
        assert caught.value.output_failure_kind == ("unfinished" if finish == "length" else "invalid_structure")
        assert (caught.value.input_tokens, caught.value.output_tokens) == (17, 9)
        assert "private answer" not in str(caught.value)
        assert body.closed
    finally:
        await client.close()


@pytest.mark.parametrize("family", ["deepseek", "openai", "anthropic"])
async def test_stream_read_timeout_maps_stable_error_and_retains_known_usage(family) -> None:
    timeout = httpx.ReadTimeout("synthetic timeout")
    events = anthropic_events()[:1] if family == "anthropic" else [chat_chunk(usage=True)]
    body = SSEBody([*events, timeout])
    provider, client, _ = sdk_provider(family, body)
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_streaming(
                messages=({"role": "user", "content": "test"},), tools=(), max_output_tokens=128, on_delta=AsyncMock()
            )
        assert caught.value.code == LLMErrorCode.LLM_TIMEOUT
        assert (caught.value.input_tokens, caught.value.output_tokens) == (
            (17, 0) if family == "anthropic" else (17, 9)
        )
        assert body.closed
    finally:
        await client.close()


@pytest.mark.parametrize("family", ["deepseek", "openai", "anthropic"])
async def test_cancellation_stops_sdk_stream_and_preserves_known_usage(family) -> None:
    events = (
        anthropic_events()[:3]
        if family == "anthropic"
        else [chat_chunk(usage=True), chat_chunk(delta={"content": "draft"})]
    )
    body = SSEBody([*events, chat_chunk()], pause_after=len(events))
    provider, client, _ = sdk_provider(family, body)
    first = asyncio.Event()

    async def receive(delta) -> None:
        first.set()

    try:
        task = asyncio.create_task(
            provider.complete_streaming(
                messages=({"role": "user", "content": "test"},), tools=(), max_output_tokens=128, on_delta=receive
            )
        )
        await asyncio.wait_for(first.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert body.closed
        assert (caught.value.input_tokens, caught.value.output_tokens) == (
            (17, 0) if family == "anthropic" else (17, 9)
        )
    finally:
        body.release.set()
        await client.close()


async def test_budgeted_streaming_checks_full_context_and_legacy_fallback_emits_no_fake_delta() -> None:
    turn = ToolTurn("review me", (), {}, 1, 2)
    legacy = SimpleNamespace(complete=AsyncMock(return_value=turn))
    callback = AsyncMock()
    provider = BudgetedToolProvider(legacy, ModelLimits(160, 32, 32))
    assert (
        await provider.complete_streaming(
            messages=({"role": "user", "content": "test"},), tools=(), max_output_tokens=32, on_delta=callback
        )
        is turn
    )
    callback.assert_not_awaited()
    with pytest.raises(ContextBudgetExceeded):
        await provider.complete_streaming(
            messages=({"role": "tool", "content": "物流" * 200},), tools=(), max_output_tokens=32, on_delta=callback
        )
    assert legacy.complete.await_count == 1


async def test_budgeted_streaming_forwards_native_callback_and_refuses_nonpositive_budget() -> None:
    turn = ToolTurn("review me", (), {}, 1, 2)
    native = SimpleNamespace(complete=AsyncMock(), complete_streaming=AsyncMock(return_value=turn))
    callback = AsyncMock()
    provider = BudgetedToolProvider(native, ModelLimits(160, 32, 32))
    assert await provider.complete_streaming(messages=(), tools=(), max_output_tokens=32, on_delta=callback) is turn
    assert native.complete_streaming.await_args.kwargs["on_delta"] is callback
    with pytest.raises(ContextBudgetExceeded):
        await provider.complete_streaming(messages=(), tools=(), max_output_tokens=0, on_delta=callback)
    assert native.complete_streaming.await_count == 1
    native.complete.assert_not_awaited()


@pytest.mark.parametrize("family", ["deepseek", "anthropic"])
@pytest.mark.parametrize("arguments", ['{"a":1,"a":2}', "[1,2]", '{"a":'])
async def test_streamed_tool_arguments_reject_duplicate_nonobject_and_incomplete_json(family, arguments) -> None:
    if family == "anthropic":
        events = anthropic_events(stop="tool_use", tool=True)
        events[2]["delta"]["partial_json"] = arguments
    else:
        events = [
            chat_chunk(delta={"tool_calls": [tool_chunk(0, arguments, initial=True)]}),
            chat_chunk(finish="tool_calls"),
            chat_chunk(usage=True),
        ]
    body = SSEBody(events)
    provider, client, _ = sdk_provider(family, body)
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_streaming(
                messages=({"role": "user", "content": "test"},),
                tools=(),
                max_output_tokens=128,
                on_delta=AsyncMock(),
            )
        assert caught.value.code == LLMErrorCode.LLM_OUTPUT_INVALID
        assert (caught.value.input_tokens, caught.value.output_tokens) == (17, 9)
        assert body.closed
    finally:
        await client.close()


async def test_anthropic_missing_message_stop_does_not_accept_disconnected_draft() -> None:
    body = SSEBody(anthropic_events()[:-1])
    provider, client, _ = sdk_provider("anthropic", body)
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_streaming(
                messages=({"role": "user", "content": "test"},),
                tools=(),
                max_output_tokens=128,
                on_delta=AsyncMock(),
            )
        assert caught.value.output_failure_kind == "unfinished"
        assert (caught.value.input_tokens, caught.value.output_tokens) == (17, 9)
        assert body.closed
    finally:
        await client.close()


@pytest.mark.parametrize("family", ["deepseek", "openai", "anthropic"])
async def test_callback_failure_closes_stream_and_propagates_to_caller(family) -> None:
    events = anthropic_events() if family == "anthropic" else [chat_chunk(delta={"content": "draft"})]
    body = SSEBody(events)
    provider, client, _ = sdk_provider(family, body)
    try:
        with pytest.raises(ValueError, match="consumer failed"):
            await provider.complete_streaming(
                messages=({"role": "user", "content": "test"},),
                tools=(),
                max_output_tokens=128,
                on_delta=AsyncMock(side_effect=ValueError("consumer failed")),
            )
        assert body.closed
    finally:
        await client.close()


async def test_chat_name_fragments_update_metadata_without_losing_early_arguments() -> None:
    body = SSEBody(
        [
            chat_chunk(
                delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-",
                            "type": "function",
                            "function": {"name": "submit_", "arguments": '{"texts":["ok"]}'},
                        }
                    ]
                }
            ),
            chat_chunk(
                delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "0",
                            "function": {"name": "reply_parts"},
                        }
                    ]
                }
            ),
            chat_chunk(finish="tool_calls"),
        ]
    )
    provider, client, _ = sdk_provider("openai", body)
    deltas = []

    async def receive(delta) -> None:
        deltas.append(delta)

    try:
        turn = await provider.complete_streaming(messages=(), tools=(), max_output_tokens=128, on_delta=receive)
        assert turn.calls[0].id == "call-0"
        assert turn.calls[0].name == "submit_reply_parts"
        assert turn.calls[0].arguments == {"texts": ["ok"]}
        assert [(item.tool_id, item.tool_name, item.arguments_delta) for item in deltas] == [
            ("call-", "submit_", '{"texts":["ok"]}'),
            ("call-0", "submit_reply_parts", ""),
        ]
    finally:
        await client.close()


@pytest.mark.parametrize("family", ["deepseek", "openai", "anthropic"])
async def test_sdk_request_timeout_before_stream_is_stable_without_invented_usage(family) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    if family == "anthropic":
        client = AsyncAnthropic(api_key="synthetic", http_client=http_client, max_retries=0)
        provider = AnthropicToolCallingProvider(model_name="synthetic-model", client=client)
    else:
        client = AsyncOpenAI(api_key="synthetic", http_client=http_client, max_retries=0)
        provider_type = DeepSeekToolCallingProvider if family == "deepseek" else OpenAIToolCallingProvider
        provider = provider_type(model_name="synthetic-model", client=client)
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_streaming(
                messages=({"role": "user", "content": "test"},),
                tools=(),
                max_output_tokens=128,
                on_delta=AsyncMock(),
            )
        assert caught.value.code == LLMErrorCode.LLM_TIMEOUT
        assert (caught.value.input_tokens, caught.value.output_tokens) == (0, 0)
    finally:
        await client.close()


@pytest.mark.parametrize("missing", ["id", "type", "name"])
async def test_chat_tool_call_missing_required_metadata_fails_closed(missing) -> None:
    call = tool_chunk(0, "{}", initial=True)
    if missing == "name":
        del call["function"]["name"]
    else:
        del call[missing]
    body = SSEBody(
        [
            chat_chunk(delta={"tool_calls": [call]}),
            chat_chunk(finish="tool_calls"),
            chat_chunk(usage=True),
        ]
    )
    provider, client, _ = sdk_provider("openai", body)
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_streaming(messages=(), tools=(), max_output_tokens=128, on_delta=AsyncMock())
        assert caught.value.code == LLMErrorCode.LLM_OUTPUT_INVALID
        assert (caught.value.input_tokens, caught.value.output_tokens) == (17, 9)
        assert body.closed
    finally:
        await client.close()
