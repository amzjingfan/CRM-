"""通用政策草稿校验使用独立措辞，不能依赖冻结样本答案。"""

from importlib import import_module


def _validator():
    return import_module("app.agent.policy_draft_validation").validate_policy_draft


def _check(evidence: str | None, content: str | None, *, language: str = "en"):
    return _validator()(
        evidence=evidence,
        content=content,
        language=language,
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
