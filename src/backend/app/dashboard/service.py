"""看板查询、店铺隔离和零值补齐。"""

import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import AgentRun
from app.auth.store_access import ensure_store_access
from app.dashboard.aggregation import store_zone, utc_bounds
from app.dashboard.models import MetricDaily
from app.dashboard.schemas import (
    AbandonedCartAlert,
    ChannelItem,
    DashboardAlerts,
    DashboardChannels,
    DashboardMetrics,
    DashboardPeriod,
    DashboardTrend,
    RefundAlert,
    ReviewAlert,
    TopQueryItem,
    TrendPoint,
)
from app.marketing.models import CustomerReview
from app.orders.models import Order
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


async def _store(session: AsyncSession, user: User, store_id: uuid.UUID) -> Store:
    await ensure_store_access(session, user, store_id)
    store = await session.get(Store, store_id)
    if store is None or store.deleted_at is not None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
    return store


def period_days(period: DashboardPeriod) -> int:
    return {"today": 1, "7d": 7, "30d": 30}[period]


async def _rows(
    session: AsyncSession,
    store: Store,
    days: int,
) -> tuple[list[MetricDaily], date]:
    today = datetime.now(store_zone(store.timezone)).date()
    start = today - timedelta(days=days - 1)
    items = list(
        (
            await session.scalars(
                select(MetricDaily)
                .where(
                    MetricDaily.store_id == store.id,
                    MetricDaily.metric_date >= start,
                    MetricDaily.metric_date <= today,
                )
                .order_by(MetricDaily.metric_date)
            )
        ).all()
    )
    return items, start


async def _period_first_output_p95(
    session: AsyncSession,
    store: Store,
    start_date: date,
    end_date: date,
) -> int | None:
    """按店铺本地日期边界从周期原始样本计算离散 P95。

    每日 P95 不能直接合并；取每日最大值会让低样本异常日严重放大周期指标。
    PostgreSQL ``percentile_disc`` 与项目最近秩口径一致，并避免把最多 30 天的
    全部延迟样本加载到应用内存。
    """
    start, _ = utc_bounds(start_date, store.timezone)
    _, end = utc_bounds(end_date, store.timezone)
    value = await session.scalar(
        select(func.percentile_disc(0.95).within_group(AgentRun.first_output_latency_ms)).where(
            AgentRun.store_id == store.id,
            AgentRun.first_output_latency_ms.is_not(None),
            AgentRun.created_at >= start,
            AgentRun.created_at < end,
        )
    )
    return int(value) if value is not None else None


async def metrics(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    period: DashboardPeriod,
) -> DashboardMetrics:
    store = await _store(session, user, store_id)
    days = period_days(period)
    rows, start = await _rows(session, store, days)
    end = start + timedelta(days=days - 1)
    agent_runs = sum(item.agent_run_count for item in rows)
    transfers = sum(item.transfer_count for item in rows)
    response_count = sum(item.response_count for item in rows)
    rag_runs = sum(item.rag_run_count for item in rows)
    rag_hits = sum(item.rag_hit_count for item in rows)
    tool_calls = sum(item.tool_call_count for item in rows)
    tool_successes = sum(item.tool_success_count for item in rows)
    labeled_intents = sum(item.intent_labeled_count for item in rows)
    correct_intents = sum(item.intent_correct_count for item in rows)
    settings = get_settings()
    weighted_response = (
        sum((item.avg_response_ms or 0) * item.response_count for item in rows) / response_count / 1000
        if response_count
        else None
    )
    return DashboardMetrics(
        total_sessions=sum(item.session_count for item in rows),
        transfer_rate=round(transfers / agent_runs * 100, 2) if agent_runs else 0,
        avg_response_time=round(weighted_response, 2) if weighted_response is not None else None,
        recovered_gmv=sum((item.recovered_gmv for item in rows), Decimal("0")),
        currency=store.currency,
        period=period,
        updated_at=max((item.updated_at for item in rows), default=None),
        intent_accuracy=(round(correct_intents / labeled_intents * 100, 2) if labeled_intents else None),
        intent_labeled_count=labeled_intents,
        rag_hit_rate=round(rag_hits / rag_runs * 100, 2) if rag_runs else 0,
        tool_success_rate=round(tool_successes / tool_calls * 100, 2) if tool_calls else 0,
        p95_first_output_latency_ms=await _period_first_output_p95(session, store, start, end),
        total_input_tokens=sum(item.input_tokens for item in rows),
        total_output_tokens=sum(item.output_tokens for item in rows),
        estimated_cost_usd=sum((item.estimated_cost_usd for item in rows), Decimal("0")),
        cost_configured=(settings.llm_input_cost_per_million_usd > 0 or settings.llm_output_cost_per_million_usd > 0),
    )


async def trend(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    days: int,
) -> DashboardTrend:
    store = await _store(session, user, store_id)
    rows, start = await _rows(session, store, days)
    values = {item.metric_date: item.session_count for item in rows}
    return DashboardTrend(
        items=[
            TrendPoint(date=start + timedelta(days=offset), sessions=values.get(start + timedelta(days=offset), 0))
            for offset in range(days)
        ]
    )


async def channels(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    period: DashboardPeriod,
) -> DashboardChannels:
    store = await _store(session, user, store_id)
    rows, _ = await _rows(session, store, period_days(period))
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update({key: int(value) for key, value in row.channel_breakdown.items()})
    total = sum(counts.values())
    platforms = ["tiktok", "shopee", "amazon"]
    return DashboardChannels(
        items=[
            ChannelItem(
                platform=platform,
                count=counts.get(platform, 0),
                percentage=round(counts.get(platform, 0) / total * 100, 2) if total else 0,
            )
            for platform in platforms
        ]
    )


async def alerts(session: AsyncSession, user: User, store_id: uuid.UUID) -> DashboardAlerts:
    store = await _store(session, user, store_id)
    refund_total = int(
        await session.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.store_id == store.id,
                Order.status.in_(["refund_requested", "return_requested"]),
            )
        )
        or 0
    )
    review_total = int(
        await session.scalar(
            select(func.count())
            .select_from(CustomerReview)
            .where(
                CustomerReview.store_id == store.id,
                CustomerReview.rating <= 3,
            )
        )
        or 0
    )
    threshold = datetime.now(UTC) - timedelta(minutes=30)
    abandoned_count, abandoned_value = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.store_id == store.id,
                Order.payment_status.in_(["pending", "unpaid"]),
                Order.created_at <= threshold,
            )
        )
    ).one()
    return DashboardAlerts(
        refund_requests=RefundAlert(total=int(refund_total)),
        bad_reviews=ReviewAlert(total=review_total, golden_window=review_total > 0),
        abandoned_carts=AbandonedCartAlert(
            total=int(abandoned_count or 0),
            potential_gmv=Decimal(str(abandoned_value or 0)),
        ),
    )


async def top_queries(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    period: DashboardPeriod,
    limit: int,
) -> list[TopQueryItem]:
    store = await _store(session, user, store_id)
    rows, _ = await _rows(session, store, period_days(period))
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update({key: int(value) for key, value in row.intent_breakdown.items()})
    return [
        TopQueryItem(rank=index, intent=intent, count=count)
        for index, (intent, count) in enumerate(counts.most_common(limit), start=1)
    ]
