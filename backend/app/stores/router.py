"""店铺与渠道管理接口。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.auth.dependencies import get_current_user, require_csrf, require_permission, require_role
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse
from app.stores.schemas import ChannelCreate, ChannelView, StoreCreate, StoreView
from app.stores.service import create_channel, create_store, delete_channel, get_channels, get_stores

router = APIRouter(prefix="/settings", tags=["店铺与渠道"])


@router.get("/stores", response_model=ApiResponse[list[StoreView]])
async def stores(session: DbSession, user: Annotated[User, Depends(get_current_user)]) -> ApiResponse[list[StoreView]]:
    """查询当前用户可访问店铺。"""
    return ApiResponse(data=[StoreView.model_validate(item) for item in await get_stores(session, user)])


@router.post(
    "/stores",
    response_model=ApiResponse[StoreView],
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
)
async def add_store(
    payload: StoreCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[StoreView]:
    """创建店铺。"""
    return ApiResponse(data=StoreView.model_validate(await create_store(session, user, payload)))


@router.get(
    "/channels",
    response_model=ApiResponse[list[ChannelView]],
    dependencies=[Depends(require_permission("settings.channels"))],
)
async def channels(
    session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[ChannelView]]:
    """查询渠道账号。"""
    return ApiResponse(data=[ChannelView.model_validate(item) for item in await get_channels(session, user)])


@router.post(
    "/channels",
    response_model=ApiResponse[ChannelView],
    dependencies=[Depends(require_csrf), Depends(require_permission("settings.channels"))],
)
async def add_channel(
    payload: ChannelCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[ChannelView]:
    """创建渠道账号。"""
    return ApiResponse(data=ChannelView.model_validate(await create_channel(session, user, payload)))


@router.delete(
    "/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf), Depends(require_permission("settings.channels"))],
)
async def remove_channel(
    channel_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """撤销渠道账号。"""
    await delete_channel(session, user, channel_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
