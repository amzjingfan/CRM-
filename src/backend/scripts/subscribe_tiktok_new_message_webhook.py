"""仅在获批后为 staging 店铺注册一个 NEW_MESSAGE Webhook。"""

import asyncio
import json
import os
import sys
import time

import httpx
from sqlalchemy import select

from app.integrations.tiktok_http import create_tiktok_http_client
from app.integrations.tiktok_oauth import generate_api_signature
from app.integrations.tiktok_read import API_BASE_URL, TikTokReadClient, TikTokWebhookSubscription
from app.shared.config.settings import get_settings
from app.shared.database.session import engine, session_factory
from app.stores.models import ChannelAccount

TOPIC = "NEW_MESSAGE"
ADDRESS = "https://staging.overselfx.com/v1/webhooks/tiktok"
PATH = "/event/202309/webhooks"
CONFIRMATION = f"{TOPIC}@{ADDRESS}"


def preflight_decision(subscriptions: list[TikTokWebhookSubscription]) -> str:
    """只允许空订阅上的首次写入或精确目标的无写入复核。"""
    if not subscriptions:
        return "write"
    if len(subscriptions) == 1 and subscriptions[0].event_type == TOPIC and subscriptions[0].address == ADDRESS:
        return "already_present"
    raise RuntimeError("Unexpected existing webhook subscription")


def build_signed_request(
    app_key: str, shop_cipher: str, app_secret: str, timestamp: int
) -> tuple[dict[str, str | int], bytes]:
    """签名与实际发送使用同一原始正文，地址和主题不可由运行参数改写。"""
    body = json.dumps({"event_type": TOPIC, "address": ADDRESS}, separators=(",", ":")).encode("utf-8")
    params: dict[str, str | int] = {
        "app_key": app_key,
        "shop_cipher": shop_cipher,
        "timestamp": timestamp,
    }
    params["sign"] = generate_api_signature(PATH, params, app_secret, body)
    return params, body


async def subscribe() -> dict[str, object]:
    """一次 PUT 后只读对账；任何不确定结果均不自动重试写入。"""
    if os.environ.get("CRM_G2_WEBHOOK_SUBSCRIPTION_CONFIRM") != CONFIRMATION:
        raise RuntimeError("Exact staging subscription confirmation is missing")
    settings = get_settings()
    if not settings.real_tiktok_read_enabled or not settings.real_tiktok_webhook_enabled:
        raise RuntimeError("Staging TikTok read and Webhook mode must both be enabled")
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
        read_client = TikTokReadClient(settings, channels[0])
        before, _request_id = await read_client.get_webhooks()
        decision = preflight_decision(before)
        if decision == "already_present":
            return {
                "status": "already_present",
                "event_type": TOPIC,
                "subscription_count": 1,
                "matching_address_count": 1,
                "write_attempted": False,
            }

        params, body = build_signed_request(
            settings.tiktok_app_key, read_client.shop_cipher, read_client.app_secret, int(time.time())
        )
        write_http_status: int | None = None
        try:
            async with create_tiktok_http_client(settings) as http_client:
                response = await http_client.request(
                    "PUT",
                    f"{API_BASE_URL}{PATH}",
                    params=params,
                    headers={
                        "content-type": "application/json",
                        "x-tts-access-token": read_client.access_token,
                    },
                    content=body,
                )
                write_http_status = response.status_code
        except httpx.TransportError:
            # 传输失败时平台可能已完成写入；只读对账，不盲目重发。
            pass

        try:
            after, _request_id = await read_client.get_webhooks()
        except Exception:
            return {
                "status": "unknown",
                "event_type": TOPIC,
                "write_attempted": True,
                "write_http_status": write_http_status,
                "post_read_succeeded": False,
            }
        confirmed = len(after) == 1 and after[0].event_type == TOPIC and after[0].address == ADDRESS
        return {
            "status": "confirmed" if confirmed else "unknown",
            "event_type": TOPIC,
            "subscription_count": len(after),
            "matching_address_count": sum(item.event_type == TOPIC and item.address == ADDRESS for item in after),
            "write_attempted": True,
            "write_http_status": write_http_status,
            "post_read_succeeded": True,
        }


async def main() -> int:
    try:
        result = await subscribe()
        print(json.dumps(result, separators=(",", ":")))
        return 0 if result["status"] in {"confirmed", "already_present"} else 2
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception:
        # 不把平台响应、Token、shop_cipher 或请求签名写入 Runner 日志。
        print("tiktok_new_message_subscription_failed", file=sys.stderr)
        raise SystemExit(1) from None
