"""汇总模型不能篡改工具事实、政策时限或通过无依据的退款结果。"""

import json
import time
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.orchestration.aggregator import ReviewedSuggestion, aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutePlan
from app.agents.orchestration.service import DynamicRunResult
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.rag.retriever import EvidenceBundle
from app.agents.runtime.state import RunPhase


class ReviewedModel:
    def __init__(self, answer: str, supported: bool) -> None:
        self.answer = answer
        self.supported = supported
        self.saw_original_evidence = False

    async def complete(self, *, messages, tools, max_output_tokens):
        if not tools:
            return ToolTurn(self.answer, (), {"role": "assistant", "content": self.answer}, 1, 1)
        payload = json.loads(messages[-1]["content"])
        self.saw_original_evidence = "七天内申请" in str(payload["evidence"])
        call = FunctionCall(
            "review-1",
            "review_answer_evidence",
            {
                "supported": self.supported,
                "evidence_ids": list(payload["evidence"]) if self.supported else [],
                "reason_code": "supported" if self.supported else "unsupported",
            },
        )
        return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 1, 1)


@pytest.mark.asyncio
async def test_order_status_does_not_authorize_refund_completion() -> None:
    result = await aggregate_results(
        question="我的退款怎么样",
        results=(
            SpecialistResult(
                uuid.uuid4(),
                "订单已发货",
                verified_facts={"query_order.status": "shipped"},
                successful_tools=("query_order",),
            ),
        ),
        provider=ReviewedModel("您的退款已经到账。", True),
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert result.reason_code == "unsafe_aggregate_output"
    assert result.content is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("answer", "supported"), [("七天内申请。", True), ("九十天内无条件退货。", False)])
async def test_independent_review_receives_policy_text_and_rejects_changed_window(answer, supported) -> None:
    chunk = str(uuid.uuid4())
    model = ReviewedModel(answer, supported)
    result = await aggregate_results(
        question="如何退货",
        results=(
            SpecialistResult(
                uuid.uuid4(), "七天内申请。", citations=(chunk,), grounding_evidence={chunk: "七天内申请"}
            ),
        ),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert model.saw_original_evidence
    assert (result.reason_code is None) is supported
    assert result.content == answer if supported else result.content is None


@pytest.mark.asyncio
async def test_approval_revoked_during_aggregation_hides_final_answer_and_citations(monkeypatch) -> None:
    from app.agents.runtime import execution

    agent, chunk = uuid.uuid4(), uuid.uuid4()
    specialist = SpecialistResult(
        agent, "旧政策", citations=(str(chunk),), knowledge_hits=(SimpleNamespace(chunk_id=chunk),)
    )
    result = DynamicRunResult(
        RunPhase.REVIEW_READY,
        RoutePlan((), 1, 0, 0),
        (specialist,),
        ReviewedSuggestion("旧政策回答", "human_review", None, (agent,), (str(chunk),)),
        None,
    )

    @asynccontextmanager
    async def session_factory():
        yield AsyncMock()

    monkeypatch.setattr(execution, "session_factory", session_factory)
    monkeypatch.setattr(execution, "revalidate_evidence", AsyncMock(return_value=EvidenceBundle((), 1)))
    final = await execution.finalize_result_evidence(
        result, SimpleNamespace(published_agents=(SimpleNamespace(id=agent),))
    )
    assert final.reason_code == "knowledge_approval_changed"
    assert final.suggestion.content is None
    assert final.suggestion.citations == ()
    assert final.specialists[0].citation_details == ()
