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
        self.review_evidence = None

    async def complete(self, *, messages, tools, max_output_tokens):
        if not tools:
            return ToolTurn(self.answer, (), {"role": "assistant", "content": self.answer}, 1, 1)
        payload = json.loads(messages[-1]["content"])
        self.review_evidence = payload["evidence"]
        self.saw_original_evidence = "七天内申请" in str(payload["evidence"])
        call = FunctionCall(
            "review-1",
            "review_answer_evidence",
            {
                "supported": self.supported,
                "evidence_ids": list(payload["evidence"]) if self.supported else [],
                "reason_code": "supported" if self.supported else "unsupported",
                "privacy_reviewed": True,
                "output_rewrite_required": False,
                "redactions": [],
            },
        )
        return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 1, 1)


@pytest.mark.asyncio
async def test_order_status_does_not_authorize_refund_completion() -> None:
    model = ReviewedModel("您的退款已经到账。", False)
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
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert result.reason_code == "answer_not_grounded"
    assert result.content is None
    assert model.review_evidence is not None


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


@pytest.mark.asyncio
async def test_tool_permission_revoked_after_generation_hides_answer_and_memory_facts(monkeypatch) -> None:
    from app.agents.runtime import execution

    agent = uuid.uuid4()
    specialist = SpecialistResult(
        agent, "订单摘要", verified_facts={"query_order.status": "shipped"}, successful_tools=("query_order",)
    )
    result = DynamicRunResult(
        RunPhase.REVIEW_READY,
        RoutePlan((), 1, 0, 0),
        (specialist,),
        ReviewedSuggestion("订单已发货", "human_review", None, (agent,), ()),
        None,
    )

    @asynccontextmanager
    async def sessions():
        yield AsyncMock()

    monkeypatch.setattr(execution, "session_factory", sessions)
    monkeypatch.setattr(execution, "current_permissions", AsyncMock(return_value=set()), raising=False)
    final = await execution.finalize_result_evidence(
        result, SimpleNamespace(store_id=uuid.uuid4(), published_agents=()), user=SimpleNamespace(id=uuid.uuid4())
    )
    assert final.suggestion.content is None
    assert final.reason_code == "tool_permission_changed"
    assert not final.specialists[0].verified_facts
    assert final.specialists[0].reason_code == "tool_permission_changed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statuses", "supported", "with_observation"),
    [
        (["COMPLETED"], True, True),
        (["PENDING"], False, True),
        (["PENDING", "COMPLETED"], False, True),
        (["COMPLETED"], True, False),
    ],
)
async def test_aftersales_status_requires_current_scoped_facts_and_independent_review(
    statuses, supported, with_observation
):
    from app.agents.runtime.worker import _verified_facts
    from app.agents.tools.loop import ToolObservation

    facts = {
        "order_ref": "o1",
        "returns": [
            {"return_ref": f"r{i + 1}", "return_type": "REFUND", "return_status": status}
            for i, status in enumerate(statuses)
        ],
    }
    observation = ToolObservation("aftersales-1", "query_aftersales", "succeeded", facts, "a" * 16)
    observations = (observation,) if with_observation else ()
    model = ReviewedModel("The refund has been completed.", supported and with_observation)
    answer = await aggregate_results(
        question="What is the status of refund application r1?",
        results=(
            SpecialistResult(
                uuid.uuid4(),
                "The refund has been completed.",
                verified_facts=_verified_facts((observation,)),
                successful_tools=("query_aftersales",),
                observations=observations,
            ),
        ),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    if with_observation:
        assert model.review_evidence is not None
        assert "r1" in str(model.review_evidence)
        assert all(status in str(model.review_evidence) for status in statuses)
    else:
        assert model.review_evidence is not None
    assert answer.content == ("The refund has been completed." if supported and with_observation else None)
    assert answer.reason_code == (
        None if supported and with_observation else "answer_not_grounded" if with_observation else "answer_not_grounded"
    )


@pytest.mark.asyncio
async def test_semantic_review_retains_clarification_about_unverified_refund_without_keyword_block() -> None:
    answer = "订单已发货；本次查询未核实退款是否到账，需由坐席另行确认。"
    model = ReviewedModel(answer, True)
    result = await aggregate_results(
        question="订单和退款进度如何",
        results=(SpecialistResult(uuid.uuid4(), answer, verified_facts={"query_order.status": "shipped"}),),
        provider=model,
        deadline=time.monotonic() + 2,
        store_id=uuid.uuid4(),
    )
    assert model.review_evidence is not None
    assert result.content == answer
    assert result.reason_code is None
