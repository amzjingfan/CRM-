"""在 staging 对精确已授权店铺回填真实客服会话。"""

import argparse
import asyncio
import json
import uuid

from app.integrations.conversation_sync import SyncSummary, sync_tiktok_channel
from app.integrations.tiktok_read import TikTokReadClient
from app.shared.config.settings import get_settings
from app.shared.database.session import engine, session_factory
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount


async def sync_channel(
    channel_id: uuid.UUID, expected_store_id: uuid.UUID, *, refresh_rich: bool = False
) -> SyncSummary:
    """只接受 staging、精确渠道和内部店铺，输出由调用者保持低敏。"""
    settings = get_settings()
    if settings.app_env != "staging":
        raise AppError(ErrorCode.PERMISSION_DENIED, "回填命令仅允许 staging", 403)
    async with session_factory() as session:
        channel = await session.get(ChannelAccount, channel_id)
        if channel is None or channel.store_id != expected_store_id:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "授权渠道不存在", 404)
        return await sync_tiktok_channel(
            session, channel, TikTokReadClient(settings, channel), refresh_rich=refresh_rich
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="回填 staging 已授权 TikTok 客服会话；不执行平台写入")
    parser.add_argument("--channel-id", required=True, type=uuid.UUID)
    parser.add_argument("--store-id", required=True, type=uuid.UUID)
    parser.add_argument("--refresh-rich", action="store_true", help="重读该渠道历史消息并补齐旧占位卡片")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    try:
        summary = await sync_channel(args.channel_id, args.store_id, refresh_rich=args.refresh_rich)
        print(json.dumps({"event": "tiktok_conversation_sync_succeeded", **summary.__dict__}, separators=(",", ":")))
        return 0
    except Exception as error:
        # 第三方异常链可能包含客户正文；命令行只报告固定错误类别。
        print(json.dumps({"event": "tiktok_conversation_sync_failed", "error_type": type(error).__name__}))
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
