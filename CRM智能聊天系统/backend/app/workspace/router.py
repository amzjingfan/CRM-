"""客服工作台 HTTP 接口。"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query

from app.auth.dependencies import (
    get_current_user,
    require_csrf,
    require_idempotency_key,
    require_permission,
    require_role,
)
from app.shared.database.base import User
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
from app.workspace.schemas import (
    AssignRequest,
    MessageView,
    OrderSummary,
    ReadResult,
    ReconcileMessageRequest,
    SendMessageRequest,
    SessionListData,
    SessionMessagesData,
    SessionSummary,
    TransferRequest,
    TransferResult,
)
from app.workspace.service import (
    assign_session,
    get_order,
    get_session_list,
    get_session_messages,
    mark_read,
    reconcile_unknown_message,
    send_agent_message,
    transfer_session,
)

router = APIRouter(prefix="/workspace", tags=["客服工作台"])


@router.get(
    "/sessions",
    response_model=ApiResponse[SessionListData],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def sessions(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    filter_name: Annotated[Literal["all", "unread", "mine"], Query(alias="filter")] = "all",
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
