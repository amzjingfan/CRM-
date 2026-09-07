"""定义模型供应商边界的稳定错误类型。"""

from enum import StrEnum


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


class LLMProviderError(Exception):
    """表示已经完成安全转换、可以被 Agent 服务处理的模型异常。"""

    def __init__(self, code: LLMErrorCode, message: str, *, retriable: bool) -> None:
        """初始化模型异常。

        Args:
            code: 对内稳定的模型错误码。
            message: 不包含密钥、Prompt 或客户原文的安全消息。
            retriable: 是否允许在总尝试预算内重试或降级。
        """
        self.code = code
        self.retriable = retriable
        super().__init__(message)
