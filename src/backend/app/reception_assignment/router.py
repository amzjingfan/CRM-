"""按店铺配置咨询分配；心跳只由本人工作台写入。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, require_csrf, require_permission, require_role
from app.reception_assignment import service
from app.reception_assignment.schemas import (
    OwnReceptionStoreView,
    ReceptionHeartbeatInput,
    ReceptionHeartbeatView,
    ReceptionStoreInput,
    ReceptionStoreView,
)
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(tags=["店铺咨询分配"])


@router.get(
    "/workspace/reception/stores",
    response_model=ApiResponse[list[OwnReceptionStoreView]],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def my_reception_stores(
    session: DbSession, actor: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[OwnReceptionStoreView]]:
    return ApiResponse(data=await service.own_reception_stores(session, actor))


@router.get(
    "/settings/departments/{department_id}/reception/stores/{store_id}",
    response_model=ApiResponse[ReceptionStoreView],
    dependencies=[Depends(require_permission("settings.team"))],
)
async def get_reception_store(
    department_id: uuid.UUID,
    store_id: uuid.UUID,
    session: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ReceptionStoreView]:
    return ApiResponse(data=await service.get_store_reception(session, actor, department_id, store_id))


@router.put(
    "/settings/departments/{department_id}/reception/stores/{store_id}",
    response_model=ApiResponse[ReceptionStoreView],
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
)
async def put_reception_store(
    department_id: uuid.UUID,
    store_id: uuid.UUID,
    payload: ReceptionStoreInput,
    session: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ReceptionStoreView]:
    return ApiResponse(data=await service.configure_store_reception(session, actor, department_id, store_id, payload))


@router.post(
    "/workspace/reception/heartbeat",
    response_model=ApiResponse[ReceptionHeartbeatView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def reception_heartbeat(
    payload: ReceptionHeartbeatInput,
    session: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ReceptionHeartbeatView]:
    return ApiResponse(data=await service.heartbeat(session, actor, payload.store_id, accepting=payload.accepting))
