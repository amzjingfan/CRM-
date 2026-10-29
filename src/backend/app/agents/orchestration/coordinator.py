"""同一截止时间内运行任意数量的已选 Agent，并确定性收敛取消。"""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

from app.agents.core.schemas import AgentCitation
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.runtime.context import ContextBudgetExceeded
from app.agents.tools.loop import ToolEvent, ToolObservation
from app.knowledge_base.schemas import KnowledgeRetrievalHit


@dataclass(frozen=True, slots=True)
class SpecialistResult:
    agent_id: uuid.UUID
    answer: str | None
    verified_facts: Mapping[str, str] = field(default_factory=dict)
    citations: tuple[str, ...] = ()
    successful_tools: tuple[str, ...] = ()
    reason_code: str | None = None
    citation_details: tuple[AgentCitation, ...] = ()
    tool_events: tuple[ToolEvent, ...] = ()
    observations: tuple[ToolObservation, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    grounding_evidence: Mapping[str, str] = field(default_factory=dict)
    knowledge_hits: tuple[KnowledgeRetrievalHit, ...] = ()


async def run_selected(
    *,
    plan: RoutePlan,
    worker: Callable[[RoutedAgent], Awaitable[SpecialistResult]],
    deadline: float,
    on_results: Callable[[tuple[SpecialistResult, ...]], None] | None = None,
) -> tuple[SpecialistResult, ...]:
    """所有已选 Agent 均获一次机会；超时取消未完成任务，不留后台调用。"""
    if not plan.selections:
        return ()
    if deadline <= time.monotonic():
        return tuple(SpecialistResult(item.agent_id, None, reason_code="deadline_exceeded") for item in plan.selections)
    tasks: list[asyncio.Future[SpecialistResult]] = [asyncio.ensure_future(worker(item)) for item in plan.selections]
    interrupted: asyncio.CancelledError | None = None
    try:
        done, pending = await asyncio.wait(tasks, timeout=max(0.0, deadline - time.monotonic()))
    except asyncio.CancelledError as error:
        # 外层同一截止时间可能先触发；先收集子任务的安全进度，再继续传播取消。
        interrupted = error
        done, pending = set(), set(tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    results: list[SpecialistResult] = []
    for selection, task in zip(plan.selections, tasks, strict=True):
        if task not in done:
            if task.done() and not task.cancelled():
                try:
                    partial = task.result()
                except Exception:
                    pass
                else:
                    if partial.agent_id == selection.agent_id:
                        # 截止后只保留诊断元数据，迟到回答、引用和事实不能发布或写入记忆。
                        results.append(
                            SpecialistResult(
                                selection.agent_id,
                                None,
                                reason_code="deadline_exceeded",
                                tool_events=partial.tool_events,
                                input_tokens=partial.input_tokens,
                                output_tokens=partial.output_tokens,
                            )
                        )
                        continue
            results.append(SpecialistResult(selection.agent_id, None, reason_code="deadline_exceeded"))
            continue
        if task.cancelled():
            results.append(SpecialistResult(selection.agent_id, None, reason_code="cancelled"))
            continue
        try:
            result = task.result()
        except ContextBudgetExceeded:
            results.append(SpecialistResult(selection.agent_id, None, reason_code="context_budget_exceeded"))
            continue
        except Exception:
            results.append(SpecialistResult(selection.agent_id, None, reason_code="agent_failed"))
            continue
        if result.agent_id != selection.agent_id:
            results.append(SpecialistResult(selection.agent_id, None, reason_code="agent_identity_mismatch"))
        else:
            results.append(result)
    collected = tuple(results)
    if on_results is not None:
        on_results(collected)
    if interrupted is not None:
        raise interrupted
    return collected
