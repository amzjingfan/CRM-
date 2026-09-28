"""对已授权 TikTok 渠道执行不输出业务数据的真实只读冒烟。"""

import argparse
import asyncio
import json
import logging
import uuid

from app.integrations.tiktok_read import TikTokReadClient
from app.shared.config.settings import get_settings
from app.shared.database.session import engine, session_factory
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.logging.setup import configure_logging
from app.stores.models import ChannelAccount


def parse_args() -> argparse.Namespace:
    """读取内部渠道 UUID；命令行不接受 Token、Secret 或客户数据。"""
    parser = argparse.ArgumentParser(description="验证真实 TikTok 店铺只读 API，不执行任何平台写操作")
    parser.add_argument("--channel-id", required=True, type=uuid.UUID, help="channel_accounts 内部 UUID")
    return parser.parse_args()


async def verify(channel_id: uuid.UUID) -> None:
    """验证店铺、订阅、订单、物流、会话和消息读取的最小路径。

    输出只包含计数和布尔状态，不包含店铺 ID、订单号、客户标识、消息、
    Token 或请求签名。没有订单或会话属于可接受结果，不会为制造样本执行写操作。
    """
    settings = get_settings()
    if not settings.real_tiktok_read_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "请先在隔离环境启用 REAL_TIKTOK_READ_ENABLED", 503)
    async with session_factory() as session:
        channel = await session.get(ChannelAccount, channel_id)
        if channel is None:
            raise ValueError("渠道不存在")
        client = TikTokReadClient(settings, channel)
        shops, _ = await client.get_active_shops()
        webhooks, _ = await client.get_webhooks()
        orders, _next_order, _ = await client.search_orders(page_size=20)
        tracking_package_count = 0
        if orders:
            details, _ = await client.get_order_details([orders[0].id])
            if details:
                tracking_packages, _ = await client.get_tracking(details[0].id)
                tracking_package_count = len(tracking_packages)
        conversations, _next_conversation, _ = await client.get_conversations(page_size=20)
        message_count = 0
        if conversations:
            messages, _next_message, _ = await client.get_conversation_messages(conversations[0].id)
            message_count = len(messages)
        print(
            json.dumps(
                {
                    "event": "tiktok_readonly_smoke_succeeded",
                    "shops": len(shops),
                    "webhooks": len(webhooks),
                    "orders": len(orders),
                    "tracking_packages": tracking_package_count,
                    "conversations": len(conversations),
                    "messages": message_count,
                },
                separators=(",", ":"),
            )
        )


async def main() -> None:
    """执行冒烟并关闭数据库连接池。"""
    args = parse_args()
    try:
        await verify(args.channel_id)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    configure_logging("INFO")
    try:
        asyncio.run(main())
    except Exception:
        # 平台响应校验异常可能携带店铺、订单或客户字段；默认 traceback 会绕过低敏日志出口。
        logging.getLogger(__name__).exception(
            "tiktok_readonly_smoke_failed", extra={"event": "tiktok_readonly_smoke_failed"}
        )
        raise SystemExit(1) from None
