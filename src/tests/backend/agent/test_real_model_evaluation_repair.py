"""G4 双阶段评测必须保存首轮事实、限制修复且失败关闭。"""

import json
import uuid
from dataclasses import replace
from pathlib import Path
from typing import TypeVar

import pytest
from _support import TESTS_ROOT

from app.agent.errors import LLMErrorCode, LLMProviderError
from app.agent.providers.base import LLMProvider, ProviderResult, StructuredRequest
from app.agent.real_model_evaluation import (
    RealModelEvaluationOutput,
    RealModelSampleResult,
    load_verified_real_model_evaluation_dataset,
    run_real_model_evaluation,
)
from app.agent.security import PromptSafetyState, evaluate_real_model_draft_safety

OutputT = TypeVar("OutputT", bound=RealModelEvaluationOutput)
DATASET_PATH = TESTS_ROOT / "ai/datasets/real-model-v1.0.0.jsonl"
MANIFEST_PATH = Path(str(DATASET_PATH).replace(".jsonl", ".manifest.json"))


def _dataset(sample_id: str = "multilingual-policy-001"):
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    case = next(item for item in dataset.cases if item.sample_id == sample_id)
    return replace(dataset, cases=(case,))


def _policy_output(content: str) -> RealModelEvaluationOutput:
    return RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": content,
            "language": "en",
            "reason_code": "policy_grounded",
            "business_claims": [
                {
                    "subject_type": "refund_policy",
                    "subject_id": None,
                    "action": "explain_policy",
                    "tense": "timeless",
                    "polarity": "affirmed",
                    "condition": "conditional",
                    "evidence_type": "faq_chunk",
                    "evidence_id": "10000000-0000-4000-8000-000000000012",
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )


class _SequenceProvider(LLMProvider):
    provider_name = "test"
    model_name = "deepseek-v4-flash"

    def __init__(self, outputs: list[RealModelEvaluationOutput | LLMProviderError], *, tokens: int = 20) -> None:
        self.outputs = outputs
        self.tokens = tokens
        self.requests: list[StructuredRequest] = []

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        request.ensure_safe_for_external_provider(response_schema_name=response_schema.__name__)
        self.requests.append(request)
        output = self.outputs.pop(0)
        if isinstance(output, LLMProviderError):
            raise output
        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=response_schema.model_validate(output.model_dump()),
            input_tokens=self.tokens,
            output_tokens=5,
            latency_ms=100,
            provider_request_id=None,
        )


async def _run(provider: _SequenceProvider, *, max_provider_calls: int = 68, max_total_tokens: int = 120000):
    return await run_real_model_evaluation(
        _dataset(),
        provider,
        run_id=uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        app_env="development",
        max_provider_calls=max_provider_calls,
        max_total_tokens=max_total_tokens,
    )


@pytest.mark.asyncio
async def test_first_pass_skips_repair_and_keeps_first_score() -> None:
    provider = _SequenceProvider(
        [_policy_output("A return request may be submitted within seven days, subject to platform review.")]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 1
    assert sample.first_passed is True
    assert sample.passed is True
    assert sample.repair_attempted is False
    assert sample.provider_call_count == 1
    assert report.evaluation_flow_version == "policy-repair-dlp-regeneration-v1"
    assert report.first_output_semantics == "first_schema_validated_output"


@pytest.mark.asyncio
async def test_repair_success_keeps_first_failure_and_final_pass_separate() -> None:
    provider = _SequenceProvider(
        [
            _policy_output("You may submit a return request within seven days."),
            _policy_output("A return request may be submitted within seven days, subject to platform review."),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 2
    assert provider.requests[1].is_repair is True
    assert sample.first_passed is False
    assert "REQUIRED_CONTENT_MISSING" in sample.first_failure_reason
    assert sample.passed is True
    assert sample.repair_attempted is True
    assert sample.repair_outcome == "succeeded"
    assert sample.first_output_hash != sample.output_hash
    assert sample.provider_call_count == 2
    assert sample.token_usage.total_tokens == 50
    assert report.metrics.first_passed_sample_count == 0
    assert report.metrics.repair_attempt_count == 1
    assert report.metrics.repair_final_pass_count == 1
    assert report.metrics.provider_call_count == 2
    serialized = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    assert "You may submit a return" not in serialized
    assert "A return request may" not in serialized


@pytest.mark.asyncio
async def test_unsafe_second_draft_fails_closed() -> None:
    provider = _SequenceProvider(
        [
            _policy_output("You may submit a return request within seven days."),
            _policy_output("Your request has been approved."),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 2
    assert sample.first_passed is False
    assert sample.decision == "transfer_human"
    assert sample.passed is False
    assert sample.repair_outcome == "failed"
    assert sample.second_attempt_disposition == "policy_rejected"
    assert sample.provider_call_count == 2


@pytest.mark.asyncio
async def test_repaired_draft_with_personal_email_fails_closed() -> None:
    provider = _SequenceProvider(
        [
            _policy_output("You may submit a return request within seven days."),
            _policy_output("A return request is subject to platform review. Contact buyer@example.com."),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 2
    assert sample.decision == "transfer_human"
    assert sample.repair_outcome == "failed"
    assert sample.second_attempt_disposition == "dlp_rejected"
    assert "buyer@example.com" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_first_draft_with_personal_email_never_enters_repair() -> None:
    provider = _SequenceProvider([_policy_output("Contact buyer@example.com for platform review.")])
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 1
    assert sample.decision == "transfer_human"
    assert sample.repair_attempted is False
    assert sample.policy_reason_codes == ["DRAFT_DLP_BLOCKED_EMAIL"]
    assert "buyer@example.com" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_uncertain_separators_regenerate_without_rejected_draft() -> None:
    rejected = "A return request, platform review, next step"
    provider = _SequenceProvider(
        [
            _policy_output(rejected),
            _policy_output("A return request is subject to platform review."),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 2
    assert provider.requests[1].is_repair is True
    assert provider.requests[1].prompt_safety_state == PromptSafetyState.ALLOWED
    assert provider.requests[1].user_prompt == provider.requests[0].user_prompt
    assert "content 不得包含逗号或地址分隔符" in provider.requests[1].system_prompt
    assert "不修改其他 JSON 字段的证据含义" in provider.requests[1].system_prompt
    assert rejected not in provider.requests[1].user_prompt
    assert rejected not in provider.requests[1].system_prompt
    assert sample.regeneration_attempted is True
    assert sample.regeneration_outcome == "succeeded"
    assert sample.second_attempt_disposition == "accepted"
    assert sample.repair_attempted is False
    assert sample.provider_call_count == 2
    assert sample.passed is True
    assert report.metrics.regeneration_attempt_count == 1
    assert report.metrics.regeneration_final_pass_count == 1
    assert rejected not in report.model_dump_json()


@pytest.mark.asyncio
async def test_regenerated_uncertain_draft_still_fails_closed() -> None:
    provider = _SequenceProvider(
        [
            _policy_output("A return request, platform review, next step"),
            _policy_output("A request, buyer address, 123 Main Street"),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 2
    assert sample.decision == "transfer_human"
    assert sample.regeneration_outcome == "failed"
    assert sample.second_attempt_disposition == "dlp_rejected"
    assert sample.provider_call_count == 2
    assert "123 Main Street" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_regenerated_model_transfer_is_distinct_from_dlp_rejection() -> None:
    transfer = RealModelEvaluationOutput.model_validate(
        {
            "decision": "transfer_human",
            "content": None,
            "language": "en",
            "reason_code": "insufficient_evidence",
            "business_claims": [],
            "send_performed": False,
        }
    )
    provider = _SequenceProvider([_policy_output("A return request, platform review, next step"), transfer])
    report = await _run(provider)
    sample = report.samples[0]
    assert sample.regeneration_outcome == "failed"
    assert sample.second_attempt_disposition == "model_transfer"
    assert sample.policy_reason_codes == ["DRAFT_DLP_UNCERTAIN_LOCATION_SEPARATORS"]
    assert sample.decision == "transfer_human"


@pytest.mark.asyncio
async def test_regeneration_never_relays_explicit_address_or_uses_third_call() -> None:
    provider = _SequenceProvider([_policy_output("Send to 123 Main Street, Seattle, WA 98101")])
    report = await _run(provider)
    assert len(provider.requests) == 1
    assert report.samples[0].regeneration_attempted is False
    assert report.samples[0].decision == "transfer_human"

    provider = _SequenceProvider(
        [
            _policy_output("A return request, platform review, next step"),
            _policy_output("You may submit a return request within seven days."),
        ]
    )
    report = await _run(provider)
    assert len(provider.requests) == 2
    assert report.samples[0].regeneration_attempted is True
    assert report.samples[0].decision == "transfer_human"
    assert report.samples[0].provider_call_count == 2


@pytest.mark.asyncio
async def test_regeneration_respects_call_budget_and_provider_failure() -> None:
    uncertain = _policy_output("A return request, platform review, next step")
    provider = _SequenceProvider([uncertain])
    report = await _run(provider, max_provider_calls=1)
    sample = report.samples[0]
    assert len(provider.requests) == 1
    assert sample.regeneration_attempted is False
    assert sample.regeneration_outcome == "budget_exhausted"
    assert sample.decision == "transfer_human"

    provider = _SequenceProvider([uncertain, LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "timeout", retriable=True)])
    report = await _run(provider)
    sample = report.samples[0]
    assert len(provider.requests) == 2
    assert sample.regeneration_attempted is True
    assert sample.regeneration_outcome == "provider_failed"
    assert sample.second_attempt_disposition == "provider_failed"
    assert sample.provider_failure is True
    assert sample.decision == "transfer_human"
    assert report.metrics.provider_failure_count == 1


def test_draft_dlp_reports_only_detector_class() -> None:
    cases = (
        ("Contact buyer@example.com", "DRAFT_DLP_BLOCKED_EMAIL"),
        ("Call +1 415 555 0123", "DRAFT_DLP_BLOCKED_PHONE"),
        ("Order ABCD-12345678", "DRAFT_DLP_BLOCKED_IDENTIFIER"),
        ("Bearer abcdefgh12345678", "DRAFT_DLP_BLOCKED_SECRET"),
    )
    for content, expected_reason in cases:
        decision = evaluate_real_model_draft_safety(content, [])
        assert decision.state == PromptSafetyState.BLOCKED
        assert decision.reason_code == expected_reason
        assert content not in decision.reason_code


@pytest.mark.parametrize(
    ("content", "expected_reason"),
    (
        ("warehouse 12, floor 2", "DRAFT_DLP_UNCERTAIN_BUSINESS_LOCATION"),
        ("The street and building information is not shown.", "DRAFT_DLP_UNCERTAIN_LOCATION_TERMS"),
        ("مرحبا 12", "DRAFT_DLP_UNCERTAIN_LOCATION_SCRIPT"),
        ("Alpha, beta, gamma", "DRAFT_DLP_UNCERTAIN_LOCATION_SEPARATORS"),
        ("stage 1, step 2", "DRAFT_DLP_UNCERTAIN_LOCATION_NUMBERS"),
    ),
)
def test_draft_location_uncertainty_reports_only_fixed_shape(content: str, expected_reason: str) -> None:
    decision = evaluate_real_model_draft_safety(content, [])
    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.reason_code == expected_reason
    assert content not in decision.reason_code


def test_policy_punctuation_and_mixed_address_keep_fail_closed_boundary() -> None:
    # 两个普通逗号目前仍属不确定，不能为了通过政策样本而放宽地址边界。
    policy_with_commas = "只有平台审核同意后，退款申请才进入下一步，当前结果仍待平台确认。"
    policy_with_sentences = "只有平台审核同意后退款申请才进入下一步。当前结果仍待平台确认。"
    mixed_address = "退款申请须审核。Send to Main Street, Seattle, Washington."

    assert evaluate_real_model_draft_safety(policy_with_commas, []).state == PromptSafetyState.UNCERTAIN
    assert evaluate_real_model_draft_safety(policy_with_sentences, []).state == PromptSafetyState.ALLOWED
    assert evaluate_real_model_draft_safety(mixed_address, []).state == PromptSafetyState.BLOCKED


@pytest.mark.asyncio
async def test_policy_repair_can_succeed_without_final_frozen_quality_pass() -> None:
    provider = _SequenceProvider(
        [
            _policy_output("You may submit a return request within seven days."),
            _policy_output("The marketplace reviews requests."),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert sample.repair_outcome == "succeeded"
    assert sample.passed is False
    assert report.metrics.repair_success_count == 1
    assert report.metrics.repair_final_pass_count == 0


@pytest.mark.asyncio
async def test_repair_transfer_human_is_not_counted_as_success() -> None:
    transfer = RealModelEvaluationOutput.model_validate(
        {
            "decision": "transfer_human",
            "content": None,
            "language": "en",
            "reason_code": "insufficient_evidence",
            "business_claims": [],
            "send_performed": False,
        }
    )
    provider = _SequenceProvider([_policy_output("You may submit a return request within seven days."), transfer])
    report = await _run(provider)
    sample = report.samples[0]
    assert sample.decision == "transfer_human"
    assert sample.repair_outcome == "failed"
    assert sample.second_attempt_disposition == "model_transfer"
    assert "POLICY_REPAIR_NO_DRAFT" in sample.policy_reason_codes
    assert report.metrics.repair_success_count == 0
    assert report.metrics.repair_final_pass_count == 0


@pytest.mark.asyncio
async def test_repair_provider_timeout_fails_closed_and_counts_failure() -> None:
    provider = _SequenceProvider(
        [
            _policy_output("You may submit a return request within seven days."),
            LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "timeout", retriable=True),
        ]
    )
    report = await _run(provider)
    sample = report.samples[0]
    assert sample.decision == "transfer_human"
    assert sample.provider_failure is True
    assert sample.second_attempt_disposition == "provider_failed"
    assert sample.first_passed is False
    assert sample.provider_call_count == 2
    assert report.metrics.provider_failure_count == 1


@pytest.mark.asyncio
async def test_call_and_token_budgets_stop_before_repair() -> None:
    for call_limit, token_limit in ((1, 120000), (68, 25)):
        provider = _SequenceProvider([_policy_output("You may submit a return request within seven days.")])
        report = await _run(provider, max_provider_calls=call_limit, max_total_tokens=token_limit)
        sample = report.samples[0]
        assert len(provider.requests) == 1
        assert sample.decision == "transfer_human"
        assert sample.repair_outcome == "budget_exhausted"
        assert sample.provider_call_count == 1


@pytest.mark.asyncio
async def test_token_budget_cannot_exceed_reviewed_ceiling() -> None:
    provider = _SequenceProvider([])
    with pytest.raises(ValueError, match="预算无效"):
        await _run(provider, max_total_tokens=120001)
    assert provider.requests == []


@pytest.mark.asyncio
async def test_injected_timeout_never_calls_provider() -> None:
    provider = _SequenceProvider([])
    report = await run_real_model_evaluation(
        _dataset("model-timeout-001"),
        provider,
        run_id=uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        app_env="development",
    )
    assert provider.requests == []
    assert report.samples[0].injected_failure is True
    assert report.samples[0].provider_call_count == 0


def test_legacy_sample_has_no_invented_repair_evidence() -> None:
    old = RealModelSampleResult.model_validate(
        {
            "model": "old-model",
            "prompt_version": "real-model-eval-v1.2.7",
            "policy_version": "prompt-dlp-v1.3.0",
            "dataset_version": "real-model-v1.0.0",
            "run_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "sample_id": "old-case",
            "category": "condition",
            "risk_level": "normal",
            "expected_decision": "human_review",
            "decision": "human_review",
            "input_hash": "a" * 64,
            "output_hash": "b" * 64,
            "failure_reason": None,
            "first_output_latency_ms": 100,
            "total_latency_ms": 100,
            "token_usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
            "passed": True,
            "provider_failure": False,
            "injected_failure": False,
        }
    )
    assert old.first_passed is None
    assert old.first_output_hash is None
    assert old.second_attempt_disposition == "not_attempted"
    assert old.repair_outcome == "not_enabled"
