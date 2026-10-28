"""根据本次可信政策证据检查草稿，独立于冻结评测答案。"""

import re
from dataclasses import dataclass
from typing import Literal

PolicyDisposition = Literal["pass", "repair", "block"]


@dataclass(frozen=True, slots=True)
class PolicyDraftValidation:
    """返回可复核的低敏原因码，不保留正文。"""

    disposition: PolicyDisposition
    reason_codes: tuple[str, ...]


_EN_REVIEW = re.compile(r"\b(?:review\w*|assess\w*|evaluat\w*)\b", re.IGNORECASE)
_ZH_REVIEW = re.compile(r"审核|审查|评估")
_EN_APPROVAL_CONDITION = re.compile(
    r"\b(?:only\s+if|if|only\s+after|after|upon|subject\s+to)\b.{0,90}\bapprov\w*\b"
    r"|\bapprov\w*\b.{0,50}\b(?:required|before|first)\b",
    re.IGNORECASE,
)
_ZH_APPROVAL_CONDITION = re.compile(
    r"(?:批准|获批|核准).{0,12}(?:后才|后方|之后才|才能)|(?:须|需|只有).{0,12}(?:批准|获批|核准)"
)
_EN_APPROVED_INSTANCE = re.compile(
    r"\b(?:has|have|had|was|were|already)\s+(?:been\s+)?approved\b|\b(?:request|application)\s+is\s+already\s+approved\b",
    re.IGNORECASE,
)
_ZH_APPROVED_INSTANCE = re.compile(r"(?:您的|你的|该)?(?:申请|请求).{0,12}(?:已获批|已批准|已经批准|获批了)")
_EN_CONFIRMED_CONDITIONAL = re.compile(
    r"\b(?:confirm|verify|affirm)s?\s+(?:this|the)\s+conditional\s+(?:workflow|rule)\b", re.IGNORECASE
)
_EN_NEGATED_CONFIRMATION = re.compile(
    r"\b(?:does\s+not|do\s+not|did\s+not|cannot|can't|never|fails?\s+to|unable\s+to)\s+"
    r"(?:confirm|verify|affirm)\w*\b",
    re.IGNORECASE,
)
_EN_PLATFORM_APPROVAL_CONDITION = re.compile(
    r"\b(?:only\s+if|if|only\s+after|after|upon|subject\s+to)\b.{0,90}"
    r"\b(?:platform|marketplace)\s+approv\w*\b",
    re.IGNORECASE,
)
_EN_NEGATED_INSTANCE_PREFIX = re.compile(r"\b(?:no|not|never|without)\b.{0,35}$", re.IGNORECASE)


def _has_review(text: str) -> bool:
    return bool(_EN_REVIEW.search(text) or _ZH_REVIEW.search(text))


def _has_approval_condition(text: str) -> bool:
    return bool(_EN_APPROVAL_CONDITION.search(text) or _ZH_APPROVAL_CONDITION.search(text))


def _asserts_instance_approved(text: str) -> bool:
    if _ZH_APPROVED_INSTANCE.search(text):
        return True
    return any(
        not _EN_NEGATED_INSTANCE_PREFIX.search(
            re.split(r"[.!?;]", text[max(0, match.start() - 40) : match.start()])[-1]
        )
        for match in _EN_APPROVED_INSTANCE.finditer(text)
    )


def _confirms_question_condition(evidence: str, customer_message: str | None) -> bool:
    """可信证据明确肯定指代条件时，才读取提问中的批准规则作上下文。"""
    return bool(
        customer_message
        and _EN_CONFIRMED_CONDITIONAL.search(evidence)
        and not _EN_NEGATED_CONFIRMATION.search(evidence)
        and _EN_PLATFORM_APPROVAL_CONDITION.search(customer_message)
    )


def validate_policy_draft(
    *,
    evidence: str | None,
    content: str | None,
    language: str,
    claim_evidence_type: str | None,
    claim_evidence_id: str | None,
    expected_evidence_type: str,
    expected_evidence_id: str | None,
    customer_message: str | None = None,
) -> PolicyDraftValidation:
    """识别政策条件缺失或无依据的批准措辞；不读取测试标签。"""
    if (claim_evidence_type, claim_evidence_id) != (expected_evidence_type, expected_evidence_id):
        return PolicyDraftValidation("block", ("POLICY_EVIDENCE_MISMATCH",))
    if not evidence or not content or language not in {"en", "zh-CN"}:
        return PolicyDraftValidation("block", ("POLICY_EVIDENCE_UNCERTAIN",))

    review_required = _has_review(evidence)
    referenced_approval_condition = expected_evidence_type == "faq_chunk" and _confirms_question_condition(
        evidence, customer_message
    )
    approval_required = _has_approval_condition(evidence) or referenced_approval_condition
    if not review_required and not approval_required:
        return PolicyDraftValidation("block", ("POLICY_EVIDENCE_UNCERTAIN",))

    reasons: list[str] = []
    if _asserts_instance_approved(content) and not _asserts_instance_approved(evidence):
        reasons.append("POLICY_UNSUPPORTED_APPROVAL_ASSERTION")
    if approval_required and (
        not _has_approval_condition(content)
        or (referenced_approval_condition and not _EN_PLATFORM_APPROVAL_CONDITION.search(content))
    ):
        reasons.append("POLICY_APPROVAL_CONDITION_MISSING")
    if review_required and not _has_review(content):
        reasons.append("POLICY_REVIEW_STEP_MISSING")
    return PolicyDraftValidation("repair", tuple(reasons)) if reasons else PolicyDraftValidation("pass", ())
