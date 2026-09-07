"""主动营销店铺隔离数据访问。"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.marketing.models import MarketingCampaign, MarketingEvent


async def find_campaign(
    session: AsyncSession, campaign_id: uuid.UUID, store_ids: set[uuid.UUID]
) -> MarketingCampaign | None:
    """按资源和允许店铺联合查找活动。"""
    if not store_ids:
        return None
    result: MarketingCampaign | None = await session.scalar(
        select(MarketingCampaign).where(MarketingCampaign.id == campaign_id, MarketingCampaign.store_id.in_(store_ids))
    )
    return result


async def find_event(session: AsyncSession, event_id: uuid.UUID, store_ids: set[uuid.UUID]) -> MarketingEvent | None:
    """按资源 ID 和授权店铺联合查找营销事件。"""
    if not store_ids:
        return None
    result: MarketingEvent | None = await session.scalar(
        select(MarketingEvent).where(MarketingEvent.id == event_id, MarketingEvent.store_id.in_(store_ids))
    )
    return result


async def claim_event_review(
    session: AsyncSession,
    event_id: uuid.UUID,
    store_ids: set[uuid.UUID],
    *,
    review_status: str,
    reviewed_by: uuid.UUID,
    reviewed_at: datetime,
    idempotency_key: str,
    request_hash: str,
) -> MarketingEvent | None:
    """原子抢占待审核事件，确保相反审核决定不能同时成功。

    条件更新由 PostgreSQL 在行锁下重新检查旧状态。并发请求中只有首个
    `waiting_review + pending` 请求能够取得返回行，失败方随后由服务层
    判断是同请求重放还是业务冲突。
    """
    if not store_ids:
        return None
    error_code = None if review_status == "approved" else "AI_MARKETING_DRAFT_REJECTED"
    statement = (
        update(MarketingEvent)
        .where(
            MarketingEvent.id == event_id,
            MarketingEvent.store_id.in_(store_ids),
            MarketingEvent.status == "waiting_review",
            MarketingEvent.ai_review_status == "pending",
            MarketingEvent.ai_draft_content.is_not(None),
        )
        .values(
            status=review_status,
            ai_review_status=review_status,
            ai_reviewed_by=reviewed_by,
            ai_reviewed_at=reviewed_at,
            ai_review_idempotency_key=idempotency_key,
            ai_review_request_hash=request_hash,
            completed_at=reviewed_at,
            error_code=error_code,
        )
        .returning(MarketingEvent)
    )
    claimed: MarketingEvent | None = await session.scalar(statement)
    return claimed


async def list_campaigns(
    session: AsyncSession, store_ids: set[uuid.UUID], store_id: uuid.UUID | None, page: int, page_size: int
) -> tuple[list[MarketingCampaign], int]:
    """稳定分页查询活动。"""
    if not store_ids:
        return [], 0
    conditions: list[ColumnElement[bool]] = [MarketingCampaign.store_id.in_(store_ids)]
    if store_id:
        conditions.append(MarketingCampaign.store_id == store_id)
    total = await session.scalar(select(func.count()).select_from(MarketingCampaign).where(*conditions)) or 0
    items = list(
        (
            await session.scalars(
                select(MarketingCampaign)
                .where(*conditions)
                .order_by(MarketingCampaign.updated_at.desc(), MarketingCampaign.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, int(total)


async def list_events(
    session: AsyncSession,
    store_ids: set[uuid.UUID],
    store_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[MarketingEvent], int]:
    """稳定分页查询营销事件。"""
    if not store_ids:
        return [], 0
    conditions: list[ColumnElement[bool]] = [MarketingEvent.store_id.in_(store_ids)]
    if store_id:
        conditions.append(MarketingEvent.store_id == store_id)
    if campaign_id:
        conditions.append(MarketingEvent.campaign_id == campaign_id)
    total = await session.scalar(select(func.count()).select_from(MarketingEvent).where(*conditions)) or 0
    items = list(
        (
            await session.scalars(
                select(MarketingEvent)
                .where(*conditions)
                .order_by(MarketingEvent.created_at.desc(), MarketingEvent.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, int(total)
