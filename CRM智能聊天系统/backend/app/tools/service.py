"""白名单业务工具实现。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.customers.models import Customer
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.tools.models import CouponIssuance
from app.tools.repository import begin_tool_call, finish_tool_call
from app.tools.schemas import (
    CouponIssueRequest,
    CouponIssueResult,
    LogisticsView,
    ShippingAddressResult,
    ShippingAddressUpdate,
)
from app.workspace.repository import find_order


async def query_logistics(session: AsyncSession, user: User, order_id: str) -> LogisticsView:
    """查询租户内订单物流摘要，不触发外部写操作。"""
    order = await find_order(session, order_id, await allowed_store_ids(session, user))
    if order is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)
    return LogisticsView(
        order_id=order.id,
        external_order_id=order.external_order_id,
        tracking_number=order.tracking_number,
        tracking_status=order.tracking_status,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
    )


async def request_address_update(
    session: AsyncSession,
    user: User,
    order_id: str,
    payload: ShippingAddressUpdate,
    idempotency_key: str,
) -> ShippingAddressResult:
    """创建 Mock 地址变更请求，不覆盖平台权威订单地址。"""
    order = await find_order(session, order_id, await allowed_store_ids(session, user))
    if order is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)
    await ensure_store_access(session, user, order.store_id)
    arguments = payload.model_dump(mode="json") | {"order_id": str(order.id)}
    call, replayed, started = await begin_tool_call(
        session,
        order.store_id,
        "user",
        user.id,
        "update_shipping_address",
        idempotency_key,
        arguments,
        {"order_id": str(order.id), "country_code": payload.country_code, "fields": sorted(payload.model_fields_set)},
    )
    if not replayed:
        # Phase 3 未接真实平台写接口，只记录待平台确认，绝不篡改本地权威快照。
        session.add(
            AuditLog(
                store_id=order.store_id,
                actor_type="user",
                actor_id=user.id,
                action="order.address.update.requested",
                resource_type="order",
                resource_id=order.id,
                after_data={"status": "pending_confirmation", "mocked": True},
                result="succeeded",
            )
        )
        await finish_tool_call(session, call, started, "succeeded", {"status": "pending_confirmation"}, True)
    return ShippingAddressResult(tool_call_id=call.id, status="pending_confirmation", mocked=True, replayed=replayed)


async def issue_coupon(
    session: AsyncSession,
    user: User,
    customer_id: uuid.UUID,
    payload: CouponIssueRequest,
    idempotency_key: str,
) -> CouponIssueResult:
    """通过幂等工具记录创建 Mock 优惠券发放结果。"""
    customer = await session.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.store_id.in_(await allowed_store_ids(session, user))
        )
    )
    if customer is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "客户不存在", 404)
    arguments = payload.model_dump(mode="json") | {"customer_id": str(customer.id)}
    call, replayed, started = await begin_tool_call(
        session,
        customer.store_id,
        "user",
        user.id,
        "send_coupon",
        idempotency_key,
        arguments,
        {"customer_id": str(customer.id), "coupon_code": payload.coupon_code},
    )
    issuance = await session.scalar(select(CouponIssuance).where(CouponIssuance.tool_call_id == call.id))
    if issuance is None:
        issuance = CouponIssuance(
            store_id=customer.store_id,
            customer_id=customer.id,
            tool_call_id=call.id,
            coupon_code=payload.coupon_code,
            description=payload.description,
            expires_at=payload.expires_at,
            mocked=True,
        )
        session.add(issuance)
        session.add(
            AuditLog(
                store_id=customer.store_id,
                actor_type="user",
                actor_id=user.id,
                action="coupon.issue",
                resource_type="customer",
                resource_id=customer.id,
                after_data={"coupon_code": payload.coupon_code, "mocked": True},
                result="succeeded",
            )
        )
        await session.flush()
        await finish_tool_call(session, call, started, "succeeded", {"issuance_id": str(issuance.id)}, True)
    return CouponIssueResult(
        issuance_id=issuance.id,
        tool_call_id=call.id,
        coupon_code=issuance.coupon_code,
        status=issuance.status,
        mocked=issuance.mocked,
        replayed=replayed,
    )
