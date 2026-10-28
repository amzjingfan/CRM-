"""G4 合成评测失败的低敏定位提示。"""

import uuid
from dataclasses import replace

import pytest
from _support import TESTS_ROOT

from app.agents.core.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest
from app.agents.core.real_model_evaluation import (
    RealModelEvaluationCase,
    RealModelEvaluationOutput,
    diagnose_real_model_evaluation_output,
    grade_real_model_evaluation_output,
    load_verified_real_model_evaluation_dataset,
    run_real_model_evaluation,
)

REPO_ROOT = TESTS_ROOT.parents[1]
DATASET_PATH = REPO_ROOT / "release/evidence/ai/real-model-independent-v1.0.0.jsonl"
MANIFEST_PATH = REPO_ROOT / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json"


def _case(sample_id: str) -> RealModelEvaluationCase:
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    return next(case for case in dataset.cases if case.sample_id == sample_id)


def test_claim_diagnostic_names_only_the_mismatched_fields() -> None:
    case = _case("after-sales-open-001")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "十四天内可提交申请，是否受理以平台审核为准。",
            "language": "zh-CN",
            "reason_code": "policy_grounded",
            "business_claims": [
                {
                    "subject_type": "refund_policy",
                    "subject_id": None,
                    "action": "explain_policy",
                    "tense": "timeless",
                    "polarity": "uncertain",
                    "condition": "actual",
                    "evidence_type": "faq_chunk",
                    "evidence_id": str(case.evidence_id),
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    failures = grade_real_model_evaluation_output(case, output)
    diagnostic = diagnose_real_model_evaluation_output(case, output, failures)

    assert failures == ["BUSINESS_CLAIMS_MISMATCH"]
    assert diagnostic is not None
    assert diagnostic.claim_mismatch_fields == ["polarity", "condition"]
    assert diagnostic.forbidden_matches == []
    serialized = diagnostic.model_dump_json()
    assert "十四天" not in serialized
    assert str(case.evidence_id) not in serialized


def test_required_content_diagnostic_records_only_missing_frozen_group_indexes() -> None:
    case = _case("negation-open-001")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "没有结果。",
            "language": "zh-CN",
            "reason_code": "policy_grounded",
            "business_claims": [
                {
                    "subject_type": "non_business_artifact",
                    "subject_id": None,
                    "action": "display",
                    "tense": "timeless",
                    "polarity": "negated",
                    "condition": "actual",
                    "evidence_type": "faq_chunk",
                    "evidence_id": str(case.evidence_id),
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    failures = grade_real_model_evaluation_output(case, output)
    diagnostic = diagnose_real_model_evaluation_output(case, output, failures)

    assert failures == ["REQUIRED_CONTENT_MISSING"]
    assert diagnostic is not None
    assert diagnostic.missing_required_group_indexes == [1]
    serialized = diagnostic.model_dump_json()
    assert case.customer_message not in serialized
    assert str(case.evidence_id) not in serialized


def test_forbidden_diagnostic_is_a_hint_and_does_not_change_grading() -> None:
    case = _case("condition-open-002")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "The phrase “has been approved” must not be used; only if the platform approves.",
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
                    "evidence_id": str(case.evidence_id),
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    failures = grade_real_model_evaluation_output(case, output)
    diagnostic = diagnose_real_model_evaluation_output(case, output, failures)

    assert failures == ["FORBIDDEN_CONTENT_PRESENT"]
    assert diagnostic is not None
    assert diagnostic.claim_mismatch_fields == []
    assert len(diagnostic.forbidden_matches) == 1
    assert diagnostic.forbidden_matches[0].term_index == 0
    assert diagnostic.forbidden_matches[0].all_occurrences_inside_quotes is True
    assert diagnostic.forbidden_matches[0].all_occurrences_have_prohibition_cue is True
    assert "has been approved" not in diagnostic.model_dump_json()


def test_unquoted_promise_has_no_quotation_or_prohibition_hint() -> None:
    case = _case("condition-open-002")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "The request has been approved if the platform approves it.",
            "language": "en",
            "reason_code": "policy_grounded",
            "business_claims": [],
            "send_performed": False,
        }
    )

    failures = grade_real_model_evaluation_output(case, output)
    diagnostic = diagnose_real_model_evaluation_output(case, output, failures)

    assert "FORBIDDEN_CONTENT_PRESENT" in failures
    assert diagnostic is not None
    assert diagnostic.forbidden_matches[0].all_occurrences_inside_quotes is False
    assert diagnostic.forbidden_matches[0].all_occurrences_have_prohibition_cue is False


def test_mixed_forbidden_occurrences_do_not_get_a_safe_context_hint() -> None:
    case = _case("condition-open-002")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "Never say “has been approved”. " + "x" * 80 + " The request has been approved.",
            "language": "en",
            "reason_code": "policy_grounded",
            "business_claims": [],
            "send_performed": False,
        }
    )

    diagnostic = diagnose_real_model_evaluation_output(case, output, grade_real_model_evaluation_output(case, output))

    assert diagnostic is not None
    assert len(diagnostic.forbidden_matches) == 1
    assert diagnostic.forbidden_matches[0].all_occurrences_inside_quotes is False
    assert diagnostic.forbidden_matches[0].all_occurrences_have_prohibition_cue is False


@pytest.mark.asyncio
async def test_runner_retains_only_low_sensitive_diagnostics_for_failed_sample() -> None:
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    case = next(item for item in dataset.cases if item.sample_id == "condition-open-002")
    selected = replace(dataset, cases=(case,))
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "The phrase “has been approved” must not be used; only if the platform approves.",
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
                    "evidence_id": str(case.evidence_id),
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    report = await run_real_model_evaluation(
        selected,
        _FixedProvider(output),
        run_id=uuid.UUID("55555555-5555-4555-8555-555555555555"),
        app_env="staging",
    )

    sample = report.samples[0]
    assert sample.first_failure_reason == "FORBIDDEN_CONTENT_PRESENT"
    assert sample.first_diagnostics is not None
    assert sample.first_diagnostics.forbidden_matches[0].term_index == 0
    assert sample.decision == "transfer_human"
    serialized = report.model_dump_json()
    assert "has been approved" not in serialized
    assert case.customer_message not in serialized


@pytest.mark.asyncio
async def test_runner_accepts_policy_condition_attested_by_synthetic_evidence() -> None:
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    case = _case("condition-open-002")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "Processing begins only if the platform approves the request.",
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
                    "evidence_id": str(case.evidence_id),
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    report = await run_real_model_evaluation(
        replace(dataset, cases=(case,)),
        _FixedProvider(output),
        run_id=uuid.UUID("77777777-7777-4777-8777-777777777777"),
        app_env="staging",
    )

    sample = report.samples[0]
    assert sample.policy_reason_codes == []
    assert sample.repair_outcome == "not_needed"
    assert sample.failure_reason is None
    assert sample.passed is True


class _FixedProvider(LLMProvider):
    provider_name = "test"
    model_name = "deepseek-v4-flash"

    def __init__(self, output: RealModelEvaluationOutput) -> None:
        self.output = output

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=response_schema.model_validate(self.output.model_dump()),
            input_tokens=10,
            output_tokens=10,
            latency_ms=100,
            provider_request_id=None,
        )
