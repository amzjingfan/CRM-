"""Webhook 数据库 Worker 进程。"""

import asyncio
import logging
import uuid

from app.integrations.service import claim_and_process_one, cleanup_processed_payloads
from app.shared.config.settings import get_settings
from app.shared.database.session import session_factory
from app.shared.logging.setup import configure_logging


async def run_worker() -> None:
    """持续认领事件；空闲时短暂等待，不使用外部任务队列。"""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    worker_trace_id = str(uuid.uuid4())
    logger.info(
        "Webhook Worker 启动",
        extra={"trace_id": worker_trace_id, "event": "webhook_worker_started"},
    )
    cleanup_counter = 0
    while True:
        try:
            async with session_factory() as session:
                processed = await claim_and_process_one(session, settings.webhook_max_retries)
                cleanup_counter += 1
                if cleanup_counter >= 60:
                    await cleanup_processed_payloads(session, settings.webhook_payload_retention_days)
                    cleanup_counter = 0
        except Exception:
            logger.exception(
                "Webhook Worker 循环失败，将继续重试",
                extra={"trace_id": worker_trace_id, "event": "webhook_worker_cycle_failed"},
            )
            processed = False
        if not processed:
            await asyncio.sleep(settings.webhook_poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_worker())
