"""只读观察 staging TikTok Webhook 事件与入站消息的低敏聚合。"""

import asyncio
import json
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select, text

from app.conversations.models import Message
from app.integrations.models import WebhookEvent
from app.shared.config.settings import get_settings
from app.shared.database.session import engine, session_factory
from app.stores.models import ChannelAccount

SUBSCRIPTION_CONFIRMED_AT = datetime(2026, 10, 9, 3, 54, 1, tzinfo=UTC)


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Invalid aggregate count")
    return value


def summarize_events(
    rows: list[tuple[str, bool, int, int]], inbound_messages: int, unbound_events: int
) -> dict[str, int]:
    """将受控状态聚成固定字段，绝不回显平台载荷或动态状态文本。"""
    result = {
        "new_message_events": 0,
        "signature_valid_events": 0,
        "succeeded_events": 0,
        "failed_events": 0,
        "pending_events": 0,
        "ignored_events": 0,
        "other_status_events": 0,
        "retried_events": 0,
        "inbound_messages": _count(inbound_messages),
        "unbound_tiktok_events": _count(unbound_events),
    }
    status_keys = {
        "succeeded": "succeeded_events",
        "failed": "failed_events",
        "received": "pending_events",
        "processing": "pending_events",
        "ignored": "ignored_events",
    }
    for status, signature_valid, retry_count, count in rows:
        amount = _count(count)
        retries = _count(retry_count)
        result["new_message_events"] += amount
        if signature_valid:
            result["signature_valid_events"] += amount
        result[status_keys.get(status, "other_status_events")] += amount
        if retries:
            result["retried_events"] += amount
    return result


async def inspect() -> dict[str, int]:
    """数据库事务强制只读，限定当前唯一已连接 TikTok 渠道。"""
    settings = get_settings()
    if settings.app_env != "staging" or not settings.real_tiktok_webhook_enabled:
        raise RuntimeError("Staging TikTok Webhook mode is disabled")
    async with session_factory() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        channels = (
            await session.scalars(
                select(ChannelAccount)
                .where(ChannelAccount.platform == "tiktok", ChannelAccount.status == "connected")
                .order_by(ChannelAccount.id)
                .limit(2)
            )
        ).all()
        if len(channels) != 1:
            raise RuntimeError("Expected exactly one connected TikTok channel")
        channel = channels[0]
        grouped = await session.execute(
            select(
                WebhookEvent.status,
                WebhookEvent.signature_valid,
                WebhookEvent.retry_count,
                func.count(),
            )
            .where(
                WebhookEvent.platform == "tiktok",
                WebhookEvent.channel_account_id == channel.id,
                WebhookEvent.event_type == "NEW_MESSAGE",
                WebhookEvent.received_at >= SUBSCRIPTION_CONFIRMED_AT,
            )
            .group_by(WebhookEvent.status, WebhookEvent.signature_valid, WebhookEvent.retry_count)
        )
        inbound_messages = await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.store_id == channel.store_id, Message.platform == "tiktok", Message.direction == "inbound")
        )
        unbound_events = await session.scalar(
            select(func.count())
            .select_from(WebhookEvent)
            .where(
                WebhookEvent.platform == "tiktok",
                WebhookEvent.channel_account_id.is_(None),
                WebhookEvent.received_at >= SUBSCRIPTION_CONFIRMED_AT,
            )
        )
        return summarize_events(
            [
                (str(status), bool(signature_valid), int(retry_count), int(count))
                for status, signature_valid, retry_count, count in grouped.all()
            ],
            inbound_messages=int(inbound_messages or 0),
            unbound_events=int(unbound_events or 0),
        )


async def main() -> None:
    try:
        print(json.dumps(await inspect(), separators=(",", ":")))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # 数据库异常可能携带敏感值；Runner 只记录固定失败标记。
        print("tiktok_webhook_event_inspection_failed", file=sys.stderr)
        raise SystemExit(1) from None
