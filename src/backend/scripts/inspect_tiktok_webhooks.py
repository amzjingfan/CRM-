"""只读核对 staging 官方 Webhook 订阅，输出不含地址和店铺标识的摘要。"""

import asyncio
import json
import re
import sys

from sqlalchemy import select

from app.integrations.tiktok_read import TikTokReadClient, TikTokWebhookSubscription
from app.shared.config.settings import get_settings
from app.shared.database.session import engine, session_factory
from app.stores.models import ChannelAccount

EXPECTED_ADDRESS = "https://staging.overselfx.com/v1/webhooks/tiktok"


def summarize_subscriptions(subscriptions: list[TikTokWebhookSubscription]) -> dict[str, object]:
    """只公开主题和地址匹配数；不回显 URL、Token、店铺或平台请求 ID。"""
    event_types = sorted(
        {
            item.event_type if re.fullmatch(r"[A-Z_]{1,100}", item.event_type) else "UNRECOGNIZED"
            for item in subscriptions
        }
    )
    matching = sum(item.address == EXPECTED_ADDRESS for item in subscriptions)
    return {
        "subscription_count": len(subscriptions),
        "event_types": event_types,
        "matching_address_count": matching,
        "unexpected_address_count": len(subscriptions) - matching,
    }


async def inspect() -> dict[str, object]:
    """仅从一个已连接 TikTok 渠道读取应用订阅，不修改数据库或平台。"""
    settings = get_settings()
    if not settings.real_tiktok_read_enabled:
        raise RuntimeError("TikTok read mode is disabled")
    async with session_factory() as session:
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
        subscriptions, _request_id = await TikTokReadClient(settings, channels[0]).get_webhooks()
    return summarize_subscriptions(subscriptions)


async def main() -> None:
    try:
        print(json.dumps(await inspect(), separators=(",", ":")))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # 平台异常可能携带店铺或请求数据；Runner 日志只写固定错误标记。
        print("tiktok_webhook_subscription_inspection_failed", file=sys.stderr)
        raise SystemExit(1) from None
