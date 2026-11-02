"""原生 function call 多轮协议与统一截止时间。"""

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Protocol

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from app.agents.core.errors import LLMProviderError
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.runtime.context import ContextBudgetExceeded
from app.agents.tools.catalog import invoke_selected_tool

MAX_TOOL_RESULT_CHARS = 16_000


def serialize_tool_result(result: object) -> str:
    """所有工具与知识预投影共用同一 JSON 编码和字符预算。"""
    return json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))


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


class ToolLoopTimeout(TimeoutError):
    """保留超时前已经完成或开始的工具记录，不携带原始异常或业务正文。"""

    def __init__(self, result: ToolLoopResult) -> None:
        self.result = result
        super().__init__(result.reason_code)


async def run_tool_loop(
    *,
    provider: ToolCallingPort,
    messages: tuple[dict[str, object], ...],
    tools: tuple[BaseTool, ...],
    deadline: float,
    max_output_tokens: int,
    required_tools: frozenset[str] = frozenset(),
) -> ToolLoopResult:
    """不限工具轮次；模型或工具每次都消耗同一绝对时限。"""
    by_name = {item.name: item for item in tools}
    if len(by_name) != len(tools):
        raise ValueError("工具目录包含重复名称")
    history = list(messages)
    events: list[ToolEvent] = []
    observations: list[ToolObservation] = []
    invalid_signatures: set[str] = set()
    last_missing: frozenset[str] | None = None
    input_tokens = 0
    output_tokens = 0
    pending_call: FunctionCall | None = None
    try:
        while True:
            try:
                async with asyncio.timeout(max(0.0, deadline - time.monotonic())):
                    turn = await provider.complete(
                        messages=tuple(history), tools=tools, max_output_tokens=max_output_tokens
                    )
            except LLMProviderError as error:
                # 供应商失败不抹除此前工具记录；只返回稳定错误类别，不带正文或异常详情。
                reason = (
                    "llm_output_unfinished" if error.output_failure_kind == "unfinished" else error.code.value.lower()
                )
                input_tokens += error.input_tokens
                output_tokens += error.output_tokens
                return ToolLoopResult(None, reason, tuple(events), input_tokens, output_tokens, tuple(observations))
            input_tokens += turn.input_tokens
            output_tokens += turn.output_tokens
            history.append(turn.assistant_message)
            if not turn.calls:
                missing = required_tools - {item.name for item in events if item.status in {"succeeded", "previewed"}}
                if missing:
                    # 只反馈真实缺项，由模型继续原生调用；无进展不能靠再次声明完成放行。
                    if missing == last_missing:
                        return ToolLoopResult(
                            None,
                            "required_tools_incomplete",
                            tuple(events),
                            input_tokens,
                            output_tokens,
                            tuple(observations),
                        )
                    last_missing = missing
                    history.append(
                        {
                            "role": "system",
                            "content": json.dumps(
                                {
                                    "required_tools_missing": sorted(missing),
                                    "instruction": (
                                        "Complete the missing workflow steps using native function calls. "
                                        "Only succeeded or previewed results complete a step; "
                                        "do not claim completion or produce a final answer until they complete."
                                    ),
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )
                    continue
                return ToolLoopResult(
                    turn.content, None, tuple(events), input_tokens, output_tokens, tuple(observations)
                )
            for call in turn.calls:
                selected = by_name.get(call.name)
                status = "succeeded"
                result: object
                if selected is None:
                    status = "tool_unavailable"
                    result = {"status": status}
                else:
                    try:
                        pending_call = call
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
                pending_call = None
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
                result_text = serialize_tool_result(result)
                if len(result_text) > MAX_TOOL_RESULT_CHARS:
                    result_text = '{"status":"tool_result_too_large"}'
                    events[-1] = ToolEvent(call_id=call.id, name=call.name, status="tool_result_too_large")
                    # 未送入模型的数据不能进入最终依据复核或会话事实记忆。
                    observations[-1] = ToolObservation(call.id, call.name, "tool_result_too_large", {})
                history.append({"role": "tool", "tool_call_id": call.id, "content": result_text})
    except asyncio.CancelledError:
        if pending_call is not None:
            events.append(ToolEvent(pending_call.id, pending_call.name, "cancelled"))
        # 子任务将诊断交回协调器；请求层的取消仍由协调器向上传播，不能留下后台调用。
        return ToolLoopResult(None, "cancelled", tuple(events), input_tokens, output_tokens, tuple(observations))
    except TimeoutError:
        reason = "agent_deadline_exceeded"
        if pending_call is not None:
            events.append(ToolEvent(pending_call.id, pending_call.name, "timeout"))
            if pending_call.name == "search_knowledge":
                reason = "rag_retrieval_timeout"
        raise ToolLoopTimeout(
            ToolLoopResult(None, reason, tuple(events), input_tokens, output_tokens, tuple(observations))
        ) from None
    except ContextBudgetExceeded:
        return ToolLoopResult(
            None, "context_budget_exceeded", tuple(events), input_tokens, output_tokens, tuple(observations)
        )
    except Exception:
        # 未预期端口失败也必须保留进度；不持久化可能带凭证或正文的异常详情。
        return ToolLoopResult(None, "tool_loop_failed", tuple(events), input_tokens, output_tokens, tuple(observations))
