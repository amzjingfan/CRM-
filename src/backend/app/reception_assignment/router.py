"""部门统一咨询分配配置。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, require_csrf, require_permission, require_role
from app.reception_assignment import service
from app.reception_assignment.schemas import ReceptionDepartmentInput, ReceptionDepartmentView
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(tags=["部门咨询分配"])


@router.get(
    "/settings/departments/{department_id}/reception",
    response_model=ApiResponse[ReceptionDepartmentView],
    dependencies=[Depends(require_permission("settings.team"))],
)
async def get_reception_department(
    department_id: uuid.UUID, session: DbSession, actor: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[ReceptionDepartmentView]:
    return ApiResponse(data=await service.get_department_reception(session, actor, department_id))


@router.put(
    "/settings/departments/{department_id}/reception",
    response_model=ApiResponse[ReceptionDepartmentView],
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
)
async def put_reception_department(
    department_id: uuid.UUID,
    payload: ReceptionDepartmentInput,
    session: DbSession,
    actor: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ReceptionDepartmentView]:
    return ApiResponse(data=await service.configure_department_reception(session, actor, department_id, payload))
