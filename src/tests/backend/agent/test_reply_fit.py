"""回答过长交模型精简，缺少依据仍按原问题语言澄清。"""

import json
import time
import uuid

import pytest
from agent._review_helpers import accepted_review_turn

from app.agents.orchestration.aggregator import aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.providers.tool_calling import ToolTurn


class FitModel:
    def __init__(self, answers, *, reject=None, redaction=None):
        self.answers = iter(answers)
        self.reject = reject
        self.redaction = redaction
        self.payloads = []
        self.reviews = []

    async def complete(self, *, messages, tools, max_output_tokens):
        payload = json.loads(messages[-1]["content"])
        if tools:
            self.reviews.append(payload["answer"])
            turn = accepted_review_turn(messages)
            if self.reject and self.reject in payload["answer"]:
                turn.calls[0].arguments.update(supported=False, reason_code="unsupported", evidence_ids=[])
            if self.redaction and self.redaction in payload["answer"]:
                segment = next(x for x in payload["answer_segments"] if self.redaction in x["text"])
                turn.calls[0].arguments["redactions"] = [{"segment_id": segment["id"], "text": self.redaction}]
            return turn
        self.payloads.append(payload)
        answer = next(self.answers)
        return ToolTurn(answer, (), {"role": "assistant", "content": answer}, 3, 2)


async def run(model, *, question="Where is my parcel?", evidence=True, **kwargs):
    return await aggregate_results(
        question=question,
        results=(
            SpecialistResult(
                uuid.uuid4(), "UNVERIFIED_DRAFT", verified_facts={"status": "in_transit"} if evidence else {}
            ),
        ),
        provider=model,
        deadline=time.monotonic() + 3,
        store_id=uuid.uuid4(),
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["In transit. Please check again later.", "包裹正在运输中，请稍后查看。"])
async def test_long_answer_is_model_shortened_then_independently_reviewed(answer):
    long = answer * 210
    model = FitModel([long, answer])
    result = await run(model)
    assert result.content == answer
    assert model.reviews == [long, answer]
    assert model.payloads[1]["filtered_answer"] == long
    assert model.payloads[1]["max_answer_characters"] == 2000
    assert "evidence" not in model.payloads[1]
    assert (result.input_tokens, result.output_tokens) == (10, 8)


@pytest.mark.asyncio
async def test_platform_count_uses_utf16_and_does_not_slice_emoji():
    model = FitModel(["📦" * 1001, "Parcel in transit."])
    result = await run(model)
    assert result.content == "Parcel in transit."
    assert len(model.reviews) == 2


@pytest.mark.asyncio
async def test_identical_oversize_rewrite_cannot_escape_or_loop():
    model = FitModel(["x" * 2001, "x" * 2001])
    result = await run(model)
    assert result.content is None and result.reason_code == "answer_too_long"


@pytest.mark.asyncio
async def test_short_answer_needs_no_extra_generation():
    model = FitModel(["In transit."])
    result = await run(model)
    assert result.content == "In transit." and len(model.payloads) == 1
    assert model.payloads[0]["max_answer_characters"] == 2000


@pytest.mark.asyncio
async def test_redacted_values_do_not_enter_length_rewrite():
    model = FitModel(
        ["In transit. " * 190 + "Email: private@example.com.", "In transit."], redaction="private@example.com"
    )
    result = await run(model)
    assert result.content == "In transit."
    assert "private@example.com" not in model.payloads[1]["filtered_answer"]


@pytest.mark.asyncio
async def test_new_fact_added_by_shortener_requires_rejection_and_regeneration():
    model = FitModel(["In transit. " * 190, "Guaranteed refund.", "In transit."], reject="Guaranteed refund")
    result = await run(model)
    assert result.content == "In transit."
    assert "Guaranteed refund." in model.reviews


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "What is the refund deadline?",
            "I cannot confirm the refund deadline from the available information. Please ask a human agent.",
        ),
        ("退款期限是多少天？", "当前知识没有可核实的退款期限，请由人工确认。"),
    ],
)
async def test_missing_evidence_uses_model_language_without_unverified_drafts(question, answer):
    model = FitModel([answer])
    result = await run(model, question=question, evidence=False)
    assert result.content == answer and result.reason_code == "no_verified_evidence"
    assert result.citations == ()
    assert "UNVERIFIED_DRAFT" not in json.dumps(model.payloads)
    assert model.reviews == [answer]


@pytest.mark.asyncio
async def test_missing_evidence_does_not_allow_fabricated_policy():
    model = FitModel(["Guaranteed refund.", "I cannot confirm the policy."], reject="Guaranteed refund")
    result = await run(model, evidence=False)
    assert result.content == "I cannot confirm the policy."
    assert result.reason_code == "no_verified_evidence"
