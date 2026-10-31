"""一次动态多 Agent 运行的纯编排入口；具体数据库会话由外层注入。"""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace

from app.agents.core.reply_policy import (
    CustomerLanguage,
    compile_reply_policy,
    detect_customer_language,
    resolve_published_reply_profile,
)
from app.agents.delivery.reply_parts import DraftPartSink
from app.agents.orchestration.aggregator import ReviewedSuggestion, aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult, run_selected
from app.agents.orchestration.fallback import UNRESOLVED_REASONS, fixed_fallback_copy
from app.agents.orchestration.router import (
    RoutedAgent,
    RouteDecisionError,
    RouteModelPort,
    RoutePlan,
    route_agents,
)
from app.agents.runtime.context import ContextBudgetExceeded
from app.agents.runtime.operator_translation import translate_for_operator
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
    aggregate_input_tokens: int = 0
    aggregate_output_tokens: int = 0
    reply_plan: bool = False
    on_draft: DraftPartSink | None = None
    primary_agent_id: uuid.UUID | None = None
    run_timeout: asyncio.Timeout | None = None
    fallback_due: bool = False

    def capture_aggregate_usage(self, input_tokens: int, output_tokens: int) -> None:
        """每轮完成即记录数值，后续外层取消也不丢失已知用量。"""
        self.aggregate_input_tokens += input_tokens
        self.aggregate_output_tokens += output_tokens

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
            ReviewedSuggestion(
                None,
                "human_review",
                reason,
                tuple(item.agent_id for item in self.specialists),
                (),
                self.aggregate_input_tokens,
                self.aggregate_output_tokens,
            ),
            reason,
        )


def _review_required(
    reason: str, agent_ids: tuple[uuid.UUID, ...] = (), *, question_language: str | None = None
) -> ReviewedSuggestion:
    clarification = {
        "no_matching_agent": "当前没有适合处理该问题的已启用 Agent，请由人工确认。",
        "deadline_exceeded": "本次处理超时，暂时无法核实答案，请由人工继续确认。",
        "specialist_incomplete": "部分 Agent 未能完成核查，暂时无法给出完整答案，请由人工继续确认。",
        "rag_retrieval_timeout": "知识检索超时，暂时无法核实相关政策，请由人工继续确认。",
        "context_budget_exceeded": "本次信息超出模型上下文预算，请缩小问题范围或由人工继续确认。",
    }.get(reason)
    reply_language = None
    if reason == "no_matching_agent":
        supported = fixed_fallback_copy(question_language)
        if supported is not None:
            reply_language = supported[0]
            clarification = (
                "I cannot verify an answer to this question yet. Please let a human agent review it."
                if reply_language == "en"
                else "当前没有可核实的答案，请由人工客服确认。"
            )
    return ReviewedSuggestion(clarification, "human_review", reason, agent_ids, (), reply_language=reply_language)


async def _fixed_fallback(
    *,
    question: str,
    snapshot: RunSnapshot,
    original_route: RoutePlan,
    original_specialists: tuple[SpecialistResult, ...],
    original_suggestion: ReviewedSuggestion,
    reason: str,
    worker: Callable[[RoutedAgent], Awaitable[SpecialistResult]],
    deadline: float,
    progress: RunProgress | None,
) -> DynamicRunResult | None:
    """第三轮只借兜底 Agent 执行内部接管工具，买家文案由可信固定版本生成。"""
    if progress is None or not progress.fallback_due or reason not in UNRESOLVED_REASONS:
        return None
    candidates = tuple(agent for agent in snapshot.published_agents if agent.agent_type == "fallback")
    if not candidates:
        return None
    # 连续轮次和兜底用途已由可信状态机决定；无需再让模型决定是否选择兜底。
    detected = detect_customer_language(question)
    language = original_route.question_language or (
        detected.value if detected in {CustomerLanguage.ZH_CN, CustomerLanguage.EN} else None
    )
    selected = candidates[0]
    fallback_route = RoutePlan(
        (RoutedAgent(selected.id, "记录本轮未解决问题与人工接管需求", language),),
        len(candidates),
        0,
        0,
        language,
    )
    fallback_results = await run_selected(
        plan=fallback_route,
        worker=worker,
        deadline=deadline,
        on_results=lambda results: progress.capture((*original_specialists, *results)),
    )
    route = RoutePlan(
        (*original_route.selections, *fallback_route.selections),
        original_route.examined_count + fallback_route.examined_count,
        original_route.input_tokens + fallback_route.input_tokens,
        original_route.output_tokens + fallback_route.output_tokens,
        original_route.question_language or fallback_route.question_language,
    )
    specialists = (*original_specialists, *fallback_results)
    # 固定文案只进入人工审阅草稿；内部接管工具失败也不能让模型改写这段文案。
    fixed = fixed_fallback_copy(route.question_language)
    if fixed is None:
        return DynamicRunResult(RunPhase.REVIEW_REQUIRED, route, specialists, original_suggestion, reason)
    language, content = fixed
    suggestion = ReviewedSuggestion(
        content,
        "human_review",
        "fallback_third_round",
        tuple(item.agent_id for item in specialists),
        (),
        reply_language=language,
    )
    return DynamicRunResult(RunPhase.REVIEW_REQUIRED, route, specialists, suggestion, "fallback_third_round")


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
    provider_name: str = "unconfigured",
    model_name: str = "unconfigured",
) -> DynamicRunResult:
    """同一快照和截止时间贯穿路由、所有专家与最终汇总。"""
    state = RunStateMachine()
    state.advance(RunPhase.FROZEN)
    state.advance(RunPhase.ROUTING)
    # 物流更新由事件入口驱动；兜底仅在业务 Agent 无解后启动，二者不参与普通问题的语义路由。
    question_agents = tuple(
        agent for agent in snapshot.published_agents if agent.agent_type not in {"logistics_event", "fallback"}
    )
    empty_route = RoutePlan((), len(question_agents), 0, 0)
    try:
        route = await route_agents(
            question=question,
            agents=question_agents,
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
        detected = detect_customer_language(question)
        question_language = route.question_language or (
            detected.value if detected in {CustomerLanguage.ZH_CN, CustomerLanguage.EN} else None
        )
        no_match = _review_required("no_matching_agent", question_language=question_language)
        fallback = await _fixed_fallback(
            question=question,
            snapshot=snapshot,
            original_route=route,
            original_specialists=(),
            original_suggestion=no_match,
            reason="no_matching_agent",
            worker=worker,
            deadline=deadline,
            progress=progress,
        )
        state.advance(RunPhase.REVIEW_REQUIRED)
        if fallback is not None:
            return fallback
        return DynamicRunResult(state.phase, route, (), no_match, "no_matching_agent")
    language_policy = (
        (
            f"本轮当前问题的语种为 {route.question_language}。默认跟随本轮语种，"
            "不能被历史会话、路由子问题、工具原文或专家草稿改变；仅已发布要求明确指定其他语言时例外。",
        )
        if route.question_language
        else ()
    )
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
    participating = tuple(
        agent for agent in snapshot.published_agents if agent.id in {item.agent_id for item in specialists}
    )
    preferences = resolve_published_reply_profile(
        participating, primary_agent_id=progress.primary_agent_id if progress else None
    )
    compiled_policy = compile_reply_policy(preferences.profile)
    output_policies = (
        tuple(agent.prompt_sections.get("language_format", "") for agent in participating) + language_policy
    )
    if compiled_policy:
        output_policies += (compiled_policy,)
    privacy_policies = tuple(agent.prompt_sections.get("compliance", "") for agent in participating)
    aggregate = aggregate_results
    if progress is not None and progress.reply_plan:
        from app.agents.delivery.generation import aggregate_reply_plan

        suggestion = await aggregate_reply_plan(
            question=question,
            results=specialists,
            provider=aggregator,
            deadline=deadline,
            store_id=snapshot.store_id,
            max_output_tokens=max_answer_tokens,
            privacy_policies=tuple(
                agent.prompt_sections.get("compliance", "")
                for agent in snapshot.published_agents
                if agent.id in {item.agent_id for item in specialists}
            ),
            output_policies=output_policies,
            on_usage=progress.capture_aggregate_usage,
            on_draft=progress.on_draft,
        )
    else:
        suggestion = await aggregate(
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
            output_policies=output_policies,
            on_usage=progress.capture_aggregate_usage if progress is not None else None,
        )
    reply_language = (
        preferences.profile.reply_language
        if preferences.profile and preferences.profile.reply_language != "auto"
        else route.question_language
    )
    suggestion = replace(suggestion, reply_language=reply_language, reply_policy_source=preferences.source)
    if suggestion.content is not None and preferences.operator_language is not None:
        translation = await translate_for_operator(
            question=question,
            answer="\n\n".join(suggestion.reply_parts) if suggestion.reply_parts else suggestion.content,
            question_language=route.question_language,
            reply_language=reply_language,
            operator_language=preferences.operator_language,
            trigger_message_id=snapshot.trigger_message_id,
            provider=aggregator,
            provider_name=provider_name,
            model_name=model_name,
            deadline=deadline,
            on_usage=progress.capture_aggregate_usage if progress else None,
            max_output_tokens=max_answer_tokens,
            privacy_policies=privacy_policies,
            run_timeout=progress.run_timeout if progress else None,
        )
        suggestion = replace(
            suggestion,
            customer_translation=translation.translation,
            customer_translation_error_code=translation.error_code,
            input_tokens=suggestion.input_tokens + translation.input_tokens,
            output_tokens=suggestion.output_tokens + translation.output_tokens,
        )
    phase = (
        RunPhase.REVIEW_READY
        if suggestion.content is not None and suggestion.reason_code is None
        else RunPhase.REVIEW_REQUIRED
    )
    if suggestion.reason_code == "deadline_exceeded":
        phase = RunPhase.TIMEOUT
    if suggestion.reason_code in UNRESOLVED_REASONS:
        fallback = await _fixed_fallback(
            question=question,
            snapshot=snapshot,
            original_route=route,
            original_specialists=specialists,
            original_suggestion=suggestion,
            reason=suggestion.reason_code,
            worker=worker,
            deadline=deadline,
            progress=progress,
        )
        if fallback is not None:
            state.advance(RunPhase.REVIEW_REQUIRED)
            return fallback
    state.advance(phase)
    return DynamicRunResult(state.phase, route, specialists, suggestion, suggestion.reason_code)
