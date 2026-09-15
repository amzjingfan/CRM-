"""知识服务 HTTP 边界错误。"""

from __future__ import annotations

from fastapi.responses import JSONResponse


def error_response(status_code: int, code: str, message: str, trace_id: str) -> JSONResponse:
    """返回不含业务四态和内部异常的稳定错误信封。"""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}, "trace_id": trace_id},
    )
