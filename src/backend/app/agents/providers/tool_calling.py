"""DeepSeek Chat Completions 原生 function calling 单轮适配。"""

import json
from dataclasses import dataclass
from typing import Literal, cast

from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from openai import APITimeoutError, AsyncOpenAI, Omit, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from app.agents.core.errors import LLMErrorCode, LLMProviderError


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
