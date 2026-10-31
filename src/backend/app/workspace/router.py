"""客服工作台 HTTP 接口。"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile

from app.agents.delivery.contracts import ReplyBatchRequest, ReplyBatchView
from app.agents.delivery.service import deliver_reviewed_batch
from app.auth.dependencies import (
    get_current_user,
    require_csrf,
    require_idempotency_key,
    require_permission,
    require_role,
)
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.redis import consume_chat_query
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.schemas.responses import ApiResponse
from app.tools.schemas import (
    CouponIssueRequest,
    CouponIssueResult,
    LogisticsView,
    ShippingAddressResult,
    ShippingAddressUpdate,
)
from app.tools.service import issue_coupon, query_logistics, request_address_update
from app.workspace.logistics_preview import LogisticsCardPreview
from app.workspace.media import MediaUploadView, upload_media
from app.workspace.schemas import (
    AssigneeView,
    AssignRequest,
    BuyerStageRequest,
    ClosedRequest,
    CustomerSummary,
    DraftTranslationRequest,
    DraftTranslationView,
    MessageTranslationView,
    MessageView,
    OrderSummary,
    ReadResult,
    ReconcileMessageRequest,
    SendLogisticsCardRequest,
    SendMediaRequest,
    SendMessageRequest,
    SendOrderCardRequest,
    SessionActionResult,
    SessionListData,
    SessionMessagesData,
    SessionSearchRequest,
    SessionSummary,
    StarRequest,
    TransferRequest,
    TransferResult,
)
from app.workspace.service import (
    assign_session,
    get_logistics_card_preview,
    get_order,
    get_session_list,
    get_session_messages,
    list_session_assignees,
    mark_read,
    reconcile_unknown_message,
    send_agent_logistics_card,
    send_agent_message,
    send_agent_order_card,
    set_buyer_stage_override,
    set_conversation_closed,
    set_conversation_star,
    transfer_session,
    translate_draft,
    translate_message,
    translate_sidebar_tracking,
    translate_sidebar_tracking_timeline,
)
from app.workspace.sidebar import (
    SidebarCoupons,
    SidebarOrderDetail,
    SidebarOrderDetailRequest,
    SidebarOrders,
    SidebarProduct,
    SidebarProducts,
    SidebarSearch,
    SidebarStandardTracking,
    SidebarTrackingTimeline,
    SidebarTrackingTimelineTranslation,
    SidebarTrackingTimelineTranslationRequest,
    SidebarTrackingTranslation,
    SidebarTrackingTranslationRequest,
    get_sidebar_enhanced_tracking,
    get_sidebar_order_detail,
    get_sidebar_product,
    get_sidebar_standard_tracking,
    search_sidebar_coupons,
    search_sidebar_orders,
    search_sidebar_products,
)

router = APIRouter(prefix="/workspace", tags=["客服工作台"])


@router.get(
    "/sessions/{session_id}/logistics-card-preview",
    response_model=ApiResponse[list[LogisticsCardPreview]],
    dependencies=[Depends(require_permission("workspace.view")), Depends(require_permission("orders.view"))],
)
async def logistics_card_preview(
    session_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    order_id: Annotated[str, Query(min_length=1, max_length=200, pattern=r"^[0-9]+$")],
) -> ApiResponse[list[LogisticsCardPreview]]:
    return ApiResponse(data=await get_logistics_card_preview(session, user, session_id, order_id))


@router.post(
    "/sessions/{session_id}/reply-batches",
    response_model=ApiResponse[ReplyBatchView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def reply_batch(
    session_id: uuid.UUID,
    payload: ReplyBatchRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[ReplyBatchView]:
    return ApiResponse(data=await deliver_reviewed_batch(session, user, session_id, payload, idempotency_key))


@router.post(
    "/sessions/{session_id}/sidebar/search",
    response_model=ApiResponse[SidebarOrders | SidebarProducts | SidebarCoupons],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def sidebar_search(
    session_id: uuid.UUID,
    payload: SidebarSearch,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarOrders | SidebarProducts | SidebarCoupons]:
    """按会话授权读取侧栏数据；搜索词放请求体，避免进入访问日志。"""
    data: SidebarOrders | SidebarProducts | SidebarCoupons
    if payload.section == "orders":
        data = await search_sidebar_orders(session, user, session_id, payload)
    elif payload.section == "products":
        data = await search_sidebar_products(session, user, session_id, payload)
    else:
        data = await search_sidebar_coupons(session, user, session_id, payload)
    return ApiResponse(data=data)


@router.post(
    "/sessions/{session_id}/sidebar/orders/detail",
    response_model=ApiResponse[SidebarOrderDetail],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def sidebar_order_detail(
    session_id: uuid.UUID,
    payload: SidebarOrderDetailRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarOrderDetail]:
    """仅在会话买家身份经官方核对后读取该订单的只读物流详情。"""
    return ApiResponse(
        data=await get_sidebar_order_detail(
            session, user, session_id, payload.order_id, include_tracking=payload.include_tracking
        )
    )


@router.post(
    "/sessions/{session_id}/sidebar/orders/standard-tracking",
    response_model=ApiResponse[SidebarStandardTracking],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def sidebar_standard_tracking(
    session_id: uuid.UUID,
    payload: SidebarOrderDetailRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarStandardTracking]:
    """当前用户与店铺授权内，独立读取已核验订单的通用物流。"""
    return ApiResponse(data=await get_sidebar_standard_tracking(session, user, session_id, payload.order_id))


@router.post(
    "/sessions/{session_id}/sidebar/orders/enhanced-tracking",
    response_model=ApiResponse[SidebarTrackingTimeline],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def sidebar_enhanced_tracking(
    session_id: uuid.UUID,
    payload: SidebarOrderDetailRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarTrackingTimeline]:
    """仅对已核对买家订单按需读取跨境多包裹轨迹。"""
    return ApiResponse(data=await get_sidebar_enhanced_tracking(session, user, session_id, payload.order_id))


@router.post(
    "/sessions/{session_id}/sidebar/orders/tracking-translation",
    response_model=ApiResponse[SidebarTrackingTranslation],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def sidebar_tracking_translation(
    session_id: uuid.UUID,
    payload: SidebarTrackingTranslationRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarTrackingTranslation]:
    """坐席主动翻译已核对买家订单的最新物流描述。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流描述翻译未启用", 503)
    client_ip = request.client.host if request.client else "unknown"
    if not await consume_chat_query(user.id, client_ip, settings.chat_query_limit, settings.chat_query_window_seconds):
        raise AppError(ErrorCode.RATE_LIMITED, "翻译请求过于频繁", 429)
    trace_id = str(getattr(request.state, "trace_id", uuid.uuid4()))
    return ApiResponse(
        data=await translate_sidebar_tracking(
            session,
            user,
            session_id,
            payload.order_id,
            trace_id,
            payload.event_description,
            payload.event_at,
            payload.event_tracking_number,
            payload.enhanced,
        )
    )


@router.post(
    "/sessions/{session_id}/sidebar/orders/tracking-timeline-translation",
    response_model=ApiResponse[SidebarTrackingTimelineTranslation],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def sidebar_tracking_timeline_translation(
    session_id: uuid.UUID,
    payload: SidebarTrackingTimelineTranslationRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarTrackingTimelineTranslation]:
    """一次点击翻译已核对订单的全部物流节点，保留原文可切换。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流描述翻译未启用", 503)
    client_ip = request.client.host if request.client else "unknown"
    if not await consume_chat_query(user.id, client_ip, settings.chat_query_limit, settings.chat_query_window_seconds):
        raise AppError(ErrorCode.RATE_LIMITED, "翻译请求过于频繁", 429)
    trace_id = str(getattr(request.state, "trace_id", uuid.uuid4()))
    return ApiResponse(
        data=await translate_sidebar_tracking_timeline(
            session,
            user,
            session_id,
            payload.order_id,
            trace_id,
            enhanced=payload.enhanced,
        )
    )


@router.get(
    "/sessions/{session_id}/sidebar/products/{product_id}",
    response_model=ApiResponse[SidebarProduct],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def sidebar_product(
    session_id: uuid.UUID,
    product_id: str,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SidebarProduct]:
    """展开商品卡时按会话店铺授权读取 SKU 属性和图片。"""
    return ApiResponse(data=await get_sidebar_product(session, user, session_id, product_id))


@router.post(
    "/sessions/search",
    response_model=ApiResponse[SessionListData],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def search_sessions(
    payload: SessionSearchRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SessionListData]:
    """从全部已授权会话中搜索，分页、店铺和状态范围同普通列表。"""
    if not payload.q and not payload.terms:
        raise AppError(ErrorCode.VALIDATION_ERROR, "请输入搜索词", 422)
    return ApiResponse(
        data=await get_session_list(
            session,
            user,
            payload.filter,
            payload.platform,
            payload.store_id,
            payload.status,
            payload.page,
            payload.page_size,
            payload.search_scope,
            payload.q,
            payload.terms,
        )
    )


@router.post(
    "/sessions/{session_id}/draft/translation",
    response_model=ApiResponse[DraftTranslationView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def draft_translation(
    session_id: uuid.UUID,
    payload: DraftTranslationRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[DraftTranslationView]:
    """只生成待人工审阅的多语言译文，不发 TikTok 消息。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "草稿翻译未启用", 503)
    client_ip = request.client.host if request.client else "unknown"
    if not await consume_chat_query(user.id, client_ip, settings.chat_query_limit, settings.chat_query_window_seconds):
        raise AppError(ErrorCode.RATE_LIMITED, "翻译请求过于频繁", 429)
    trace_id = str(getattr(request.state, "trace_id", uuid.uuid4()))
    return ApiResponse(
        data=await translate_draft(session, user, session_id, payload.source_text, payload.target_language, trace_id)
    )


@router.post(
    "/sessions/{session_id}/messages/{message_id}/translation",
    response_model=ApiResponse[MessageTranslationView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def message_translation(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[MessageTranslationView]:
    """坐席主动翻译一条已授权消息，不发送任何平台消息。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "消息翻译未启用", 503)
    client_ip = request.client.host if request.client else "unknown"
    if not await consume_chat_query(user.id, client_ip, settings.chat_query_limit, settings.chat_query_window_seconds):
        raise AppError(ErrorCode.RATE_LIMITED, "翻译请求过于频繁", 429)
    trace_id = str(getattr(request.state, "trace_id", uuid.uuid4()))
    return ApiResponse(data=await translate_message(session, user, session_id, message_id, trace_id))


@router.get(
    "/sessions",
    response_model=ApiResponse[SessionListData],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def sessions(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    filter_name: Annotated[Literal["all", "unread", "mine", "starred", "closed"], Query(alias="filter")] = "all",
    platform: str | None = None,
    store_id: uuid.UUID | None = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[SessionListData]:
    """分页查询工作台会话。"""
    return ApiResponse(
        data=await get_session_list(session, user, filter_name, platform, store_id, status, page, page_size)
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[SessionMessagesData],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def messages(
    session_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[SessionMessagesData]:
    """读取消息详情但不改变未读状态。"""
    return ApiResponse(data=await get_session_messages(session, user, session_id, page, page_size))


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[MessageView],
    description=(
        "需要 workspace.reply 权限、认证用户的店铺访问权、Cookie Origin/CSRF 校验和必填 Idempotency-Key；"
        "请求体 confirmed 只接受 JSON 布尔 true。真实平台结果未知时返回可对账的 unknown，不自动重试。"
    ),
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def send_message(
    session_id: uuid.UUID,
    payload: SendMessageRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[MessageView]:
    """人工发送消息，要求二次确认和显式幂等键。"""
    message = await send_agent_message(
        session,
        user,
        session_id,
        payload.content,
        idempotency_key,
        confirmed=payload.confirmed,
    )
    return ApiResponse(data=message)


@router.post(
    "/sessions/{session_id}/messages/media/upload",
    response_model=ApiResponse[MediaUploadView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def upload_message_media(
    session_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[MediaUploadView]:
    """仅把校验后的文件上传 TikTok，并返回绑定当前坐席的短时凭据。"""
    return ApiResponse(data=await upload_media(session, user, session_id, file, idempotency_key))


@router.post(
    "/sessions/{session_id}/messages/media",
    response_model=ApiResponse[MessageView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def send_message_media(
    session_id: uuid.UUID,
    payload: SendMediaRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[MessageView]:
    """坐席二次确认后，由工具层完成目标复核、幂等、审计和唯一一次外发。"""
    message = await send_agent_message(
        session,
        user,
        session_id,
        "[图片]" if payload.kind == "image" else "[视频]",
        idempotency_key,
        confirmed=payload.confirmed,
        message_type=payload.kind,
        media_token=payload.upload_token,
    )
    return ApiResponse(data=message)


@router.post(
    "/sessions/{session_id}/messages/logistics-card",
    response_model=ApiResponse[MessageView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def send_logistics_card(
    session_id: uuid.UUID,
    payload: SendLogisticsCardRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[MessageView]:
    """坐席二次确认后发送当前买家订单的 TikTok 原生物流卡片。"""
    message = await send_agent_logistics_card(
        session,
        user,
        session_id,
        payload.order_id,
        payload.package_id,
        idempotency_key,
        confirmed=payload.confirmed,
    )
    return ApiResponse(data=message)


@router.post(
    "/sessions/{session_id}/messages/order-card",
    response_model=ApiResponse[MessageView],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def send_order_card(
    session_id: uuid.UUID,
    payload: SendOrderCardRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[MessageView]:
    """人工确认后发送已核对买家订单的 TikTok 原生订单卡片。"""
    return ApiResponse(
        data=await send_agent_order_card(
            session,
            user,
            session_id,
            payload.order_id,
            idempotency_key,
            confirmed=payload.confirmed,
        )
    )


@router.post(
    "/messages/{message_id}/reconcile",
    response_model=ApiResponse[MessageView],
    description=(
        "仅系统级 admin 可用；要求 Cookie Origin/CSRF 和消息店铺访问权。"
        "只允许依据 TikTok 后台事实关闭 unknown 消息，并同步工具调用与审计终态。"
    ),
    dependencies=[Depends(require_csrf), Depends(require_role("admin"))],
)
async def reconcile_message(
    message_id: uuid.UUID,
    payload: ReconcileMessageRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[MessageView]:
    """管理员根据 TikTok 后台事实关闭 unknown 结果并解除发送熔断。"""
    return ApiResponse(
        data=await reconcile_unknown_message(
            session,
            user,
            message_id,
            payload.resolution,
            payload.external_message_id,
        )
    )


@router.post(
    "/sessions/{session_id}/read",
    response_model=ApiResponse[ReadResult],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def read_session(
    session_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[ReadResult]:
    """显式标记会话已读。"""
    return ApiResponse(data=ReadResult(unread_count=await mark_read(session, user, session_id)))


@router.patch(
    "/sessions/{session_id}/star",
    response_model=ApiResponse[SessionActionResult],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.transfer"))],
)
async def star_session(
    session_id: uuid.UUID, payload: StarRequest, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[SessionActionResult]:
    """标记或取消 CRM 内部差评风险星标。"""
    return ApiResponse(data=await set_conversation_star(session, user, session_id, payload.starred))


@router.patch(
    "/sessions/{session_id}/buyer-stage",
    response_model=ApiResponse[CustomerSummary],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def update_buyer_stage(
    session_id: uuid.UUID,
    payload: BuyerStageRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[CustomerSummary]:
    """显式设置买家阶段或恢复按订单自动判断，不发送平台消息。"""
    return ApiResponse(data=await set_buyer_stage_override(session, user, session_id, payload.stage))


@router.patch(
    "/sessions/{session_id}/closed",
    response_model=ApiResponse[SessionActionResult],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.transfer"))],
)
async def close_session(
    session_id: uuid.UUID, payload: ClosedRequest, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[SessionActionResult]:
    """仅更新 CRM 会话工作流；不调用 TikTok 关闭接口。"""
    return ApiResponse(data=await set_conversation_closed(session, user, session_id, payload.closed))


@router.get(
    "/sessions/{session_id}/assignees",
    response_model=ApiResponse[list[AssigneeView]],
    dependencies=[Depends(require_permission("workspace.transfer"))],
)
async def assignees(
    session_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[AssigneeView]]:
    """列出会话店铺可转交的在职坐席。"""
    return ApiResponse(data=await list_session_assignees(session, user, session_id))


@router.post(
    "/sessions/{session_id}/assign",
    response_model=ApiResponse[SessionSummary],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.transfer"))],
)
async def assign(
    session_id: uuid.UUID,
    payload: AssignRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SessionSummary]:
    """分配会话。"""
    await assign_session(session, user, session_id, payload.user_id)
    detail = await get_session_messages(session, user, session_id, 1, 1)
    return ApiResponse(data=detail.session)


@router.post(
    "/sessions/{session_id}/transfer",
    response_model=ApiResponse[TransferResult],
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.transfer"))],
)
async def transfer(
    session_id: uuid.UUID,
    payload: TransferRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApiResponse[TransferResult]:
    """转人工并返回审计记录 ID。"""
    if not idempotency_key or len(idempotency_key) > 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Idempotency-Key 必填且不能超过 200 字符", 422)
    return ApiResponse(
        data=await transfer_session(session, user, session_id, payload.reason, payload.assign_to, idempotency_key)
    )


@router.get(
    "/actions/order/{order_id}",
    response_model=ApiResponse[OrderSummary],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def order(
    order_id: str, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[OrderSummary]:
    """查询订单摘要。"""
    return ApiResponse(data=await get_order(session, user, order_id))


@router.get(
    "/actions/order/{order_id}/logistics",
    response_model=ApiResponse[LogisticsView],
    dependencies=[Depends(require_permission("orders.view"))],
)
async def logistics(
    order_id: str, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[LogisticsView]:
    """查询店铺隔离的物流摘要。"""
    return ApiResponse(data=await query_logistics(session, user, order_id))


@router.patch(
    "/actions/order/{order_id}/shipping-address",
    description=(
        "需要 orders.address.update 权限；按店铺隔离；当前为 Mock pending_confirmation；必须携带 Idempotency-Key。"
    ),
    response_model=ApiResponse[ShippingAddressResult],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("orders.address.update")),
        Depends(require_idempotency_key),
    ],
)
async def update_address(
    order_id: str,
    payload: ShippingAddressUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApiResponse[ShippingAddressResult]:
    """提交 Mock 地址修改请求，不覆盖订单快照。"""
    if not idempotency_key or len(idempotency_key) > 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Idempotency-Key 必填且不能超过 200 字符", 422)
    return ApiResponse(data=await request_address_update(session, user, order_id, payload, idempotency_key))


@router.post(
    "/actions/customer/{customer_id}/coupon",
    response_model=ApiResponse[CouponIssueResult],
    dependencies=[Depends(require_csrf), Depends(require_permission("coupons.issue"))],
)
async def coupon(
    customer_id: uuid.UUID,
    payload: CouponIssueRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApiResponse[CouponIssueResult]:
    """向客户发放明确标记为 Mock 的优惠券。"""
    if not idempotency_key or len(idempotency_key) > 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Idempotency-Key 必填且不能超过 200 字符", 422)
    return ApiResponse(data=await issue_coupon(session, user, customer_id, payload, idempotency_key))
