"""TikTok Shop OAuth 公开路由。"""

import uuid
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.auth.dependencies import get_current_user, require_permission
from app.integrations.oauth_schemas import TikTokOAuthStart
from app.integrations.oauth_service import complete_tiktok_oauth, start_tiktok_oauth
from app.shared.config.settings import TIKTOK_OAUTH_CALLBACK_ROUTE
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(tags=["TikTok OAuth"])


@router.get(
    "/settings/channels/tiktok/oauth/start",
    response_model=ApiResponse[TikTokOAuthStart],
    dependencies=[Depends(require_permission("settings.channels"))],
)
async def begin_tiktok_oauth(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    return_to: Annotated[str, Query(max_length=200)] = "/settings/channels",
) -> ApiResponse[TikTokOAuthStart]:
    """为当前用户和内部店铺创建一次性 TikTok 卖家授权。"""
    return ApiResponse(data=await start_tiktok_oauth(session, user, store_id, return_to))


@router.get(TIKTOK_OAUTH_CALLBACK_ROUTE, response_model=None)
async def tiktok_oauth_callback(
    session: DbSession,
    state: Annotated[str, Query(min_length=20, max_length=200)],
    code: Annotated[str | None, Query(max_length=500)] = None,
    error: Annotated[str | None, Query(max_length=100)] = None,
) -> RedirectResponse:
    """消费 state 并完成授权，允许 TikTok 在独立卖家浏览器中回调。"""
    completion = await complete_tiktok_oauth(session, state, code, error)
    query = urlencode({"oauth": "tiktok", "status": completion.status})
    return RedirectResponse(f"{completion.return_to}?{query}", status_code=303)
