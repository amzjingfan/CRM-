"""主动营销活动管理业务规则。"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.marketing.models import MarketingCampaign, MarketingEvent
from app.marketing.repository import claim_event_review, find_campaign, find_event, list_campaigns, list_events
from app.marketing.schemas import (
    CampaignCreate,
    CampaignPage,
    CampaignUpdate,
    CampaignView,
    MarketingDraftReview,
    MarketingEventPage,
    MarketingEventView,
)
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


async def get_campaigns(
    session: AsyncSession, user: User, store_id: uuid.UUID | None, page: int, page_size: int
) -> CampaignPage:
    """返回授权店铺营销活动。"""
    stores = await allowed_store_ids(session, user)
    if store_id and store_id not in stores:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    items, total = await list_campaigns(session, stores, store_id, page, page_size)
    return CampaignPage(
        items=[CampaignView.model_validate(item) for item in items], page=page, page_size=page_size, total=total
    )


async def create_campaign(session: AsyncSession, user: User, payload: CampaignCreate) -> MarketingCampaign:
    """创建默认草稿活动，启用前可由运营复核配置。"""
    await ensure_store_access(session, user, payload.store_id)
    campaign = MarketingCampaign(**payload.model_dump(), created_by=user.id)
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def update_campaign(
    session: AsyncSession, user: User, campaign_id: uuid.UUID, payload: CampaignUpdate
) -> MarketingCampaign:
    """更新活动；触发类型在创建后保持稳定，避免已有事件语义变化。"""
    campaign = await find_campaign(session, campaign_id, await allowed_store_ids(session, user))
    if campaign is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "营销活动不存在", 404)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, key, value)
    if campaign.content_mode == "template" and "message" in campaign.action_type and not campaign.template_content:
        raise AppError(ErrorCode.VALIDATION_ERROR, "模板消息不能为空", 422)
    if "coupon" in campaign.action_type and not campaign.coupon_code:
        raise AppError(ErrorCode.VALIDATION_ERROR, "优惠券动作必须填写 coupon_code", 422)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def set_campaign_status(
    session: AsyncSession, user: User, campaign_id: uuid.UUID, status: str
) -> MarketingCampaign:
    """启停活动并记录审计；AI 内容模式可启用，但事件只进入 waiting_ai。"""
    campaign = await find_campaign(session, campaign_id, await allowed_store_ids(session, user))
    if campaign is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "营销活动不存在", 404)
    campaign.status = status
    session.add(
        AuditLog(
            store_id=campaign.store_id,
            actor_type="user",
            actor_id=user.id,
            action=f"marketing.{status}",
            resource_type="marketing_campaign",
            resource_id=campaign.id,
            after_data={"status": status, "content_mode": campaign.content_mode},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def delete_campaign(session: AsyncSession, user: User, campaign_id: uuid.UUID) -> None:
    """仅允许删除未启用活动，防止执行历史失去归属。"""
    campaign = await find_campaign(session, campaign_id, await allowed_store_ids(session, user))
    if campaign is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "营销活动不存在", 404)
    if campaign.status == "active":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先停用营销活动", 409)
    await session.delete(campaign)
    await session.commit()


async def get_events(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> MarketingEventPage:
    """返回授权店铺营销执行记录。"""
    stores = await allowed_store_ids(session, user)
    if store_id and store_id not in stores:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    items, total = await list_events(session, stores, store_id, campaign_id, page, page_size)
    return MarketingEventPage(
        items=[MarketingEventView.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


async def review_marketing_draft(
    session: AsyncSession,
    user: User,
    event_id: uuid.UUID,
    payload: MarketingDraftReview,
    idempotency_key: str | None = None,
) -> MarketingEvent:
    """原子记录人工审核并支持同请求安全重放，始终禁止平台发送。

    HTTP 调用必须传入客户端幂等键；内部可信调用未传键时使用请求摘要
    派生稳定键，避免测试、脚本或后续任务绕过幂等边界。审核状态变更和
    成功审计在同一事务提交，并发失败方不会留下相反的成功审计。
    """
    stores = await allowed_store_ids(session, user)
    request_hash = _marketing_review_request_hash(event_id, user.id, payload)
    effective_idempotency_key = idempotency_key or f"internal-review:{request_hash}"
    review_status = "approved" if payload.decision == "approve" else "rejected"
    now = datetime.now(UTC)
    try:
        event = await claim_event_review(
            session,
            event_id,
            stores,
            review_status=review_status,
            reviewed_by=user.id,
            reviewed_at=now,
            idempotency_key=effective_idempotency_key,
            request_hash=request_hash,
        )
    except IntegrityError as error:
        # 店铺级唯一约束会阻止同一键并发用于不同事件；失败事务不得保留状态或审计。
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同审核请求", 409) from error

    if event is None:
        current = await find_event(session, event_id, stores)
        if current is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "营销事件不存在", 404)
        stored_key = getattr(current, "ai_review_idempotency_key", None)
        stored_hash = getattr(current, "ai_review_request_hash", None)
        if stored_key == effective_idempotency_key:
            if stored_hash != request_hash:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同审核请求", 409)
            # 同键同请求只读取首个终态，不重复提交，也不重复写成功审计。
            return current
        if current.ai_draft_content is None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "营销草稿不存在", 409)
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "营销草稿当前不可审核", 409)

    audit_data: dict[str, object] = {
        "decision": payload.decision,
        "agent_run_id": str(event.ai_draft_agent_run_id) if event.ai_draft_agent_run_id else None,
        "idempotency_key_sha256": hashlib.sha256(effective_idempotency_key.encode("utf-8")).hexdigest(),
        "request_hash": request_hash,
        "send_performed": False,
    }
    if payload.comment:
        # 自由文本可能含客户信息，只保存摘要用于追踪，不保存原文。
        audit_data["comment_sha256"] = hashlib.sha256(payload.comment.encode("utf-8")).hexdigest()
    session.add(
        AuditLog(
            store_id=event.store_id,
            actor_type="user",
            actor_id=user.id,
            action="marketing.ai_draft.review",
            resource_type="marketing_event",
            resource_id=event.id,
            after_data=audit_data,
            result="succeeded",
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同审核请求", 409) from error
    await session.refresh(event)
    return event


def _marketing_review_request_hash(
    event_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    payload: MarketingDraftReview,
) -> str:
    """计算审核请求低敏摘要，评论原文只参与哈希且不进入日志。"""
    comment_hash = hashlib.sha256((payload.comment or "").encode("utf-8")).hexdigest()
    canonical = f"{event_id}:{reviewer_id}:{payload.decision}:{comment_hash}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
