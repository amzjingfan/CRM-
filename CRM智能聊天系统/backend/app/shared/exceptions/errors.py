"""统一的业务异常和错误码。"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """对外稳定的错误码。"""

    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    USER_DISABLED = "USER_DISABLED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    THIRD_PARTY_ERROR = "THIRD_PARTY_ERROR"


ERROR_NUMERIC_CODES: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 40001,
    ErrorCode.AUTHENTICATION_REQUIRED: 40101,
    ErrorCode.INVALID_CREDENTIALS: 40101,
    ErrorCode.TOKEN_EXPIRED: 40102,
    ErrorCode.TOKEN_INVALID: 40101,
    ErrorCode.USER_DISABLED: 40301,
    ErrorCode.PERMISSION_DENIED: 40301,
    ErrorCode.RESOURCE_NOT_FOUND: 40401,
    ErrorCode.RESOURCE_CONFLICT: 40901,
    ErrorCode.RATE_LIMITED: 42901,
    ErrorCode.INTERNAL_ERROR: 50001,
    ErrorCode.THIRD_PARTY_ERROR: 50003,
}


class AppError(Exception):
    """可安全转换为 API 响应的应用异常。"""

    def __init__(self, code: ErrorCode, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    @property
    def numeric_code(self) -> int:
        """返回管理端接口文档定义的稳定数字错误码。"""
        return ERROR_NUMERIC_CODES[self.code]
