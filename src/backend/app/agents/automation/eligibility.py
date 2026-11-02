"""将已独立复核的正式结果固化为资格；内部建议仍保持 human_review。"""

import hashlib

from app.agents.orchestration.fallback import fixed_fallback_copy
from app.agents.orchestration.service import DynamicRunResult
from app.agents.runtime.state import RunPhase


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def review_eligibility(result: DynamicRunResult) -> dict[str, object]:
    # REVIEW_READY 只由最终证据/隐私独立复核通过路径产生；错误草稿不能凭正文获批。
    eligible = bool(
        result.phase == RunPhase.REVIEW_READY
        and result.reason_code is None
        and result.suggestion.reason_code is None
        and result.specialists
        and all(item.answer is not None and item.reason_code is None for item in result.specialists)
        and result.suggestion.content
    )
    fixed = fixed_fallback_copy(result.suggestion.reply_language)
    fixed_approved = bool(
        result.phase == RunPhase.REVIEW_REQUIRED
        and result.reason_code == result.suggestion.reason_code == "fallback_third_round"
        and fixed is not None
        and result.suggestion.content == fixed[1]
        and not result.suggestion.reply_parts
        and result.specialists
        and {"create_handoff_request", "add_internal_note"} <= set(result.specialists[-1].successful_tools)
        and result.specialists[-1].reason_code is None
    )
    eligible = eligible or fixed_approved
    parts = result.suggestion.reply_parts or ((result.suggestion.content,) if result.suggestion.content else ())
    return {
        "eligible": eligible,
        "review_basis": "fixed_fallback" if fixed_approved else "independent_review",
        "reply_language": result.suggestion.reply_language,
        "review_phase": result.phase.value,
        "reason_code": result.reason_code or result.suggestion.reason_code,
        "content_hashes": [content_hash(item) for item in parts],
        "review_version": "independent-evidence-privacy-v1",
    }
