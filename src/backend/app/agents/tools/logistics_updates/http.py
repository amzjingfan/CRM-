"""物流通知策略、低敏台账和显式人工只读预演。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.schemas.responses import ApiResponse

from .integration import ManualLogisticsPreview, ManualLogisticsPreviewRequest, manual_preview
from .policy import (
    LogisticsNotificationView,
    LogisticsPolicyUpdate,
    LogisticsPolicyView,
    get_policy,
    list_notifications,
    update_policy,
)

router = APIRouter(prefix="/logistics-notifications", dependencies=[Depends(require_permission("workspace.reply"))])


@router.get("/policy", response_model=ApiResponse[LogisticsPolicyView])
async def notification_policy(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[LogisticsPolicyView]:
    return ApiResponse(data=await get_policy(session, user, store_id, get_settings()))


@router.patch("/policy", response_model=ApiResponse[LogisticsPolicyView], dependencies=[Depends(require_csrf)])
async def patch_notification_policy(
    store_id: uuid.UUID,
    payload: LogisticsPolicyUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[LogisticsPolicyView]:
    return ApiResponse(data=await update_policy(session, user, store_id, payload, get_settings()))


@router.post("/preview", response_model=ApiResponse[ManualLogisticsPreview], dependencies=[Depends(require_csrf)])
async def preview_logistics_notification(
    payload: ManualLogisticsPreviewRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ManualLogisticsPreview]:
    return ApiResponse(data=await manual_preview(session, user, payload, get_settings()))


@router.get("", response_model=ApiResponse[list[LogisticsNotificationView]])
async def notifications(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    conversation_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[LogisticsNotificationView]]:
    return ApiResponse(
        data=await list_notifications(
            session,
            user,
            store_id,
            conversation_id=conversation_id,
            offset=offset,
        )
    )


@router.get("/{notification_key}", response_model=ApiResponse[LogisticsNotificationView])
async def notification(
    notification_key: str,
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[LogisticsNotificationView]:
    rows = await list_notifications(session, user, store_id, notification_key=notification_key)
    if not rows:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "通知记录不存在", 404)
    return ApiResponse(data=rows[0])
