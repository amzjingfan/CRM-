"""Webhook 数据库 Worker 进程。"""

import asyncio
import logging
import time
import uuid

from app.integrations.conversation_sync import process_tiktok_conversation_sync_cycle
from app.integrations.service import claim_and_process_one, cleanup_processed_payloads
from app.shared.config.settings import get_settings
from app.shared.database.session import session_factory
from app.shared.logging.setup import configure_logging


async def _run_conversation_sync() -> None:
    """使用独立数据库会话，不阻塞 Webhook 事件认领。"""
    try:
        async with session_factory() as session:
            await process_tiktok_conversation_sync_cycle(session, get_settings())
    except Exception as error:
        logging.getLogger(__name__).warning(
            "tiktok_conversation_sync_cycle_failed",
            extra={"event": "tiktok_conversation_sync_cycle_failed", "error_type": type(error).__name__},
        )


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
    next_conversation_sync_at = 0.0
    sync_task: asyncio.Task[None] | None = None
    while True:
        try:
            async with session_factory() as session:
                processed = await claim_and_process_one(session, settings.webhook_max_retries)
                cleanup_counter += 1
                if cleanup_counter >= 60:
                    await cleanup_processed_payloads(session, settings.webhook_payload_retention_days)
                    cleanup_counter = 0
            if (
                settings.tiktok_conversation_sync_enabled
                and time.monotonic() >= next_conversation_sync_at
                and (sync_task is None or sync_task.done())
            ):
                sync_task = asyncio.create_task(_run_conversation_sync())
                next_conversation_sync_at = time.monotonic() + settings.tiktok_conversation_sync_poll_seconds
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
