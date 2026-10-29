"""过滤私密值后由模型重新组织正文，并独立核验重写没有恢复已删信息。"""

import asyncio
import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.orchestration.aggregator import aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.providers.tool_calling import FunctionCall, ToolTurn

PRIVATE = "buyer@example.invalid"


class PrivacyModel:
    def __init__(self, *, restore_private=False, unsupported=False):
        self.generations = 0
        self.reviews = 0
        self.restore_private = restore_private
        self.unsupported = unsupported

    async def complete(self, *, messages, tools, max_output_tokens):
        if tools:
            self.reviews += 1
            payload = json.loads(messages[-1]["content"])
            redactions = [
                {"segment_id": segment["id"], "text": PRIVATE}
                for segment in payload["answer_segments"]
                if PRIVATE in segment["text"]
            ]
            arguments = {
                "supported": not self.unsupported,
                "reason_code": "unsupported" if self.unsupported else "supported",
                "evidence_ids": payload["allowed_evidence_ids"],
                "privacy_reviewed": True,
                "output_rewrite_required": False,
                "redactions": redactions,
            }
            return ToolTurn(None, (FunctionCall("review", "review_answer_evidence", arguments),), {}, 3, 2)
        self.generations += 1
        if self.generations == 1:
            text = f"Your order has shipped. Contact: {PRIVATE}."
        else:
            assert PRIVATE not in json.dumps(messages)
            assert "敏感信息已隐藏" not in json.dumps(messages)
            if self.unsupported:
                assert json.loads(messages[-1]["content"])["evidence"]
                return ToolTurn(f"Your order has shipped. Contact: {PRIVATE}.", (), {}, 3, 2)
            assert "evidence" not in json.loads(messages[-1]["content"])
            text = f"Your order has shipped. Contact: {PRIVATE}." if self.restore_private else "Your order has shipped."
        return ToolTurn(text, (), {}, 3, 2)


async def _run(model):
    return await aggregate_results(
        question="Where is my order?",
        results=(SpecialistResult(uuid.uuid4(), "Order shipped", verified_facts={"status": "shipped"}),),
        provider=model,
        deadline=time.monotonic() + 3,
        store_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_sensitive_value_is_removed_then_remaining_answer_is_recomposed():
    model = PrivacyModel()
    result = await _run(model)
    assert result.content == "Your order has shipped."
    assert (model.generations, model.reviews) == (2, 2)
    assert (result.input_tokens, result.output_tokens) == (12, 8)


@pytest.mark.asyncio
async def test_rewriter_restoring_private_value_is_not_displayed_or_retried_forever():
    model = PrivacyModel(restore_private=True)
    result = await _run(model)
    assert result.content is None
    assert result.reason_code == "privacy_rewrite_incomplete"
    assert (model.generations, model.reviews) == (2, 1)
    assert (result.input_tokens, result.output_tokens) == (9, 6)


@pytest.mark.asyncio
async def test_unsupported_remaining_facts_are_not_laundered_by_privacy_rewriting():
    model = PrivacyModel(unsupported=True)
    result = await _run(model)
    assert result.content is None
    assert (model.generations, model.reviews) == (2, 1)
    assert result.reason_code == "answer_not_grounded"


@pytest.mark.asyncio
async def test_semantic_language_mismatch_recomposes_safe_body_in_original_buyer_language():
    from unittest.mock import AsyncMock

    from app.agents.safety.grounding import review_final_answer

    def reviewed(rewrite):
        return ToolTurn(
            None,
            (
                FunctionCall(
                    "review",
                    "review_answer_evidence",
                    {
                        "supported": True,
                        "reason_code": "supported",
                        "evidence_ids": ["e1"],
                        "privacy_reviewed": True,
                        "output_rewrite_required": rewrite,
                        "redactions": [],
                    },
                ),
            ),
            {},
            3,
            2,
        )

    model = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                reviewed(True),
                ToolTurn("Your order has shipped.", (), {}, 4, 2),
                reviewed(False),
            ]
        )
    )
    result = await review_final_answer(
        question="Where is my order?",
        answer="您的订单已发货。",
        evidence={"status": "shipped"},
        provider=model,
        deadline=time.monotonic() + 2,
        output_policies=("跟随买家原始语言回复",),
    )
    assert result.answer == "Your order has shipped."
    payload = json.loads(model.complete.await_args_list[1].kwargs["messages"][-1]["content"])
    assert payload["question"] == "Where is my order?"
    assert payload["filtered_answer"] == "您的订单已发货。" and "evidence" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_at", [3, 4])
async def test_outer_cancellation_keeps_completed_aggregate_review_and_rewrite_usage(monkeypatch, cancel_at):
    from app.agents.orchestration import service
    from app.agents.orchestration.router import RoutedAgent, RoutePlan

    started = asyncio.Event()

    class SlowModel(PrivacyModel):
        calls = 0

        async def complete(self, **kwargs):
            self.calls += 1
            if self.calls == cancel_at:
                started.set()
                await asyncio.Future()
            return await super().complete(**kwargs)

    agent = uuid.uuid4()
    monkeypatch.setattr(
        service, "route_agents", AsyncMock(return_value=RoutePlan((RoutedAgent(agent, "order"),), 1, 1, 1))
    )
    progress = service.RunProgress()
    task = asyncio.create_task(
        service.execute_dynamic_run(
            question="Where is my order?",
            snapshot=SimpleNamespace(store_id=uuid.uuid4(), published_agents=()),
            router=SimpleNamespace(),
            aggregator=SlowModel(),
            worker=AsyncMock(return_value=SpecialistResult(agent, "shipped", verified_facts={"status": "shipped"})),
            deadline=time.monotonic() + 5,
            max_catalog_tokens=1000,
            progress=progress,
        )
    )
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    failed = progress.failure("deadline_exceeded")
    assert failed.suggestion.content is None
    assert failed.specialists[0].answer is None
    assert (failed.suggestion.input_tokens, failed.suggestion.output_tokens) == (
        (cancel_at - 1) * 3,
        (cancel_at - 1) * 2,
    )
