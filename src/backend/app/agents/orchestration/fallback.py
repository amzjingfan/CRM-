"""会话内连续无解的确定性计数和买家语言固定安抚话术。"""

import uuid
from collections.abc import Sequence
from typing import Protocol

UNRESOLVED_REASONS = frozenset(
    {
        "no_matching_agent",
        "answer_not_grounded",
        "insufficient_evidence",
        "no_verified_evidence",
        "fallback_third_round",
    }
)

FIXED_FALLBACK = {
    "en": (
        "We have received your question. At present, there are too many inquiries and the agent is occupied.\n"
        "Please wait patiently. We will contact you as soon as possible. Thank you!"
    ),
    "zh-CN": "我们已收到您的问题。目前咨询较多，人工客服正在忙碌。请耐心等待，我们会尽快与您联系。谢谢！",
}


def fixed_fallback_copy(language: str | None) -> tuple[str, str] | None:
    """只为已支持的买家语种提供固定文案；地区标签不改变内容。"""
    normalized = (language or "").lower()
    if normalized == "en" or normalized.startswith("en-"):
        return "en", FIXED_FALLBACK["en"]
    if normalized in {"zh-cn", "zh-hans", "zh-hans-cn"}:
        return "zh-CN", FIXED_FALLBACK["zh-CN"]
    return None


def is_third_unresolved_question(previous: Sequence[str | None], current: str | None) -> bool:
    """只接受连续三个已完成的无解业务回合；超时和工具故障不冒充无解。"""
    return len(previous) >= 2 and all(reason in UNRESOLVED_REASONS for reason in (*previous[-2:], current))


class QuestionRun(Protocol):
    trigger_message_id: uuid.UUID | None
    status: str
    error_code: str | None


def prior_question_reasons(
    message_ids: Sequence[uuid.UUID], newest_first: Sequence[QuestionRun]
) -> tuple[str | None, ...]:
    """同一消息重试只看最新正式运行；缺失、故障均不能推进兜底计数。"""
    latest: dict[uuid.UUID, QuestionRun] = {}
    for prior_run in newest_first:
        if prior_run.trigger_message_id is not None:
            latest.setdefault(prior_run.trigger_message_id, prior_run)
    outcomes: list[str | None] = []
    for message_id in message_ids:
        run = latest.get(message_id)
        if run is None:
            outcomes.append("missing_run")
        elif run.status != "succeeded":
            outcomes.append("run_failed")
        else:
            outcomes.append(run.error_code)
    return tuple(outcomes)
