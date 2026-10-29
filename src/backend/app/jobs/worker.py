"""知识导入与营销调度 Worker。"""

import asyncio
import logging
import time
import uuid

from app.agents.core.factory import build_knowledge_vectorization_service
from app.integrations.oauth_service import (
    cleanup_tiktok_oauth_jobs,
    process_tiktok_oauth_job,
    process_tiktok_token_refresh_cycle,
)
from app.knowledge_base.importer import process_import_job
from app.shared.config.settings import get_settings
from app.shared.database.session import session_factory
from app.shared.logging.setup import configure_logging

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    """公平轮询知识、营销和指标任务；单次失败不终止进程。"""
    settings = get_settings()
    configure_logging(settings.log_level)
    worker_trace_id = str(uuid.uuid4())
    logger.info("Jobs Worker 启动", extra={"trace_id": worker_trace_id, "event": "jobs_worker_started"})
    vectorization_service = build_knowledge_vectorization_service(settings) if settings.embedding_enabled else None
    next_marketing_at = 0.0
    next_metrics_at = 0.0
    next_tiktok_refresh_at = 0.0
    next_oauth_cleanup_at = 0.0
    next_logistics_scan_at = 0.0
    while True:
        processed = False
        try:
            async with session_factory() as session:
                processed = await process_tiktok_oauth_job(session, settings)
            async with session_factory() as session:
                processed = await process_import_job(session) or processed
            if settings.logistics_notifications_enabled and time.monotonic() >= next_logistics_scan_at:
                from app.agents.tools.logistics_updates.worker import process_logistics_notification_cycle

                logistics_processed = await process_logistics_notification_cycle(session_factory, settings)
                processed = logistics_processed or processed
                # 这里只查本地到期台账；每单真正读取前另有至少八小时持久占位。
                next_logistics_scan_at = time.monotonic() + (0 if logistics_processed else 60)
            if vectorization_service is not None:
                async with session_factory() as session:
                    vectorization_result = await vectorization_service.process_cycle(session)
                processed = vectorization_result.claimed > 0 or processed
            # 营销按独立 60 秒节奏扫描，知识导入仍可保持更短轮询延迟。
            if time.monotonic() >= next_marketing_at:
                from app.marketing.worker import process_marketing_cycle

                async with session_factory() as session:
                    processed = await process_marketing_cycle(session, settings) or processed
                next_marketing_at = time.monotonic() + settings.marketing_poll_seconds
            if time.monotonic() >= next_metrics_at:
                from app.dashboard.aggregation import aggregate_recent_metrics

                async with session_factory() as session:
                    await aggregate_recent_metrics(session)
                next_metrics_at = time.monotonic() + settings.metrics_poll_seconds
            if time.monotonic() >= next_tiktok_refresh_at:
                async with session_factory() as session:
                    refreshed = await process_tiktok_token_refresh_cycle(session, settings)
                processed = refreshed > 0 or processed
                next_tiktok_refresh_at = time.monotonic() + settings.tiktok_token_refresh_poll_seconds
            if time.monotonic() >= next_oauth_cleanup_at:
                async with session_factory() as session:
                    await cleanup_tiktok_oauth_jobs(session)
                next_oauth_cleanup_at = time.monotonic() + 3600
        except Exception:
            logger.exception(
                "Jobs 后台任务执行失败",
                extra={"trace_id": worker_trace_id, "event": "jobs_cycle_failed"},
            )
        await asyncio.sleep(0 if processed else settings.jobs_poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_worker())
