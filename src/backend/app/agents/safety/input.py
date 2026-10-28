"""按来源标记不可信数据并在模型调用前执行字段级脱敏。"""

import json
from dataclasses import dataclass
from typing import Literal

from app.agents.core.security import PromptSafetyState, evaluate_prompt_safety
from app.shared.exceptions.errors import AppError, ErrorCode

UntrustedSource = Literal["user_message", "knowledge_chunk", "tool_result", "session_summary", "agent_draft"]


@dataclass(frozen=True, slots=True)
class SafeModelText:
    """保留来源与脱敏后的文本；原始字段不得写入运行日志。"""

    source: UntrustedSource
    text: str
    redacted: bool

    def as_user_message(self) -> dict[str, str]:
        """通过 JSON 数据边界传给 user 角色，不能冒充系统指令。"""
        return {
            "role": "user",
            "content": json.dumps(
                {"untrusted_source": self.source, "text": self.text}, ensure_ascii=False, separators=(",", ":")
            ),
        }


def prepare_untrusted_text(text: str, *, source: UntrustedSource) -> SafeModelText:
    """放行已脱敏的普通自由文本；完整地址或结构化冒充保持失败关闭。"""
    normalized = text.strip()
    if not normalized or len(normalized) > 16_000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 输入为空或超过安全长度", 422)
    if normalized[0] in "{[":
        raise AppError(ErrorCode.VALIDATION_ERROR, "结构化输入需先按字段校验", 422)
    decision = evaluate_prompt_safety(normalized)
    if decision.state == PromptSafetyState.BLOCKED or decision.reason_code != "UNTRUSTED_FREE_TEXT_REQUIRES_DLP":
        raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 输入含不可传递的敏感内容", 422)
    return SafeModelText(
        source=source,
        text=decision.sanitized_text,
        redacted=decision.sanitized_text != normalized,
    )
