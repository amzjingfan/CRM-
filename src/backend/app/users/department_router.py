"""部门组织管理接口；组织归属不改变 RBAC。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.auth.dependencies import get_current_user, require_csrf, require_role
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse
from app.users import department_service as service
from app.users.department_schemas import DepartmentCreate, DepartmentMemberAdd, DepartmentUpdate, DepartmentView
from app.users.schemas import TeamMemberView

router = APIRouter(prefix="/settings/departments", tags=["部门管理"])
READ = [Depends(get_current_user)]
WRITE = [Depends(require_csrf), Depends(require_role("admin"))]


@router.get("", response_model=ApiResponse[list[DepartmentView]], dependencies=READ)
async def departments(
    session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[DepartmentView]]:
    return ApiResponse(data=await service.list_departments(session, user))


@router.post("", response_model=ApiResponse[DepartmentView], dependencies=WRITE)
async def create_department(
    payload: DepartmentCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[DepartmentView]:
    return ApiResponse(data=await service.create_department(session, user, payload))


@router.get("/{department_id}", response_model=ApiResponse[DepartmentView], dependencies=READ)
async def department(
    department_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[DepartmentView]:
    return ApiResponse(data=await service.get_department(session, user, department_id))


@router.patch("/{department_id}", response_model=ApiResponse[DepartmentView], dependencies=WRITE)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[DepartmentView]:
    return ApiResponse(data=await service.update_department(session, user, department_id, payload))


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
async def delete_department(
    department_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    await service.delete_department(session, user, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{department_id}/members", response_model=ApiResponse[list[TeamMemberView]], dependencies=READ)
async def members(
    department_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[TeamMemberView]]:
    return ApiResponse(data=await service.list_members(session, user, department_id))


@router.post("/{department_id}/members", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
async def add_member(
    department_id: uuid.UUID,
    payload: DepartmentMemberAdd,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await service.add_member(session, user, department_id, payload.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{department_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
async def remove_member(
    department_id: uuid.UUID, member_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    await service.remove_member(session, user, department_id, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
