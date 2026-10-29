"""模型按上下文识别敏感片段，程序只原位脱敏而不改写业务事实。"""

import json
import time
import uuid

import pytest

from app.agents.orchestration.aggregator import aggregate_results
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.providers.tool_calling import FunctionCall, ToolTurn


class PrivacyReviewModel:
    def __init__(self, answer: str, redactions: list[str], *, reviewed: bool = True) -> None:
        self.answer, self.redactions, self.reviewed = answer, redactions, reviewed
        self.review_payload = None

    async def complete(self, *, messages, tools, max_output_tokens):
        if not tools:
            return ToolTurn(self.answer, (), {"role": "assistant", "content": self.answer}, 3, 2)
        self.review_payload = json.loads(messages[-1]["content"])
        redactions = []
        for value in self.redactions:
            segment = next((item for item in self.review_payload["answer_segments"] if value in item["text"]), None)
            redactions.append({"segment_id": segment["id"] if segment else "missing", "text": value})
        arguments = {
            "supported": True,
            "evidence_ids": list(self.review_payload["evidence"]),
            "reason_code": "supported",
            "redactions": redactions,
        }
        if self.reviewed:
            arguments["privacy_reviewed"] = True
        return ToolTurn(
            None,
            (FunctionCall("review", "review_answer_evidence", arguments),),
            {"role": "assistant", "content": None},
            5,
            4,
        )


async def aggregate(model, **kwargs):
    return await aggregate_results(
        question="请详细说明订单和物流",
        results=(
            SpecialistResult(
                uuid.uuid4(),
                model.answer,
                verified_facts={"query_order.status": "shipped", "query_logistics.status": "in_transit"},
                successful_tools=("query_order", "query_logistics"),
            ),
        ),
        provider=model,
        deadline=time.monotonic() + 3,
        store_id=uuid.uuid4(),
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("label", ["订单号", "物流单号", "运单号", "商品型号", "包裹编号", "物流渠道"])
async def test_model_accepted_business_labels_and_times_remain_verbatim(label) -> None:
    text = f"商品：测试衬衫。数量：1。{label}：已隐藏。下单时间：2026-10-01T12:00:00+00:00。"
    model = PrivacyReviewModel(text, [])
    result = await aggregate(model)
    assert result.content == text
    assert result.reason_code is None
    assert model.review_payload["answer"] == text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sensitive",
    ["buyer@example.com", "13800138000", "123 Main Street, New York, NY 10001", "甲乙丙隐私测试串"],
)
async def test_only_model_identified_private_span_is_hidden(sensitive) -> None:
    text = f"包裹目前运输中。核对资料：{sensitive}。请继续查看配送轨迹。"
    model = PrivacyReviewModel(text, [sensitive])
    result = await aggregate(model)
    assert result.content == text.replace(sensitive, "【敏感信息已隐藏】")
    assert result.reason_code is None
    assert result.action == "human_review"


@pytest.mark.asyncio
async def test_nonexistent_redaction_cannot_rewrite_or_approve_the_answer() -> None:
    result = await aggregate(PrivacyReviewModel("包裹目前运输中。", ["订单已退款"]))
    assert result.content is None
    assert result.reason_code == "answer_not_grounded"


@pytest.mark.asyncio
async def test_missing_privacy_review_does_not_silently_approve_raw_text() -> None:
    result = await aggregate(PrivacyReviewModel("包裹目前运输中。", [], reviewed=False))
    assert result.content is None
    assert result.reason_code == "answer_not_grounded"


@pytest.mark.asyncio
async def test_published_compliance_policy_reaches_the_semantic_reviewer() -> None:
    model = PrivacyReviewModel("包裹目前运输中。", [])
    result = await aggregate(model, privacy_policies=("仅隐藏个人识别资料，保留订单业务状态。",))
    assert result.content == model.answer
    assert model.review_payload["published_privacy_policies"] == ["仅隐藏个人识别资料，保留订单业务状态。"]
    assert model.review_payload["allowed_evidence_ids"] == list(model.review_payload["evidence"])
    assert set(model.review_payload["evidence"]) == {"e1", "e2"}


@pytest.mark.asyncio
async def test_imprecise_redaction_hides_only_identified_segment_and_retains_business_answer() -> None:
    class ImpreciseModel(PrivacyReviewModel):
        async def complete(self, *, messages, tools, max_output_tokens):
            turn = await super().complete(messages=messages, tools=tools, max_output_tokens=max_output_tokens)
            if tools:
                segment = next(item for item in self.review_payload["answer_segments"] if "核对资料" in item["text"])
                turn.calls[0].arguments["redactions"] = [{"segment_id": segment["id"], "text": "模型错写的片段"}]
            return turn

    model = ImpreciseModel("包裹目前运输中。核对资料：buyer@example.com。请继续查看配送轨迹。", [])
    result = await aggregate(model)
    assert result.content == "包裹目前运输中。【敏感信息已隐藏】请继续查看配送轨迹。"
    assert result.reason_code is None


@pytest.mark.asyncio
async def test_identified_private_value_is_hidden_in_every_occurrence() -> None:
    model = PrivacyReviewModel(
        "包裹目前运输中。联系方式buyer@example.com。备用联系buyer@example.com。", ["buyer@example.com"]
    )
    result = await aggregate(model)
    assert result.content == model.answer.replace("buyer@example.com", "【敏感信息已隐藏】")


@pytest.mark.asyncio
async def test_overlapping_private_spans_are_merged_without_leaving_a_partial_identifier() -> None:
    model = PrivacyReviewModel("包裹目前运输中。核对资料buyer@example.com。", ["buyer@example.com", "example.com"])
    result = await aggregate(model)
    assert result.content == "包裹目前运输中。核对资料【敏感信息已隐藏】。"
