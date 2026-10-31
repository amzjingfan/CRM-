"""兜底话术只在同会话连续无业务答案时出现，故障不计入轮数。"""

import uuid
from types import SimpleNamespace

from app.agents.orchestration.fallback import (
    FIXED_FALLBACK,
    fixed_fallback_copy,
    is_third_unresolved_question,
    prior_question_reasons,
)


def test_third_unresolved_question_uses_fixed_copy_in_buyer_language() -> None:
    assert is_third_unresolved_question(("no_matching_agent", "answer_not_grounded"), "no_matching_agent")
    assert FIXED_FALLBACK["en"] == (
        "We have received your question. At present, there are too many inquiries and the agent is occupied.\n"
        "Please wait patiently. We will contact you as soon as possible. Thank you!"
    )
    assert FIXED_FALLBACK["zh-CN"] == (
        "我们已收到您的问题。目前咨询较多，人工客服正在忙碌。请耐心等待，我们会尽快与您联系。谢谢！"
    )
    assert fixed_fallback_copy("en-US") == ("en", FIXED_FALLBACK["en"])
    assert fixed_fallback_copy("zh-Hans") == ("zh-CN", FIXED_FALLBACK["zh-CN"])
    assert fixed_fallback_copy("es") is None


def test_fault_and_resolved_answer_do_not_count_towards_third_unresolved_question() -> None:
    assert not is_third_unresolved_question(("no_matching_agent", "deadline_exceeded"), "answer_not_grounded")
    assert not is_third_unresolved_question(("no_matching_agent", None), "answer_not_grounded")
    assert not is_third_unresolved_question(("no_matching_agent", "answer_not_grounded"), "aggregate_failed")


def test_prior_runs_are_scoped_to_distinct_buyer_messages_and_latest_result() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    runs = [
        SimpleNamespace(trigger_message_id=second, status="succeeded", error_code="answer_not_grounded"),
        SimpleNamespace(trigger_message_id=second, status="failed", error_code="deadline_exceeded"),
        SimpleNamespace(trigger_message_id=first, status="succeeded", error_code="no_matching_agent"),
    ]
    assert prior_question_reasons((first, second), runs) == ("no_matching_agent", "answer_not_grounded")
    assert prior_question_reasons((first, uuid.uuid4()), runs) == ("no_matching_agent", "missing_run")
