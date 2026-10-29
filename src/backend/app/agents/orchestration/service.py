"""一次动态多 Agent 运行的纯编排入口；具体数据库会话由外层注入。"""

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.agents.orchestration.aggregator import ReviewedSuggestion, aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult, run_selected
from app.agents.orchestration.router import (
    RoutedAgent,
    RouteDecisionError,
    RouteModelPort,
    RoutePlan,
    route_agents,
)
from app.agents.runtime.context import ContextBudgetExceeded
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.runtime.state import RunPhase, RunStateMachine


@dataclass(frozen=True, slots=True)
class DynamicRunResult:
    phase: RunPhase
    route: RoutePlan
    specialists: tuple[SpecialistResult, ...]
    suggestion: ReviewedSuggestion
    reason_code: str | None


@dataclass(slots=True)
class RunProgress:
    """入口超时/异常也能持久化的数值诊断；不保存草稿、引用、业务事实或记忆。"""

    route: RoutePlan = field(default_factory=lambda: RoutePlan((), 0, 0, 0))
    specialists: tuple[SpecialistResult, ...] = ()

    def capture(self, results: tuple[SpecialistResult, ...]) -> None:
        self.specialists = tuple(
            SpecialistResult(
                item.agent_id,
                None,
                reason_code=item.reason_code,
                tool_events=item.tool_events,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
            )
            for item in results
        )

    def failure(self, reason: str) -> DynamicRunResult:
        return DynamicRunResult(
            RunPhase.TIMEOUT if reason == "deadline_exceeded" else RunPhase.REVIEW_REQUIRED,
            self.route,
            self.specialists,
            ReviewedSuggestion(None, "human_review", reason, tuple(item.agent_id for item in self.specialists), ()),
            reason,
        )


def _review_required(reason: str, agent_ids: tuple[uuid.UUID, ...] = ()) -> ReviewedSuggestion:
    clarification = {
        "no_matching_agent": "当前没有适合处理该问题的已启用 Agent，请由人工确认。",
        "deadline_exceeded": "本次处理超时，暂时无法核实答案，请由人工继续确认。",
        "specialist_incomplete": "部分 Agent 未能完成核查，暂时无法给出完整答案，请由人工继续确认。",
        "rag_retrieval_timeout": "知识检索超时，暂时无法核实相关政策，请由人工继续确认。",
        "context_budget_exceeded": "本次信息超出模型上下文预算，请缩小问题范围或由人工继续确认。",
    }.get(reason)
    return ReviewedSuggestion(clarification, "human_review", reason, agent_ids, ())


async def execute_dynamic_run(
    *,
    question: str,
    snapshot: RunSnapshot,
    router: RouteModelPort,
    aggregator: RouteModelPort,
    worker: Callable[[RoutedAgent], Awaitable[SpecialistResult]],
    deadline: float,
    max_catalog_tokens: int,
    routing_context: str = "",
    max_answer_tokens: int = 1024,
    progress: RunProgress | None = None,
) -> DynamicRunResult:
    """同一快照和截止时间贯穿路由、所有专家与最终汇总。"""
    state = RunStateMachine()
    state.advance(RunPhase.FROZEN)
    state.advance(RunPhase.ROUTING)
    empty_route = RoutePlan((), len(snapshot.published_agents), 0, 0)
    try:
        route = await route_agents(
            question=question,
            agents=snapshot.published_agents,
            provider=router,
            deadline=deadline,
            max_catalog_tokens=max_catalog_tokens,
            routing_context=routing_context,
        )
    except TimeoutError:
        state.advance(RunPhase.TIMEOUT)
        return DynamicRunResult(
            state.phase, empty_route, (), _review_required("deadline_exceeded"), "deadline_exceeded"
        )
    except ContextBudgetExceeded:
        state.advance(RunPhase.REVIEW_REQUIRED)
        return DynamicRunResult(
            state.phase, empty_route, (), _review_required("context_budget_exceeded"), "context_budget_exceeded"
        )
    except RouteDecisionError as error:
        state.advance(RunPhase.REVIEW_REQUIRED)
        return DynamicRunResult(state.phase, empty_route, (), _review_required(error.reason_code), error.reason_code)
    if progress is not None:
        progress.route = route
    if not route.selections:
        state.advance(RunPhase.REVIEW_REQUIRED)
        return DynamicRunResult(state.phase, route, (), _review_required("no_matching_agent"), "no_matching_agent")
    state.advance(RunPhase.EXECUTING)
    specialists = await run_selected(
        plan=route, worker=worker, deadline=deadline, on_results=progress.capture if progress is not None else None
    )
    failed = tuple(item for item in specialists if item.reason_code or not item.answer)
    if failed:
        if any(item.reason_code == "context_budget_exceeded" for item in failed):
            reason = "context_budget_exceeded"
        elif any(item.reason_code == "rag_retrieval_timeout" for item in failed):
            reason = "rag_retrieval_timeout"
        elif time.monotonic() >= deadline:
            reason = "deadline_exceeded"
        else:
            reason = "specialist_incomplete"
        state.advance(RunPhase.REVIEW_REQUIRED if reason != "deadline_exceeded" else RunPhase.TIMEOUT)
        return DynamicRunResult(
            state.phase,
            route,
            specialists,
            _review_required(reason, tuple(item.agent_id for item in specialists)),
            reason,
        )
    state.advance(RunPhase.AGGREGATING)
    suggestion = await aggregate_results(
        question=question,
        results=specialists,
        provider=aggregator,
        deadline=deadline,
        store_id=snapshot.store_id,
        max_output_tokens=max_answer_tokens,
        privacy_policies=tuple(
            agent.prompt_sections["compliance"]
            for agent in snapshot.published_agents
            if any(item.agent_id == agent.id for item in specialists) and "compliance" in agent.prompt_sections
        ),
    )
    phase = (
        RunPhase.REVIEW_READY
        if suggestion.content is not None and suggestion.reason_code is None
        else RunPhase.REVIEW_REQUIRED
    )
    if suggestion.reason_code == "deadline_exceeded":
        phase = RunPhase.TIMEOUT
    state.advance(phase)
    return DynamicRunResult(state.phase, route, specialists, suggestion, suggestion.reason_code)
