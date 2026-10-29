"""DeepSeek Chat Completions 原生 function calling 单轮适配。"""

import asyncio
import json
from dataclasses import dataclass
from typing import Literal, cast

import httpx
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from openai import APITimeoutError, AsyncOpenAI, Omit, omit
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam, ChatCompletionToolParam
from pydantic import ValidationError

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.providers.text_streaming import ModelDeltaCallback, ModelStreamDelta


@dataclass(frozen=True, slots=True)
class FunctionCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolTurn:
    content: str | None
    calls: tuple[FunctionCall, ...]
    assistant_message: dict[str, object]
    input_tokens: int
    output_tokens: int


@dataclass(slots=True)
class _StreamingCall:
    id: str = ""
    name: str = ""
    arguments: str = ""
    type: str = ""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError("duplicate tool argument")
        parsed[key] = value
    return parsed


def _parse_arguments(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "工具参数无效", retriable=False) from error
    if not isinstance(parsed, dict):
        raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "工具参数必须是对象", retriable=False)
    return cast(dict[str, object], parsed)


class DeepSeekToolCallingProvider:
    """只负责模型协议；授权、DLP、工具执行和循环截止由运行层处理。"""

    def __init__(
        self,
        *,
        model_name: str,
        client: AsyncOpenAI,
        thinking_enabled: bool = False,
        deepseek_protocol: bool = True,
    ) -> None:
        if not model_name.strip():
            raise LLMProviderError(LLMErrorCode.LLM_CONFIGURATION_ERROR, "模型名称为空", retriable=False)
        self.model_name = model_name.strip()
        self._client = client
        self.thinking_enabled = thinking_enabled
        self._deepseek_protocol = deepseek_protocol

    async def complete(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
    ) -> ToolTurn:
        """回传助手原始 reasoning_content 和 tool_calls，供下一轮完整续传。"""
        if max_output_tokens <= 0:
            raise ValueError("模型输出预算必须为正数")
        schemas = [convert_to_openai_tool(item) for item in tools]
        tool_choice: Literal["auto"] | Omit = "auto" if schemas else omit
        try:
            if self._deepseek_protocol:
                response = await self._client.chat.completions.create(
                    model=self.model_name,
                    messages=cast(list[ChatCompletionMessageParam], list(messages)),
                    tools=cast(list[ChatCompletionToolParam], schemas) if schemas else omit,
                    tool_choice=tool_choice,
                    max_tokens=max_output_tokens,
                    stream=False,
                    extra_body={"thinking": {"type": "enabled" if self.thinking_enabled else "disabled"}},
                )
            else:
                response = await self._client.chat.completions.create(
                    model=self.model_name,
                    messages=cast(list[ChatCompletionMessageParam], list(messages)),
                    tools=cast(list[ChatCompletionToolParam], schemas) if schemas else omit,
                    tool_choice=tool_choice,
                    max_completion_tokens=max_output_tokens,
                    stream=False,
                    store=False,
                )
        except APITimeoutError as error:
            raise LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "模型请求超时", retriable=False) from error
        return self._parse_response(response)

    async def complete_streaming(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
        on_delta: ModelDeltaCallback,
    ) -> ToolTurn:
        if max_output_tokens <= 0:
            raise ValueError("模型输出预算必须为正数")
        schemas = [convert_to_openai_tool(item) for item in tools]
        content = ""
        reasoning = ""
        reasoning_seen = False
        calls: dict[int, _StreamingCall] = {}
        finish_reason: str | None = None
        input_tokens = output_tokens = 0
        try:
            stream = await self._client.chat.completions.create(
                model=self.model_name,
                messages=cast(list[ChatCompletionMessageParam], list(messages)),
                tools=cast(list[ChatCompletionToolParam], schemas) if schemas else omit,
                tool_choice="auto" if schemas else omit,
                max_tokens=max_output_tokens if self._deepseek_protocol else omit,
                max_completion_tokens=omit if self._deepseek_protocol else max_output_tokens,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={"thinking": {"type": "enabled" if self.thinking_enabled else "disabled"}}
                if self._deepseek_protocol
                else None,
                store=omit if self._deepseek_protocol else False,
            )
            async with stream:
                async for chunk in stream:
                    if chunk.usage is not None:
                        input_tokens = chunk.usage.prompt_tokens
                        output_tokens = chunk.usage.completion_tokens
                    if not chunk.choices:
                        continue
                    if len(chunk.choices) != 1 or chunk.choices[0].index != 0 or finish_reason is not None:
                        raise LLMProviderError(
                            LLMErrorCode.LLM_OUTPUT_INVALID, "模型响应数量或顺序异常", retriable=False
                        )
                    choice = chunk.choices[0]
                    delta = choice.delta
                    raw_reasoning = getattr(delta, "reasoning_content", None)
                    if isinstance(raw_reasoning, str):
                        reasoning_seen = True
                        reasoning += raw_reasoning
                    if delta.content:
                        content += delta.content
                        await on_delta(ModelStreamDelta(kind="text", text=delta.content))
                    for item in delta.tool_calls or ():
                        if item.index < 0:
                            raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "工具调用索引无效", retriable=False)
                        call = calls.setdefault(item.index, _StreamingCall())
                        if item.id:
                            call.id += item.id
                        if item.type:
                            call.type = item.type
                        arguments_delta = ""
                        if item.function is not None:
                            if item.function.name:
                                call.name += item.function.name
                            arguments_delta = item.function.arguments or ""
                            call.arguments += arguments_delta
                        if arguments_delta or item.id or (item.function is not None and item.function.name):
                            await on_delta(
                                ModelStreamDelta(
                                    kind="tool_arguments",
                                    tool_index=item.index,
                                    tool_id=call.id or None,
                                    tool_name=call.name or None,
                                    arguments_delta=arguments_delta,
                                )
                            )
                    finish_reason = choice.finish_reason
            wire_calls = [
                {"id": call.id, "type": call.type, "function": {"name": call.name, "arguments": call.arguments}}
                for _, call in sorted(calls.items())
            ]
            # 与非流式路径共用严格校验；草稿回调不构成最终回答或工具执行授权。
            response = ChatCompletion.model_validate(
                {
                    "id": "stream",
                    "object": "chat.completion",
                    "created": 0,
                    "model": self.model_name,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": finish_reason,
                            "message": {
                                "role": "assistant",
                                "content": content or None,
                                "tool_calls": wire_calls or None,
                                **({"reasoning_content": reasoning} if reasoning_seen else {}),
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                }
            )
            return self._parse_response(response)
        except (APITimeoutError, httpx.TimeoutException) as error:
            failure = LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "模型请求超时", retriable=False)
            failure.input_tokens, failure.output_tokens = input_tokens, output_tokens
            raise failure from error
        except ValidationError as error:
            failure = LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "模型流响应结构无效",
                retriable=False,
                output_failure_kind="invalid_structure",
            )
            failure.input_tokens, failure.output_tokens = input_tokens, output_tokens
            raise failure from error
        except (LLMProviderError, asyncio.CancelledError) as error:
            error.__dict__.update(input_tokens=input_tokens, output_tokens=output_tokens)
            raise

    def _parse_response(self, response: ChatCompletion) -> ToolTurn:
        try:
            if len(response.choices) != 1:
                raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型响应数量异常", retriable=False)
            choice = response.choices[0]
            message = choice.message
            raw_calls = message.tool_calls or []
            if choice.finish_reason not in {"stop", "tool_calls"} or bool(raw_calls) != (
                choice.finish_reason == "tool_calls"
            ):
                raise LLMProviderError(
                    LLMErrorCode.LLM_OUTPUT_INVALID,
                    "模型工具调用未完成",
                    retriable=False,
                    output_failure_kind="unfinished" if choice.finish_reason == "length" else "invalid_structure",
                )
            reasoning_content = getattr(message, "reasoning_content", None)
            if self.thinking_enabled and not isinstance(reasoning_content, str):
                raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型推理上下文缺失", retriable=False)
            calls: list[FunctionCall] = []
            wire_calls: list[dict[str, object]] = []
            seen_ids: set[str] = set()
            for item in raw_calls:
                if item.type != "function" or not item.id or item.id in seen_ids or not item.function.name:
                    raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "工具调用标识无效", retriable=False)
                seen_ids.add(item.id)
                calls.append(
                    FunctionCall(
                        id=item.id,
                        name=item.function.name,
                        arguments=_parse_arguments(item.function.arguments),
                    )
                )
                wire_calls.append(
                    {
                        "id": item.id,
                        "type": "function",
                        "function": {"name": item.function.name, "arguments": item.function.arguments},
                    }
                )
            content = message.content if isinstance(message.content, str) and message.content.strip() else None
            if not calls and content is None:
                raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型未返回回答", retriable=False)
            assistant_message: dict[str, object] = {"role": "assistant", "content": content}
            if self.thinking_enabled:
                assistant_message["reasoning_content"] = reasoning_content
            if wire_calls:
                assistant_message["tool_calls"] = wire_calls
            usage = response.usage
            return ToolTurn(
                content=content,
                calls=tuple(calls),
                assistant_message=assistant_message,
                input_tokens=usage.prompt_tokens if usage is not None else 0,
                output_tokens=usage.completion_tokens if usage is not None else 0,
            )
        except LLMProviderError as error:
            if response.usage is not None:
                error.input_tokens = response.usage.prompt_tokens
                error.output_tokens = response.usage.completion_tokens
            raise


class OpenAIToolCallingProvider(DeepSeekToolCallingProvider):
    """OpenAI Chat Completions 原生 tool_calls；请求不存储到 Provider 侧。"""

    def __init__(self, *, model_name: str, client: AsyncOpenAI) -> None:
        super().__init__(model_name=model_name, client=client, deepseek_protocol=False)
