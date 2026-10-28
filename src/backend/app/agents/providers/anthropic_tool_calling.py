"""Anthropic Messages 原生 tool_use/tool_result 适配。"""

import json
from typing import cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.providers.tool_calling import FunctionCall, ToolTurn


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
        if response.stop_reason not in {"end_turn", "tool_use"}:
            raise LLMProviderError(LLMErrorCode.LLM_OUTPUT_INVALID, "模型响应未完整结束", retriable=False)
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
