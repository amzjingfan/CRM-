"""定义模型供应商边界的稳定错误类型。"""

from enum import StrEnum
from typing import Literal

LLMOutputFailureKind = Literal["unfinished", "empty", "invalid_structure", "invalid_json", "invalid_schema"]
LLMOutputSchemaPath = Literal[
    "root",
    "unknown",
    "decision",
    "content",
    "language",
    "reason_code",
    "business_claims",
    "send_performed",
    "business_claims[].subject_type",
    "business_claims[].subject_id",
    "business_claims[].action",
    "business_claims[].tense",
    "business_claims[].polarity",
    "business_claims[].condition",
    "business_claims[].evidence_type",
    "business_claims[].evidence_id",
    "business_claims[].confidence",
]
LLMOutputSchemaErrorType = Literal[
    "missing",
    "extra_forbidden",
    "literal_error",
    "string_type",
    "string_too_short",
    "string_too_long",
    "list_type",
    "too_long",
    "less_than_equal",
    "greater_than_equal",
    "float_parsing",
    "uuid_parsing",
    "value_error",
    "model_type",
    "other",
]
LLMOutputSchemaIssue = tuple[LLMOutputSchemaPath, LLMOutputSchemaErrorType]


class LLMErrorCode(StrEnum):
    """屏蔽不同供应商异常差异的模型错误码。"""

    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_RATE_LIMITED = "LLM_RATE_LIMITED"
    LLM_CONNECTION_ERROR = "LLM_CONNECTION_ERROR"
    LLM_AUTHENTICATION_ERROR = "LLM_AUTHENTICATION_ERROR"
    LLM_PERMISSION_DENIED = "LLM_PERMISSION_DENIED"
    LLM_INVALID_REQUEST = "LLM_INVALID_REQUEST"
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
    LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
    LLM_REFUSAL = "LLM_REFUSAL"
    LLM_CONFIGURATION_ERROR = "LLM_CONFIGURATION_ERROR"


class LLMFailureStage(StrEnum):
    """运行失败摘要允许持久化的固定模型节点。"""

    CLASSIFICATION = "classification"
    FAQ_DRAFT = "faq_draft"
    SAFETY_REVIEW = "safety_review"
    TOOL_DRAFT = "tool_draft"
    TOOL_SAFETY_REVIEW = "tool_safety_review"
    TRANSLATION = "translation"


class LLMProviderError(Exception):
    """表示已经完成安全转换、可以被 Agent 服务处理的模型异常。"""

    def __init__(
        self,
        code: LLMErrorCode,
        message: str,
        *,
        retriable: bool,
        output_failure_kind: LLMOutputFailureKind | None = None,
        output_schema_issues: tuple[LLMOutputSchemaIssue, ...] = (),
    ) -> None:
        """初始化模型异常。

        Args:
            code: 对内稳定的模型错误码。
            message: 不包含密钥、Prompt 或客户原文的安全消息。
            retriable: 是否允许在总尝试预算内重试或降级。
            output_failure_kind: 可选的固定输出失败类别，不包含供应商原文。
        """
        self.code = code
        self.retriable = retriable
        self.output_failure_kind = output_failure_kind
        self.output_schema_issues = output_schema_issues
        self.failure_stage: LLMFailureStage | None = None
        super().__init__(message)
