"""主动营销管理 HTTP 接口。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.auth.dependencies import get_current_user, require_csrf, require_idempotency_key, require_permission
from app.marketing.schemas import (
    CampaignCreate,
    CampaignPage,
    CampaignUpdate,
    CampaignView,
    MarketingDraftReview,
    MarketingEventPage,
    MarketingEventView,
)
from app.marketing.service import (
    create_campaign,
    delete_campaign,
    get_campaigns,
    get_events,
    review_marketing_draft,
    set_campaign_status,
    update_campaign,
)
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(
    prefix="/marketing",
    tags=["主动营销"],
)


@router.get(
    "/campaigns", response_model=ApiResponse[CampaignPage], dependencies=[Depends(require_permission("marketing.view"))]
)
async def campaigns(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    store_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[CampaignPage]:
    """分页查询营销活动。"""
    return ApiResponse(data=await get_campaigns(session, user, store_id, page, page_size))


@router.post(
    "/campaigns",
    description=(
        "需要 marketing.manage 权限；活动按 store_id 隔离；AI 内容只进入 waiting_ai，重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[CampaignView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("marketing.manage")),
        Depends(require_idempotency_key),
    ],
)
async def add_campaign(
    payload: CampaignCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[CampaignView]:
    """创建营销活动草稿。"""
    return ApiResponse(data=CampaignView.model_validate(await create_campaign(session, user, payload)))


@router.get(
    "/campaigns/{campaign_id}",
    response_model=ApiResponse[CampaignView],
    dependencies=[Depends(require_permission("marketing.view"))],
)
async def campaign_detail(
    campaign_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[CampaignView]:
    """读取单个活动。"""
    from app.auth.store_access import allowed_store_ids
    from app.marketing.repository import find_campaign
    from app.shared.exceptions.errors import AppError, ErrorCode

    campaign = await find_campaign(session, campaign_id, await allowed_store_ids(session, user))
    if campaign is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "营销活动不存在", 404)
    return ApiResponse(data=CampaignView.model_validate(campaign))


@router.patch(
    "/campaigns/{campaign_id}",
    description=(
        "需要 marketing.manage 权限；活动按资源所属 store_id 隔离；"
        "跨店铺资源返回 40401；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[CampaignView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("marketing.manage")),
        Depends(require_idempotency_key),
    ],
)
async def edit_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[CampaignView]:
    """更新营销活动配置。"""
    return ApiResponse(data=CampaignView.model_validate(await update_campaign(session, user, campaign_id, payload)))


@router.delete(
    "/campaigns/{campaign_id}",
    description=(
        "需要 marketing.manage 权限；活动按资源所属 store_id 隔离且启用状态不可删除；重复请求必须复用 Idempotency-Key。"
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("marketing.manage")),
        Depends(require_idempotency_key),
    ],
)
async def remove_campaign(
    campaign_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    """删除未启用活动。"""
    await delete_campaign(session, user, campaign_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/campaigns/{campaign_id}/enable",
    description=(
        "需要 marketing.manage 权限；活动按资源所属 store_id 隔离；"
        "AI 内容活动只进入 waiting_ai；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[CampaignView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("marketing.manage")),
        Depends(require_idempotency_key),
    ],
)
async def enable_campaign(
    campaign_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[CampaignView]:
    """启用活动。"""
    return ApiResponse(
        data=CampaignView.model_validate(await set_campaign_status(session, user, campaign_id, "active"))
    )


@router.post(
    "/campaigns/{campaign_id}/disable",
    description=(
        "需要 marketing.manage 权限；活动按资源所属 store_id 隔离；"
        "停用后不再发现新事件；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[CampaignView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("marketing.manage")),
        Depends(require_idempotency_key),
    ],
)
async def disable_campaign(
    campaign_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[CampaignView]:
    """停用活动。"""
    return ApiResponse(
        data=CampaignView.model_validate(await set_campaign_status(session, user, campaign_id, "disabled"))
    )


@router.get(
    "/events",
    response_model=ApiResponse[MarketingEventPage],
    dependencies=[Depends(require_permission("marketing.view"))],
)
async def events(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    store_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[MarketingEventPage]:
    """分页查询营销执行和转化记录。"""
    return ApiResponse(data=await get_events(session, user, store_id, campaign_id, page, page_size))


@router.post(
    "/events/{event_id}/review",
    description=(
        "需要 marketing.manage 权限；按营销事件所属 store_id 隔离；"
        "只记录 AI 草稿的人工批准或拒绝，不执行发券、消息或任何平台写操作；"
        "重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[MarketingEventView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("marketing.manage")),
    ],
)
async def review_event_draft(
    event_id: uuid.UUID,
    payload: MarketingDraftReview,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[MarketingEventView]:
    """人工审核 AI 营销草稿，审核结论与平台发送严格分离。"""
    event = await review_marketing_draft(session, user, event_id, payload, idempotency_key)
    return ApiResponse(data=MarketingEventView.model_validate(event))
