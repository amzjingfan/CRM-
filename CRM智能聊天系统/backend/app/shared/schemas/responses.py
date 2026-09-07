"""统一 API 响应模型。"""

from typing import Generic, TypeVar

from pydantic import BaseModel

ResponseData = TypeVar("ResponseData")


class ApiResponse(BaseModel, Generic[ResponseData]):
    """所有成功和业务错误响应的外层结构。"""

    code: int = 0
    message: str = "success"
    data: ResponseData | None = None
