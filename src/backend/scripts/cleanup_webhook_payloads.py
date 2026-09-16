"""按配置清理已成功处理且超过保留期的 Webhook 载荷正文。"""

import asyncio

from app.integrations.service import cleanup_processed_payloads
from app.shared.config.settings import get_settings
from app.shared.database.session import session_factory


async def cleanup() -> None:
    """执行一次可安全重复的载荷清理任务。"""
    async with session_factory() as session:
        count = await cleanup_processed_payloads(session, get_settings().webhook_payload_retention_days)
        print(f"Cleaned webhook payloads: {count}")


if __name__ == "__main__":
    asyncio.run(cleanup())
