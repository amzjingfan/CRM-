"""团队管理 HTTP API。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.auth.dependencies import get_current_user, require_csrf, require_permission, require_role
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse
from app.users.schemas import TeamMemberCreate, TeamMemberUpdate, TeamMemberView
from app.users.service import create_member, delete_member_permanently, disable_member, list_team, update_member

router = APIRouter(prefix="/settings/team", tags=["团队管理"])
READ_DESCRIPTION = "权限：settings.team；普通用户只能查看其店铺范围内的团队成员。"
WRITE_DESCRIPTION = "权限：系统级 admin；需 CSRF。店铺角色必须显式绑定 store_id，禁止自我禁用和禁用最后一个管理员。"
DELETE_DESCRIPTION = "权限：系统级 admin；需 CSRF。仅允许永久删除已禁用且没有受保护业务引用的员工。"


@router.get(
    "",
    response_model=ApiResponse[list[TeamMemberView]],
    dependencies=[Depends(require_permission("settings.team"))],
    description=READ_DESCRIPTION,
)
async def team(
    session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[TeamMemberView]]:
    return ApiResponse(data=await list_team(session, user))


@router.post(
    "",
    response_model=ApiResponse[TeamMemberView],
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
    description=WRITE_DESCRIPTION,
)
async def add_member(
    payload: TeamMemberCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[TeamMemberView]:
    return ApiResponse(data=await create_member(session, user, payload))


@router.get(
    "/{member_id}",
    response_model=ApiResponse[TeamMemberView],
    dependencies=[Depends(require_permission("settings.team"))],
    description=READ_DESCRIPTION,
)
async def member(
    member_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[TeamMemberView]:
    items = await list_team(session, user)
    for item in items:
        if item.id == member_id:
            return ApiResponse(data=item)
    from app.shared.exceptions.errors import AppError, ErrorCode

    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)


@router.patch(
    "/{member_id}",
    response_model=ApiResponse[TeamMemberView],
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
    description=WRITE_DESCRIPTION,
)
async def edit_member(
    member_id: uuid.UUID,
    payload: TeamMemberUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[TeamMemberView]:
    return ApiResponse(data=await update_member(session, user, member_id, payload))


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
    description=WRITE_DESCRIPTION,
)
async def remove_member(
    member_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    await disable_member(session, user, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{member_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
    description=DELETE_DESCRIPTION,
)
async def permanently_remove_member(
    member_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    await delete_member_permanently(session, user, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
