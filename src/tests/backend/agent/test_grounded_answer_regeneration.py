"""被拒回答须重新基于证据生成并复核，不能重复提交旧稿刷判定。"""

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


def verdict(supported: bool) -> ToolTurn:
    return ToolTurn(
        None,
        (
            FunctionCall(
                "review",
                "review_answer_evidence",
                {
                    "supported": supported,
                    "reason_code": "supported" if supported else "unsupported",
                    "evidence_ids": ["e1"],
                    "privacy_reviewed": True,
                    "output_rewrite_required": False,
                    "redactions": [],
                },
            ),
        ),
        {},
        3,
        1,
    )


@pytest.mark.asyncio
async def test_rejected_answer_is_replaced_from_verified_evidence_and_reviewed_again():
    calls = []

    async def complete(**kwargs):
        calls.append(kwargs)
        return [
            ToolTurn("Payment completed.", (), {}, 2, 1),
            verdict(False),
            ToolTurn("The order has shipped. Payment status is not provided.", (), {}, 4, 2),
            verdict(True),
        ][len(calls) - 1]

    result = await aggregate_results(
        question="Check my order",
        results=(
            SpecialistResult(uuid.uuid4(), "shipped", verified_facts={"status": "shipped", "payment_status": None}),
        ),
        provider=SimpleNamespace(complete=complete),
        store_id=uuid.uuid4(),
        deadline=time.monotonic() + 2,
    )
    assert result.content == "The order has shipped. Payment status is not provided."
    assert (result.input_tokens, result.output_tokens) == (12, 5)
    revised_payload = json.loads(calls[2]["messages"][-1]["content"])
    assert revised_payload["evidence"]
    assert "Payment completed." not in json.dumps(calls[2]["messages"])
    assert calls[3]["tools"]


@pytest.mark.asyncio
async def test_same_rejected_answer_is_not_resubmitted_until_the_model_changes_its_vote():
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn("Payment completed.", (), {}, 2, 1),
                verdict(False),
                ToolTurn("Payment completed.", (), {}, 4, 2),
            ]
        )
    )
    result = await aggregate_results(
        question="Check my order",
        results=(SpecialistResult(uuid.uuid4(), "shipped", verified_facts={"status": "shipped"}),),
        provider=provider,
        store_id=uuid.uuid4(),
        deadline=time.monotonic() + 2,
    )
    assert result.content is None and result.reason_code == "answer_not_grounded"
    assert provider.complete.await_count == 3
    assert (result.input_tokens, result.output_tokens) == (9, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_regeneration_keeps_original_deadline_and_completed_usage(cancel):
    started = asyncio.Event()
    used = []
    calls = 0

    async def complete(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ToolTurn("Payment completed.", (), {}, 2, 1)
        if calls == 2:
            return verdict(False)
        started.set()
        await asyncio.Future()

    task = asyncio.create_task(
        aggregate_results(
            question="Check my order",
            results=(SpecialistResult(uuid.uuid4(), "shipped", verified_facts={"status": "shipped"}),),
            provider=SimpleNamespace(complete=complete),
            store_id=uuid.uuid4(),
            deadline=time.monotonic() + (2 if cancel else 0.03),
            on_usage=lambda i, o: used.append((i, o)),
        )
    )
    await asyncio.wait_for(started.wait(), 1)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert result.content is None and result.reason_code == "deadline_exceeded"
        assert (result.input_tokens, result.output_tokens) == (5, 2)
    assert tuple(map(sum, zip(*used, strict=True))) == (5, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["privacy_flag", "evidence_id", "segment_id", "tool_name"])
async def test_invalid_review_protocol_does_not_trigger_regeneration(invalid):
    turn = verdict(True)
    args = dict(turn.calls[0].arguments)
    name = "review_answer_evidence"
    if invalid == "privacy_flag":
        args.pop("privacy_reviewed")
    elif invalid == "evidence_id":
        args["evidence_ids"] = ["made-up"]
    elif invalid == "segment_id":
        args["redactions"] = [{"segment_id": "not-present", "text": "unknown"}]
    else:
        name = "unknown_review"
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn("The order shipped.", (), {}, 2, 1),
                ToolTurn(None, (FunctionCall("review", name, args),), {}, 3, 1),
            ]
        )
    )
    result = await aggregate_results(
        question="Check my order",
        results=(SpecialistResult(uuid.uuid4(), "shipped", verified_facts={"status": "shipped"}),),
        provider=provider,
        store_id=uuid.uuid4(),
        deadline=time.monotonic() + 2,
    )
    assert result.content is None and result.reason_code == "evidence_review_invalid"
    assert provider.complete.await_count == 2


@pytest.mark.asyncio
async def test_privacy_rewritten_rejected_answer_is_not_submitted_to_review_twice():
    initial = "The order shipped. Email: synthetic.customer@example.com."
    private_review = verdict(True)
    args = dict(private_review.calls[0].arguments)
    args["redactions"] = [{"segment_id": "s2", "text": "synthetic.customer@example.com"}]
    provider = SimpleNamespace(
        complete=AsyncMock(
            side_effect=[
                ToolTurn(initial, (), {}, 2, 1),
                ToolTurn(None, (FunctionCall("review", "review_answer_evidence", args),), {}, 3, 1),
                ToolTurn("Payment completed.", (), {}, 4, 2),
                verdict(False),
                ToolTurn("Payment completed.", (), {}, 4, 2),
                verdict(True),
            ]
        )
    )
    result = await aggregate_results(
        question="Check my order",
        results=(SpecialistResult(uuid.uuid4(), "shipped", verified_facts={"status": "shipped"}),),
        provider=provider,
        store_id=uuid.uuid4(),
        deadline=time.monotonic() + 2,
    )
    assert result.content is None and result.reason_code == "answer_not_grounded"
    assert provider.complete.await_count == 5
