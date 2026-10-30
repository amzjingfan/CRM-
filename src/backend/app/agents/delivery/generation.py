"""真正流式生成审阅计划；每条完整答复仍独立通过既有隐私与依据复核。"""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Protocol, runtime_checkable

from langchain_core.tools import BaseTool

from app.agents.core.errors import LLMProviderError
from app.agents.delivery.reply_parts import DraftPartSink, ReplyDraftCollector, parts_from_turn, submit_reply_parts
from app.agents.orchestration.aggregator import (
    _AGGREGATE_SYSTEM,
    ReviewedSuggestion,
    _conflicting_facts,
    aggregate_results,
)
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RouteModelPort
from app.agents.providers.text_streaming import ModelDeltaCallback
from app.agents.providers.tool_calling import ToolTurn
from app.agents.runtime.context import ContextBudgetExceeded
from app.agents.safety.input import prepare_untrusted_text
from app.agents.tools.business_identifiers import business_identifier_values
from app.shared.exceptions.errors import AppError

REPLY_PLAN_PROMPT_VERSION = "agent-reply-plan-v1.1.0"


@runtime_checkable
class StreamingReplyProvider(RouteModelPort, Protocol):
    async def complete_streaming(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
        on_delta: ModelDeltaCallback,
    ) -> ToolTurn: ...


class _CandidateProvider:
    """首轮复用已经生成的候选；实际复核/重组仍走原Provider及其预算。"""

    def __init__(self, inner: RouteModelPort, candidate: str) -> None:
        self.inner = inner
        self.candidate: str | None = candidate

    async def complete(
        self, *, messages: tuple[dict[str, object], ...], tools: tuple[BaseTool, ...], max_output_tokens: int
    ) -> ToolTurn:
        if self.candidate is not None:
            text, self.candidate = self.candidate, None
            return ToolTurn(text, (), {"role": "assistant", "content": text}, 0, 0)
        return await self.inner.complete(messages=messages, tools=tools, max_output_tokens=max_output_tokens)


async def aggregate_reply_plan(
    *,
    question: str,
    results: tuple[SpecialistResult, ...],
    provider: RouteModelPort,
    deadline: float,
    store_id: uuid.UUID,
    max_output_tokens: int = 1024,
    privacy_policies: tuple[str, ...] = (),
    output_policies: tuple[str, ...] = (),
    on_usage: Callable[[int, int], None] | None = None,
    on_draft: DraftPartSink | None = None,
) -> ReviewedSuggestion:
    agent_ids = tuple(item.agent_id for item in results)
    if not results or not any(item.answer for item in results) or _conflicting_facts(results):
        return await aggregate_results(
            question=question,
            results=results,
            provider=provider,
            deadline=deadline,
            store_id=store_id,
            max_output_tokens=max_output_tokens,
            privacy_policies=privacy_policies,
            output_policies=output_policies,
            on_usage=on_usage,
        )
    citations = tuple(dict.fromkeys(citation for item in results for citation in item.citations))
    missing = not citations and not any(item.verified_facts for item in results)
    input_tokens = output_tokens = 0

    def failure(reason: str) -> ReviewedSuggestion:
        return ReviewedSuggestion(None, "human_review", reason, agent_ids, (), input_tokens, output_tokens)

    try:
        safe_question = prepare_untrusted_text(question, source="user_message").text
        drafts = (
            []
            if missing
            else [
                {
                    "agent_id": str(item.agent_id),
                    "untrusted_draft": item.answer,
                    "verified_facts": dict(item.verified_facts),
                    "citations": item.citations,
                }
                for item in results
                if item.answer
            ]
        )
        messages: tuple[dict[str, object], ...] = (
            {
                "role": "system",
                "content": _AGGREGATE_SYSTEM
                + (
                    "仅通过submit_reply_parts提交答复。当前question是一条买家消息，不混答历史消息。"
                    "简单问题一条简短答复；多个独立问题按自然顺序拆为完整、各自可理解的短答复。"
                    "各条分别负责不同问题，不得每条重复回答整题，也不重复列出其他条已回答的事实。"
                    "每条最多2000 UTF-16单元，优先1200以内。物流正文仅最新节点、时间和必要定位信息；"
                    "不要列全部轨迹，完整详情随后以物流卡片呈现。不输出内部引用、审核或发送状态。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": safe_question,
                        "drafts": drafts,
                        "evidence_status": "no_verified_evidence" if missing else "available",
                        "published_output_policies": list(output_policies),
                        "max_answer_characters": 2000,
                        "target_answer_characters": 1200,
                    },
                    ensure_ascii=False,
                ),
            },
        )
        async with asyncio.timeout(max(0.0, deadline - time.monotonic())):
            if on_draft is not None and isinstance(provider, StreamingReplyProvider):
                literals = tuple(
                    value
                    for item in results
                    for observation in item.observations
                    for value in business_identifier_values(observation.facts)
                )
                turn = await provider.complete_streaming(
                    messages=messages,
                    tools=(submit_reply_parts,),
                    max_output_tokens=max_output_tokens,
                    on_delta=ReplyDraftCollector(on_draft, literal_values=literals),
                )
            else:
                turn = await provider.complete(
                    messages=messages, tools=(submit_reply_parts,), max_output_tokens=max_output_tokens
                )
        input_tokens += turn.input_tokens
        output_tokens += turn.output_tokens
        if on_usage is not None:
            on_usage(turn.input_tokens, turn.output_tokens)
        parts = parts_from_turn(turn)
    except asyncio.CancelledError as error:
        if on_usage is not None:
            on_usage(getattr(error, "input_tokens", 0), getattr(error, "output_tokens", 0))
        raise
    except TimeoutError:
        return failure("deadline_exceeded")
    except ContextBudgetExceeded:
        return failure("context_budget_exceeded")
    except AppError:
        return failure("sensitive_agent_input")
    except LLMProviderError as error:
        input_tokens += error.input_tokens
        output_tokens += error.output_tokens
        if on_usage is not None:
            on_usage(error.input_tokens, error.output_tokens)
        return failure(error.code.value.lower())
    except (ValueError, TypeError):
        return failure("invalid_reply_parts_submission")

    verified = []
    reason = None
    for index, part in enumerate(parts):
        result = await aggregate_results(
            question=safe_question,
            results=results,
            provider=_CandidateProvider(provider, part),
            deadline=deadline,
            store_id=store_id,
            max_output_tokens=max_output_tokens,
            privacy_policies=privacy_policies,
            output_policies=(
                *output_policies,
                (
                    f"当前正在独立复核有序分批答复第{index + 1}/{len(parts)}条，只需该条内容完整且有依据，"
                    "不要求在该条重复其他答复。物流仅最新节点；完整轨迹由卡片展示。"
                ),
            ),
            on_usage=on_usage,
            regenerate_unsupported=False,
        )
        input_tokens += result.input_tokens
        output_tokens += result.output_tokens
        if result.content is None:
            if result.reason_code == "answer_not_grounded":
                # 单段失去依据后不能拿整题重答该段，否则会把同一整题答案重复交付多次。
                # 废弃整组候选，仅从原始专家证据重建一条完整答复；被拒正文不回投。
                fallback = await aggregate_results(
                    question=safe_question,
                    results=results,
                    provider=provider,
                    deadline=deadline,
                    store_id=store_id,
                    max_output_tokens=max_output_tokens,
                    privacy_policies=privacy_policies,
                    output_policies=(*output_policies, "本次重建一条完整简洁答复，不重复答案；物流仅最新节点。"),
                    on_usage=on_usage,
                )
                return replace(
                    fallback,
                    reply_parts=(fallback.content,) if fallback.content else (),
                    input_tokens=input_tokens + fallback.input_tokens,
                    output_tokens=output_tokens + fallback.output_tokens,
                )
            return failure(result.reason_code or "answer_not_grounded")
        verified.append(result.content)
        reason = reason or result.reason_code
    return replace(
        result,
        content=verified[0],
        reply_parts=tuple(verified),
        reason_code=reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
