"""原生 function call 多轮协议与统一截止时间。"""

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Protocol

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from app.agents.providers.tool_calling import ToolTurn
from app.agents.tools.catalog import invoke_selected_tool


class ToolCallingPort(Protocol):
    async def complete(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
    ) -> ToolTurn: ...


@dataclass(frozen=True, slots=True)
class ToolEvent:
    call_id: str
    name: str
    status: str


@dataclass(frozen=True, slots=True)
class ToolObservation:
    """仅保留已投影的事实，不存可信订单或客户 ID。"""

    call_id: str
    name: str
    status: str
    facts: dict[str, object]
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class ToolLoopResult:
    answer: str | None
    reason_code: str | None
    events: tuple[ToolEvent, ...]
    input_tokens: int
    output_tokens: int
    observations: tuple[ToolObservation, ...] = ()


async def run_tool_loop(
    *,
    provider: ToolCallingPort,
    messages: tuple[dict[str, object], ...],
    tools: tuple[BaseTool, ...],
    deadline: float,
    max_output_tokens: int,
) -> ToolLoopResult:
    """不限工具轮次；模型或工具每次都消耗同一绝对时限。"""
    by_name = {item.name: item for item in tools}
    if len(by_name) != len(tools):
        raise ValueError("工具目录包含重复名称")
    history = list(messages)
    events: list[ToolEvent] = []
    observations: list[ToolObservation] = []
    invalid_signatures: set[str] = set()
    input_tokens = 0
    output_tokens = 0
    while True:
        async with asyncio.timeout(max(0.0, deadline - time.monotonic())):
            turn = await provider.complete(messages=tuple(history), tools=tools, max_output_tokens=max_output_tokens)
        input_tokens += turn.input_tokens
        output_tokens += turn.output_tokens
        history.append(turn.assistant_message)
        if not turn.calls:
            return ToolLoopResult(turn.content, None, tuple(events), input_tokens, output_tokens, tuple(observations))
        for call in turn.calls:
            selected = by_name.get(call.name)
            status = "succeeded"
            result: object
            if selected is None:
                status = "tool_unavailable"
                result = {"status": status}
            else:
                try:
                    async with asyncio.timeout(max(0.0, deadline - time.monotonic())):
                        result = await invoke_selected_tool(selected, call.arguments)
                    if isinstance(result, dict):
                        status = str(result.get("status", "succeeded"))
                except (ValidationError, ValueError):
                    status = "invalid_arguments"
                    result = {"status": status}
                except TimeoutError:
                    raise
                except Exception:
                    status = "tool_failed"
                    result = {"status": status}
            events.append(ToolEvent(call_id=call.id, name=call.name, status=status))
            raw_facts = result.get("facts") if isinstance(result, dict) else None
            facts = dict(raw_facts) if isinstance(raw_facts, dict) else {}
            raw_scope = result.get("fact_scope") if isinstance(result, dict) else None
            scope = raw_scope if isinstance(raw_scope, str) and re.fullmatch(r"[0-9a-f]{16}", raw_scope) else None
            observations.append(ToolObservation(call.id, call.name, status, facts, scope))
            if status in {"tool_unavailable", "invalid_arguments"}:
                signature = json.dumps([call.name, call.arguments], sort_keys=True, ensure_ascii=False)
                if signature in invalid_signatures:
                    return ToolLoopResult(
                        None,
                        "repeated_invalid_tool_call",
                        tuple(events),
                        input_tokens,
                        output_tokens,
                        tuple(observations),
                    )
                invalid_signatures.add(signature)
            result_text = json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))
            if len(result_text) > 16_000:
                result_text = '{"status":"tool_result_too_large"}'
                events[-1] = ToolEvent(call_id=call.id, name=call.name, status="tool_result_too_large")
                # 未送入模型的数据不能进入最终依据复核或会话事实记忆。
                observations[-1] = ToolObservation(call.id, call.name, "tool_result_too_large", {})
            history.append({"role": "tool", "tool_call_id": call.id, "content": result_text})
