"""从事实表幂等重建每日指标。"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.agents.runtime.models import AgentRun
from app.conversations.models import Conversation, Message
from app.dashboard.models import MetricDaily
from app.marketing.models import MarketingEvent
from app.orders.models import Order
from app.shared.config.settings import get_settings
from app.stores.models import Store
from app.tools.models import ToolCall


def store_zone(timezone_name: str) -> ZoneInfo:
    """拒绝静默使用主机时区；非法店铺时区稳定回退 UTC。"""
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def utc_bounds(metric_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = store_zone(timezone_name)
    local_start = datetime.combine(metric_date, time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def percentile_95(values: list[int]) -> int | None:
    """使用最近秩法计算可复现 P95；空样本明确返回空值。"""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, (95 * len(ordered) + 99) // 100)
    return ordered[rank - 1]


async def _count(session: AsyncSession, statement: Select[tuple[int]]) -> int:
    value = await session.scalar(statement)
    return int(value or 0)


async def aggregate_store_day(session: AsyncSession, store: Store, metric_date: date) -> MetricDaily:
    """按店铺本地日聚合；重复执行覆盖同一行而不是累计。"""
    start, end = utc_bounds(metric_date, store.timezone)

    def time_filter(column: Any) -> Any:
        return and_(column >= start, column < end)

    session_count = await _count(
        session,
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.store_id == store.id,
            time_filter(Conversation.created_at),
        ),
    )
    message_count = await _count(
        session,
        select(func.count()).select_from(Message).where(Message.store_id == store.id, time_filter(Message.created_at)),
    )
    agent_run_count = await _count(
        session,
        select(func.count())
        .select_from(AgentRun)
        .where(
            AgentRun.store_id == store.id,
            AgentRun.status == "succeeded",
            AgentRun.action.in_(["auto_reply", "human_review", "transfer_human"]),
            time_filter(AgentRun.created_at),
        ),
    )
    run_rows = list(
        (
            await session.scalars(
                select(AgentRun).where(
                    AgentRun.store_id == store.id,
                    time_filter(AgentRun.created_at),
                )
            )
        ).all()
    )
    rag_runs = [item for item in run_rows if "KNOWLEDGE_RETRIEVED" in (item.output_summary or "")]
    rag_hit_count = sum(item.retrieval_score is not None and item.retrieval_score > 0 for item in rag_runs)
    tool_rows = list(
        (
            await session.scalars(
                select(ToolCall).where(
                    ToolCall.store_id == store.id,
                    ToolCall.agent_run_id.is_not(None),
                    time_filter(ToolCall.created_at),
                )
            )
        ).all()
    )
    first_output_values = [
        item.first_output_latency_ms for item in run_rows if item.first_output_latency_ms is not None
    ]
    input_tokens = sum(item.input_tokens or 0 for item in run_rows)
    output_tokens = sum(item.output_tokens or 0 for item in run_rows)
    settings = get_settings()
    estimated_cost = (
        Decimal(input_tokens) * settings.llm_input_cost_per_million_usd
        + Decimal(output_tokens) * settings.llm_output_cost_per_million_usd
    ) / Decimal(1_000_000)
    transfer_count = await _count(
        session,
        select(func.count())
        .select_from(AgentRun)
        .where(
            AgentRun.store_id == store.id,
            AgentRun.action == "transfer_human",
            time_filter(AgentRun.created_at),
        ),
    )
    ai_reply_count = await _count(
        session,
        select(func.count())
        .select_from(Message)
        .where(
            Message.store_id == store.id,
            Message.role == "assistant",
            Message.agent_run_id.is_not(None),
            Message.status.in_(["sent", "delivered"]),
            time_filter(Message.created_at),
        ),
    )

    channel_rows = (
        await session.execute(
            select(Conversation.platform, func.count())
            .where(Conversation.store_id == store.id, time_filter(Conversation.created_at))
            .group_by(Conversation.platform)
        )
    ).all()
    intent_rows = (
        await session.execute(
            select(AgentRun.intent, func.count())
            .where(
                AgentRun.store_id == store.id,
                AgentRun.intent.is_not(None),
                time_filter(AgentRun.created_at),
            )
            .group_by(AgentRun.intent)
        )
    ).all()

    inbound = aliased(Message)
    outbound = aliased(Message)
    first_outbound = (
        select(func.min(outbound.created_at))
        .where(
            outbound.conversation_id == inbound.conversation_id,
            outbound.created_at > inbound.created_at,
            outbound.direction == "outbound",
        )
        .correlate(inbound)
        .scalar_subquery()
    )
    average_seconds = await session.scalar(
        select(func.avg(func.extract("epoch", first_outbound) - func.extract("epoch", inbound.created_at))).where(
            inbound.store_id == store.id,
            inbound.direction == "inbound",
            time_filter(inbound.created_at),
            first_outbound.is_not(None),
        )
    )
    response_count = await _count(
        session,
        select(func.count())
        .select_from(inbound)
        .where(
            inbound.store_id == store.id,
            inbound.direction == "inbound",
            time_filter(inbound.created_at),
            first_outbound.is_not(None),
        ),
    )
    avg_response_ms = int(float(average_seconds) * 1000) if average_seconds is not None else None

    recovered = await session.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0))
        .select_from(MarketingEvent)
        .join(Order, and_(MarketingEvent.source_type == "order", MarketingEvent.source_id == Order.id))
        .where(
            MarketingEvent.store_id == store.id,
            MarketingEvent.converted_at.is_not(None),
            time_filter(MarketingEvent.converted_at),
        )
    )
    transfer_rate = Decimal(transfer_count) / Decimal(agent_run_count) if agent_run_count else Decimal("0")
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "store_id": store.id,
        "metric_date": metric_date,
        "aggregation_timezone": store.timezone,
        "aggregation_version": "v2",
        "session_count": session_count,
        "message_count": message_count,
        "agent_run_count": agent_run_count,
        "ai_reply_count": ai_reply_count,
        "transfer_count": transfer_count,
        "response_count": response_count,
        "transfer_rate": transfer_rate,
        "avg_response_ms": avg_response_ms,
        "recovered_gmv": Decimal(str(recovered or 0)),
        "channel_breakdown": {str(key): int(value) for key, value in channel_rows},
        "intent_breakdown": {str(key): int(value) for key, value in intent_rows if key is not None},
        "rag_run_count": len(rag_runs),
        "rag_hit_count": rag_hit_count,
        "tool_call_count": len(tool_rows),
        "tool_success_count": sum(item.status == "succeeded" for item in tool_rows),
        "first_output_count": len(first_output_values),
        "p95_first_output_latency_ms": percentile_95(first_output_values),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost.quantize(Decimal("0.000001")),
        # 当前没有人工线上意图标签，不能把模型自信度伪装成准确率。
        "intent_labeled_count": 0,
        "intent_correct_count": 0,
        "updated_at": func.now(),
    }
    base_statement = insert(MetricDaily).values(**values)
    upsert_statement = base_statement.on_conflict_do_update(
        constraint="uq_metric_daily_store_date",
        set_={key: value for key, value in values.items() if key not in {"id", "store_id", "metric_date"}},
    ).returning(MetricDaily)
    row = cast(MetricDaily | None, await session.scalar(upsert_statement))
    assert row is not None
    return row


async def aggregate_recent_metrics(session: AsyncSession, days: int = 2) -> int:
    """更新全部有效店铺最近日期；单次调用统一提交。"""
    stores = list(
        (await session.scalars(select(Store).where(Store.status == "active", Store.deleted_at.is_(None)))).all()
    )
    processed = 0
    for store in stores:
        local_today = datetime.now(store_zone(store.timezone)).date()
        for offset in range(days):
            await aggregate_store_day(session, store, local_today - timedelta(days=offset))
            processed += 1
    await session.commit()
    return processed
