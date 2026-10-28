"""七段式 Agent Prompt 发布与版本校验。"""

import hashlib

import pytest

from app.shared.exceptions.errors import AppError

SECTIONS = {
    "identity": "你是本店物流咨询专员，只处理本店授权会话。",
    "service_scope": "解释当前订单与物流状态；不承诺到货时间。",
    "tool_rules": "优先读取获授权工具；任何写入均请坐席确认。",
    "escalation": "物流数据缺失、状态冲突或超时则升级人工。",
    "language_format": "使用买家语言，输出一段有来源的建议。",
    "compliance": "不泄露个人资料，不发送平台消息。",
    "clarification": "缺少订单上下文时先澄清；工具故障时说明无法确认。",
}


def test_seven_sections_compile_in_fixed_order_and_hash_is_stable() -> None:
    from app.agents.prompts.compiler import compile_prompt, verify_published_prompt

    prompt = compile_prompt(dict(reversed(list(SECTIONS.items()))))
    assert list(prompt.sections) == list(SECTIONS)
    assert prompt.content_sha256 == hashlib.sha256(prompt.text.encode()).hexdigest()
    assert verify_published_prompt(prompt.sections, prompt.content_sha256).text == prompt.text
    assert prompt.text.index("身份与职责边界") < prompt.text.index("澄清策略与异常兜底")
    assert "不得直接发送平台消息" in prompt.text


@pytest.mark.parametrize(
    "sections",
    [
        {key: value for key, value in SECTIONS.items() if key != "compliance"},
        {**SECTIONS, "tool_rules": "   "},
        {**SECTIONS, "unknown": "不要校验"},
        {**SECTIONS, "identity": "A" * 4001},
        {**SECTIONS, "identity": "我的地址是 123 Main Street, New York, NY 10001"},
    ],
)
def test_invalid_or_sensitive_section_cannot_publish(sections: dict[str, str]) -> None:
    from app.agents.prompts.compiler import compile_prompt

    with pytest.raises(AppError) as error:
        compile_prompt(sections)
    assert error.value.status_code == 422


def test_published_prompt_hash_detects_mutation() -> None:
    from app.agents.prompts.compiler import compile_prompt, verify_published_prompt

    digest = compile_prompt(SECTIONS).content_sha256
    with pytest.raises(AppError) as error:
        verify_published_prompt({**SECTIONS, "identity": "另一个身份"}, digest)
    assert error.value.status_code == 409
