"""Anthropic Messages 原生 tool_use/tool_result 适配。"""

import asyncio
import json
from typing import cast

import httpx
from anthropic import APITimeoutError, AsyncAnthropic, omit
from anthropic.types import Message, MessageParam, ToolParam
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.providers.text_streaming import ModelDeltaCallback, ModelStreamDelta
from app.agents.providers.tool_calling import FunctionCall, ToolTurn, _parse_arguments


def _history(messages: tuple[dict[str, object], ...]) -> tuple[str, list[MessageParam]]:
    system_parts: list[str] = []
    converted: list[MessageParam] = []
    for item in messages:
        role = item.get("role")
        content = item.get("content")
        if role == "system" and isinstance(content, str):
            system_parts.append(content)
        elif role == "user" and isinstance(content, str):
            converted.append(cast(MessageParam, {"role": "user", "content": content}))
        elif role == "assistant":
            blocks: list[dict[str, object]] = []
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            calls = item.get("tool_calls")
            if isinstance(calls, list):
                for raw in calls:
                    if not isinstance(raw, dict):
                        raise ValueError("Anthropic assistant tool call invalid")
                    function = raw.get("function")
                    if not isinstance(function, dict) or not isinstance(function.get("arguments"), str):
                        raise ValueError("Anthropic assistant tool arguments invalid")
                    arguments = json.loads(function["arguments"])
                    if not isinstance(arguments, dict):
                        raise ValueError("Anthropic assistant tool arguments invalid")
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": raw["id"],
                            "name": function["name"],
                            "input": arguments,
                        }
                    )
            if not blocks:
                raise ValueError("Anthropic assistant message empty")
            converted.append(cast(MessageParam, {"role": "assistant", "content": blocks}))
        elif role == "tool" and isinstance(content, str):
            call_id = item.get("tool_call_id")
            if not isinstance(call_id, str):
                raise ValueError("Anthropic tool result ID invalid")
            block = {"type": "tool_result", "tool_use_id": call_id, "content": content}
            if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                converted[-1]["content"].append(cast(object, block))
            else:
                converted.append(cast(MessageParam, {"role": "user", "content": [block]}))
        else:
            raise ValueError("Anthropic message role or content invalid")
    if not converted:
        raise ValueError("Anthropic messages empty")
    return "\n\n".join(system_parts), converted


def _tool_schema(tool: BaseTool) -> ToolParam:
    schema = convert_to_openai_tool(tool)
    function = schema.get("function")
    if not isinstance(function, dict):
        raise ValueError("Anthropic tool schema invalid")
    return cast(
        ToolParam,
        {
            "name": function["name"],
            "description": function.get("description", ""),
            "input_schema": function["parameters"],
        },
    )


class AnthropicToolCallingProvider:
    def __init__(self, *, model_name: str, client: AsyncAnthropic) -> None:
        if not model_name.strip():
            raise ValueError("Anthropic model name empty")
        self.model_name = model_name.strip()
        self._client = client

    async def complete(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
    ) -> ToolTurn:
        if max_output_tokens <= 0:
            raise ValueError("模型输出预算必须为正数")
        system, history = _history(messages)
        schemas = [_tool_schema(item) for item in tools]
        if schemas:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=max_output_tokens,
                system=system,
                messages=history,
                tools=schemas,
                tool_choice={"type": "auto"},
            )
        else:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=max_output_tokens,
                system=system,
                messages=history,
            )
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
        system, history = _history(messages)
        schemas = [_tool_schema(item) for item in tools]
        tool_metadata: dict[int, tuple[str, str]] = {}
        arguments: dict[int, str] = {}
        input_tokens = output_tokens = 0
        stopped = False
        try:
            async with self._client.messages.stream(
                model=self.model_name,
                max_tokens=max_output_tokens,
                system=system,
                messages=history,
                tools=schemas if schemas else omit,
                tool_choice={"type": "auto"} if schemas else omit,
            ) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        input_tokens = event.message.usage.input_tokens
                        output_tokens = event.message.usage.output_tokens
                    elif event.type == "message_delta":
                        output_tokens = event.usage.output_tokens
                        if event.usage.input_tokens is not None:
                            input_tokens = event.usage.input_tokens
                    elif event.type == "message_stop":
                        stopped = True
                    elif event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            tool_metadata[event.index] = (block.id, block.name)
                        elif block.type == "text" and block.text:
                            await on_delta(ModelStreamDelta(kind="text", text=block.text))
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta" and delta.text:
                            await on_delta(ModelStreamDelta(kind="text", text=delta.text))
                        elif delta.type == "input_json_delta":
                            metadata = tool_metadata.get(event.index)
                            if metadata is None:
                                raise LLMProviderError(
                                    LLMErrorCode.LLM_OUTPUT_INVALID, "模型工具参数缺少调用标识", retriable=False
                                )
                            arguments[event.index] = arguments.get(event.index, "") + delta.partial_json
                            if delta.partial_json:
                                await on_delta(
                                    ModelStreamDelta(
                                        kind="tool_arguments",
                                        tool_index=event.index,
                                        tool_id=metadata[0],
                                        tool_name=metadata[1],
                                        arguments_delta=delta.partial_json,
                                    )
                                )
                if not stopped:
                    raise LLMProviderError(
                        LLMErrorCode.LLM_OUTPUT_INVALID,
                        "模型流未完整结束",
                        retriable=False,
                        output_failure_kind="unfinished",
                    )
                response = await stream.get_final_message()
                for index, raw_arguments in arguments.items():
                    block = response.content[index]
                    if block.type != "tool_use":
                        raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型工具参数类型无效", retriable=False)
                    # SDK 的增量 JSON 合并不能替代重复键与对象根的严格校验。
                    block.input = _parse_arguments(raw_arguments)
                return self._parse_response(response)
        except (APITimeoutError, httpx.TimeoutException) as error:
            failure = LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "模型请求超时", retriable=False)
            failure.input_tokens, failure.output_tokens = input_tokens, output_tokens
            raise failure from error
        except (LLMProviderError, asyncio.CancelledError) as error:
            error.__dict__.update(input_tokens=input_tokens, output_tokens=output_tokens)
            raise

    def _parse_response(self, response: Message) -> ToolTurn:
        try:
            return self._validated_turn(response)
        except LLMProviderError as error:
            error.input_tokens = response.usage.input_tokens
            error.output_tokens = response.usage.output_tokens
            raise

    def _validated_turn(self, response: Message) -> ToolTurn:
        if response.stop_reason not in {"end_turn", "tool_use"}:
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "模型响应未完整结束",
                retriable=False,
                output_failure_kind="unfinished" if response.stop_reason == "max_tokens" else "invalid_structure",
            )
        text_blocks: list[str] = []
        calls: list[FunctionCall] = []
        wire_calls: list[dict[str, object]] = []
        seen: set[str] = set()
        for block in response.content:
            if block.type == "text":
                text_blocks.append(block.text)
            elif block.type == "tool_use":
                if not block.id or block.id in seen or not block.name or not isinstance(block.input, dict):
                    raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型工具调用无效", retriable=False)
                seen.add(block.id)
                arguments = block.input
                calls.append(FunctionCall(block.id, block.name, arguments))
                wire_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {"name": block.name, "arguments": json.dumps(arguments, ensure_ascii=False)},
                    }
                )
            else:
                raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型响应类型无效", retriable=False)
        if bool(calls) != (response.stop_reason == "tool_use"):
            raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型工具调用未完成", retriable=False)
        content = "\n".join(item for item in text_blocks if item.strip()) or None
        if not calls and content is None:
            raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型未返回回答", retriable=False)
        assistant_message: dict[str, object] = {"role": "assistant", "content": content}
        if wire_calls:
            assistant_message["tool_calls"] = wire_calls
        return ToolTurn(
            content,
            tuple(calls),
            assistant_message,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
