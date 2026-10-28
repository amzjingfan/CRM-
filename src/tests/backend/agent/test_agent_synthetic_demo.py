"""AI 合成数据手动演示的边界测试。"""

import json

import pytest
from pydantic import ValidationError

from app.agents.core.security import (
    SYNTHETIC_DEMO_SCENARIOS,
    SYNTHETIC_DEMO_SYSTEM_PROMPT,
    PromptSafetyState,
    build_synthetic_demo_payload,
    evaluate_prompt_safety,
    evaluate_system_prompt_safety,
)
from app.agents.core.synthetic_demo import resolve_synthetic_demo_scenario
from app.shared.config.settings import Settings


def test_fixed_synthetic_demo_envelope_is_allowed() -> None:
    """只有服务端固定的合成场景和系统 Prompt 可以触达真实 Provider。"""
    user_decision = evaluate_prompt_safety(build_synthetic_demo_payload("logistics"))
    system_decision = evaluate_system_prompt_safety(SYNTHETIC_DEMO_SYSTEM_PROMPT)

    assert user_decision.state == PromptSafetyState.ALLOWED
    assert user_decision.reason_code == "TRUSTED_SYNTHETIC_DEMO_PAYLOAD_ALLOWED"
    assert system_decision.state == PromptSafetyState.ALLOWED


def test_mutated_synthetic_demo_payload_fails_closed() -> None:
    """增加字段或替换正文后不能借演示标识绕过客户文本安全门禁。"""
    payload = json.loads(build_synthetic_demo_payload("general"))
    payload["customer_message"] = "真实客户提交的任意正文"

    decision = evaluate_prompt_safety(json.dumps(payload, ensure_ascii=False))

    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.reason_code == "UNTRUSTED_STRUCTURED_DATA_REQUIRES_DLP"


def test_demo_conversation_requires_exact_seeded_message() -> None:
    """会话 ID 和固定正文必须同时匹配，避免员工修改消息后继续走演示白名单。"""
    message = SYNTHETIC_DEMO_SCENARIOS["return-policy"]["customer_message"]

    assert resolve_synthetic_demo_scenario("ai-demo-return-policy", message) == "return-policy"
    assert resolve_synthetic_demo_scenario("ai-demo-return-policy", f"{message} 追加内容") is None
    assert resolve_synthetic_demo_scenario("real-conversation", message) is None


def test_synthetic_demo_cannot_start_in_production() -> None:
    """即使配置了 LLM，生产环境也不能启用合成演示旁路。"""
    with pytest.raises(ValidationError, match="AI 合成演示只允许"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET_KEY="test-secret-key-with-32-characters",
            LLM_ENABLED=True,
            AI_SYNTHETIC_DEMO_ENABLED=True,
        )
