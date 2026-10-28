"""通用政策草稿校验使用独立措辞，不能依赖冻结样本答案。"""

from importlib import import_module


def _validator():
    return import_module("app.agents.core.policy_draft_validation").validate_policy_draft


def _check(
    evidence: str | None,
    content: str | None,
    *,
    language: str = "en",
    customer_message: str | None = None,
):
    return _validator()(
        evidence=evidence,
        content=content,
        language=language,
        customer_message=customer_message,
        claim_evidence_type="faq_chunk",
        claim_evidence_id="evidence-1",
        expected_evidence_type="faq_chunk",
        expected_evidence_id="evidence-1",
    )


def test_english_policy_preserves_approval_condition_and_review() -> None:
    result = _check(
        "Processing starts only if the marketplace approves a request; each case is subject to platform review.",
        "The marketplace reviews each request. Processing starts only after platform approval.",
    )
    assert result.disposition == "pass"
    assert result.reason_codes == ()


def test_english_policy_missing_review_is_repairable() -> None:
    result = _check(
        "A request may be filed within twelve days, subject to platform review.",
        "You may file the request within twelve days.",
    )
    assert result.disposition == "repair"
    assert result.reason_codes == ("POLICY_REVIEW_STEP_MISSING",)


def test_english_policy_unsupported_approval_is_repairable_before_exposure() -> None:
    result = _check(
        "Processing begins only if the marketplace approves the request.",
        "Your request has been approved and processing will begin.",
    )
    assert result.disposition == "repair"
    assert "POLICY_UNSUPPORTED_APPROVAL_ASSERTION" in result.reason_codes


def test_chinese_policy_missing_condition_is_repairable() -> None:
    result = _check("平台审核批准后才开始处理申请。", "您可提交申请，由平台审核。", language="zh-CN")
    assert result.disposition == "repair"
    assert "POLICY_APPROVAL_CONDITION_MISSING" in result.reason_codes


def test_policy_evidence_reference_mismatch_blocks() -> None:
    result = _validator()(
        evidence="The marketplace reviews each request.",
        content="The marketplace reviews each request.",
        language="en",
        claim_evidence_type="faq_chunk",
        claim_evidence_id="foreign-evidence",
        expected_evidence_type="faq_chunk",
        expected_evidence_id="evidence-1",
    )
    assert result.disposition == "block"
    assert result.reason_codes == ("POLICY_EVIDENCE_MISMATCH",)


def test_policy_missing_or_unrecognized_evidence_blocks() -> None:
    assert _check(None, "The marketplace will review your request.").disposition == "block"
    assert _check("There is an unrelated informational page.", "There is an informational page.").disposition == "block"


def test_policy_accepts_review_paraphrase_without_frozen_keywords() -> None:
    result = _check(
        "Each return request receives a marketplace assessment before the next step.",
        "The marketplace assesses each return request first.",
    )
    assert result.disposition == "pass"


def test_confirmed_conditional_workflow_uses_the_question_as_context_not_as_evidence() -> None:
    result = _check(
        "Synthetic policy confirms this conditional workflow; it does not show that any request was approved.",
        "Processing begins only if the platform approves a request.",
        customer_message="Explain the rule: processing begins only if the platform approves the request.",
    )
    assert result.disposition == "pass"


def test_conditional_coreference_requires_positive_attestation_and_a_matching_condition() -> None:
    question = "Explain the rule: processing begins only if the platform approves the request."
    content = "Processing begins only if the platform approves a request."
    assert (
        _check("This page does not confirm this conditional workflow.", content, customer_message=question).disposition
        == "block"
    )
    assert _check("This page confirms this conditional workflow.", content).disposition == "block"
    assert (
        _check(
            "This page confirms this conditional workflow.", content, customer_message="What is the status?"
        ).disposition
        == "block"
    )
    assert _check("Unrelated page.", content, customer_message=question).disposition == "block"
    customer_approval = _check(
        "This page confirms this conditional workflow.",
        "Processing begins if the customer approves.",
        customer_message=question,
    )
    assert customer_approval.disposition == "repair"
    assert "POLICY_APPROVAL_CONDITION_MISSING" in customer_approval.reason_codes
    unsupported = _check(
        "This page confirms this conditional workflow; no request was approved.",
        "Your request has been approved.",
        customer_message=question,
    )
    assert unsupported.disposition == "repair"
    assert "POLICY_UNSUPPORTED_APPROVAL_ASSERTION" in unsupported.reason_codes


def test_later_negation_does_not_cancel_an_earlier_approval_assertion() -> None:
    result = _check(
        "This page confirms this conditional workflow; no request was approved.",
        'The phrase "has been approved" must not be used; processing begins only if the platform approves.',
        customer_message="Processing begins only if the platform approves a request.",
    )
    assert result.disposition == "repair"
    assert "POLICY_UNSUPPORTED_APPROVAL_ASSERTION" in result.reason_codes


def test_unrelated_prior_negation_does_not_cancel_a_later_approval_assertion() -> None:
    result = _check(
        "This page confirms this conditional workflow; no request was approved.",
        "No action is needed. Your request was approved. Processing begins only if the platform approves.",
        customer_message="Processing begins only if the platform approves a request.",
    )
    assert result.disposition == "repair"
    assert "POLICY_UNSUPPORTED_APPROVAL_ASSERTION" in result.reason_codes


def test_negated_conditional_attestation_is_not_trusted() -> None:
    result = _check(
        "This page never confirms this conditional workflow.",
        "Processing begins only if the platform approves.",
        customer_message="Processing begins only if the platform approves a request.",
    )
    assert result.disposition == "block"
