"""第三方平台 Webhook 接口。"""

import json

from fastapi import APIRouter, Request

from app.integrations.schemas import WebhookAccepted
from app.integrations.service import receive_webhook
from app.shared.config.settings import get_settings
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/webhooks", tags=["平台 Webhook"])


@router.post("/{platform}", response_model=ApiResponse[WebhookAccepted])
async def webhook(platform: str, request: Request, session: DbSession) -> ApiResponse[WebhookAccepted]:
    """限制载荷大小、验签并快速落库，业务处理交给 Worker。"""
    content_length = request.headers.get("content-length")
    maximum = get_settings().webhook_max_body_bytes
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Webhook Content-Length 无效", 400) from exc
        if declared_length < 0:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Webhook Content-Length 无效", 400)
        if declared_length > maximum:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Webhook 请求体超过 1 MiB", 413)
    raw_body = await request.body()
    if len(raw_body) > maximum:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Webhook 请求体超过 1 MiB", 413)
    try:
        parsed = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Webhook JSON 无效", 422) from exc
    if not isinstance(parsed, dict):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Webhook 必须是 JSON 对象", 422)
    headers = {key.lower(): value for key, value in request.headers.items()}
    result = await receive_webhook(session, platform, raw_body, parsed, headers)
    return ApiResponse(data=result)
