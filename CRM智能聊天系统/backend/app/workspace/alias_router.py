"""兼容管理端现有 /sessions 查询路径。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user, require_permission
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse
from app.workspace.schemas import SessionListData
from app.workspace.service import get_session_list

router = APIRouter(tags=["会话兼容接口"])


@router.get(
    "/sessions",
    response_model=ApiResponse[SessionListData],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def sessions_alias(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[SessionListData]:
    """提供不创建会话的只读兼容接口。"""
    return ApiResponse(data=await get_session_list(session, user, "all", None, None, None, page, page_size))
