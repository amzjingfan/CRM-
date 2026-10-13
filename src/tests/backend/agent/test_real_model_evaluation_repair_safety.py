"""G4 修复请求只能使用本轮冻结数据的单次授权。"""

import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path

from _support import TESTS_ROOT

from app.agent import real_model_evaluation
from app.agent.real_model_evaluation import RealModelEvaluationOutput, load_verified_real_model_evaluation_dataset
from app.agent.security import PromptSafetyState, evaluate_prompt_safety

DATASET_PATH = TESTS_ROOT / "ai/datasets/real-model-v1.0.0.jsonl"
MANIFEST_PATH = Path(str(DATASET_PATH).replace(".jsonl", ".manifest.json"))


def _input():
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    case = dataset.cases[0]
    output = RealModelEvaluationOutput(
        decision="human_review",
        content="平台会在处理前审核申请。",
        language=case.target_language,
        reason_code="policy_grounded",
        business_claims=[],
    )
    return case, dataset, output


def _request(output: RealModelEvaluationOutput | None = None):
    case, dataset, default_output = _input()
    return real_model_evaluation.build_real_model_repair_request(
        case,
        dataset,
        output or default_output,
        ("POLICY_REVIEW_STEP_MISSING",),
        run_id=uuid.UUID("12345678-1234-4234-8234-123456789abc"),
    )


def test_repair_request_uses_narrow_payload_and_once_only_hash_grant() -> None:
    request = _request()
    payload = json.loads(request.user_prompt)
    assert request.prompt_safety_state == PromptSafetyState.ALLOWED
    assert request.is_repair is True
    assert request.temperature == 0.0
    assert payload["operation"] == "real_model_evaluation_repair"
    assert payload["reason_codes"] == ["POLICY_REVIEW_STEP_MISSING"]
    assert "sample_id" not in payload
    assert "dataset_version" not in payload
    assert "expected_decision" not in request.user_prompt
    assert "required_term_groups" not in request.user_prompt
    assert "forbidden_terms" not in request.user_prompt
    assert len(request.real_model_evaluation_context.allowed_repair_payload_hashes) == 1


def test_repair_payload_extra_answer_field_is_rejected() -> None:
    request = _request()
    payload = json.loads(request.user_prompt)
    payload["expected_decision"] = "human_review"
    tampered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    context = replace(
        request.real_model_evaluation_context,
        allowed_repair_payload_hashes=frozenset({hashlib.sha256(tampered.encode()).hexdigest()}),
    )
    decision = evaluate_prompt_safety(tampered, real_model_evaluation_context=context)
    assert decision.state == PromptSafetyState.UNCERTAIN


def test_repair_payload_wrong_source_is_rejected_even_with_own_hash() -> None:
    request = _request()
    payload = json.loads(request.user_prompt)
    payload["source_payload_sha256"] = "0" * 64
    tampered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    context = replace(
        request.real_model_evaluation_context,
        allowed_repair_payload_hashes=frozenset({hashlib.sha256(tampered.encode()).hexdigest()}),
    )
    decision = evaluate_prompt_safety(tampered, real_model_evaluation_context=context)
    assert decision.state == PromptSafetyState.UNCERTAIN


def test_repair_payload_with_secret_or_address_is_blocked() -> None:
    case, dataset, output = _input()
    for content in (
        "The token is Bearer secret-123456789abc.",
        "Send the parcel to 123 Main Street, Seattle, WA 98101.",
    ):
        unsafe_output = output.model_copy(update={"content": content})
        request = real_model_evaluation.build_real_model_repair_request(
            case,
            dataset,
            unsafe_output,
            ("POLICY_REVIEW_STEP_MISSING",),
            run_id=uuid.UUID("12345678-1234-4234-8234-123456789abc"),
        )
        assert request.prompt_safety_state == PromptSafetyState.BLOCKED


def test_original_dataset_context_cannot_authorize_repair_payload() -> None:
    _, dataset, _ = _input()
    request = _request()
    decision = evaluate_prompt_safety(request.user_prompt, real_model_evaluation_context=dataset.safety_context)
    assert decision.state == PromptSafetyState.UNCERTAIN


def test_repair_payload_with_personal_identifier_inside_claim_is_blocked() -> None:
    request = _request()
    payload = json.loads(request.user_prompt)
    payload["first_output"]["business_claims"] = [
        {
            "subject_type": "refund_policy",
            "subject_id": "buyer@example.com",
            "action": "explain_policy",
            "tense": "timeless",
            "polarity": "affirmed",
            "condition": "conditional",
            "evidence_type": payload["evidence_type"],
            "evidence_id": payload["evidence_id"],
            "confidence": 0.8,
        }
    ]
    tampered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    context = replace(
        request.real_model_evaluation_context,
        allowed_repair_payload_hashes=frozenset({hashlib.sha256(tampered.encode()).hexdigest()}),
    )
    decision = evaluate_prompt_safety(tampered, real_model_evaluation_context=context)
    assert decision.state == PromptSafetyState.BLOCKED
