"""现有后端进程内 SQL 队列；租约围栏保护重启和迟到结果。"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.management.templates import application, batch
from app.agents.management.templates.models import AgentTemplateBatch, AgentTemplateBatchItem
from app.agents.management.templates.state import snapshot_hash
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError

logger = logging.getLogger(__name__)


class TemplateBatchProcessor:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        self.poll_seconds = float(getattr(settings, "agent_template_processor_poll_seconds", 2.0))
        budget = min(
            float(getattr(settings, "llm_timeout_seconds", 120)),
            float(getattr(settings, "request_timeout_seconds", 120)),
        )
        self.review_budget = budget
        self.lease_seconds = max(float(getattr(settings, "agent_template_processor_lease_seconds", 180)), budget + 30)

    def start(self) -> None:
        if getattr(self.settings, "agent_template_processor_enabled", True) and self._task is None:
            self._task = asyncio.create_task(self._run_loop(), name="agent-template-batches")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        # 短健康检查生命周期不会因默认轮询立刻建立数据库连接。
        await asyncio.sleep(self.poll_seconds)
        while True:
            try:
                worked = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # 驱动错误内容可能带 SQL 参数，仅记录固定事件，不打印异常正文。
                logger.warning("模板批次轮询暂不可用", extra={"event": "template_batch_poll_unavailable"})
                worked = False
            if not worked:
                await asyncio.sleep(self.poll_seconds)

    async def _claim(self) -> tuple[AgentTemplateBatchItem | None, bool]:
        async with self.session_factory() as session:
            now = datetime.now(UTC)
            available = or_(
                AgentTemplateBatchItem.status == "pending",
                and_(AgentTemplateBatchItem.status == "running", AgentTemplateBatchItem.lease_expires_at <= now),
            )
            candidates = (
                await session.scalars(
                    select(AgentTemplateBatch.id)
                    .where(
                        AgentTemplateBatch.status.in_(["queued", "running"]),
                        AgentTemplateBatch.cancel_requested.is_(False),
                        select(AgentTemplateBatchItem.id)
                        .where(AgentTemplateBatchItem.batch_id == AgentTemplateBatch.id, available)
                        .exists(),
                    )
                    .order_by(AgentTemplateBatch.created_at, AgentTemplateBatch.id)
                    .limit(50)
                )
            ).all()
            for candidate_id in candidates:
                candidate = await session.get(AgentTemplateBatch, candidate_id)
                if candidate is None:
                    continue
                row = await batch.lock_batch(session, candidate, skip_locked=True)
                if row is None:
                    await session.rollback()
                    continue
                if row.status not in {"queued", "running"} or row.cancel_requested:
                    await session.rollback()
                    continue
                item = await session.scalar(
                    select(AgentTemplateBatchItem)
                    .where(AgentTemplateBatchItem.batch_id == row.id, available)
                    .order_by(AgentTemplateBatchItem.created_at, AgentTemplateBatchItem.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                    .execution_options(populate_existing=True)
                )
                if item is None:
                    await session.rollback()
                    continue
                item.status, item.attempt_token = "running", uuid.uuid4()
                item.lease_expires_at = datetime.now(UTC) + timedelta(seconds=self.lease_seconds)
                item.attempt_count += 1
                item.started_at, item.finished_at, item.error_code = datetime.now(UTC), None, None
                row.status = "running"
                try:
                    with session.no_autoflush:
                        actor = await batch.active_actor(session, item.requested_by)
                        confirmation = row.confirmation_json
                        if (
                            row.confirmed_by is None
                            or snapshot_hash(confirmation) != row.confirmation_hash
                            or confirmation
                            != {
                                "preview_id": str(row.id),
                                "preview_hash": row.preview_hash,
                                "confirmed": True,
                                "actor_id": str(row.confirmed_by),
                            }
                        ):
                            batch.conflict()
                        await application.validate_preview_item(session, actor, row, item)
                except AppError:
                    item.status, item.error_code, item.finished_at = (
                        "needs_repreview",
                        "preview_invalid",
                        datetime.now(UTC),
                    )
                    item.lease_expires_at = None
                    await batch.finalize(session, row)
                    await session.commit()
                    return None, True
                # claim仍独占项目，外部复核预算从验证完成后起算，不能被数据库等待耗尽。
                item.lease_expires_at = datetime.now(UTC) + timedelta(seconds=self.lease_seconds)
                await session.commit()
                # expire_on_commit=False，离开上下文后模型仅使用冻结 JSON。
                return item, True
            return None, False

    async def _failure(self, item: AgentTemplateBatchItem, error: Exception) -> None:
        async with self.session_factory() as session:
            row = await session.get(AgentTemplateBatch, item.batch_id)
            if row is None:
                return
            row = await batch.lock_batch(session, row)
            assert row is not None
            current = await session.scalar(
                select(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.id == item.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if current is None or current.status != "running" or current.attempt_token != item.attempt_token:
                return
            # 已过期执行者也不能把新认领前的租约改成失败；保留恢复资格。
            if current.lease_expires_at is None or current.lease_expires_at <= datetime.now(UTC):
                return
            if row.cancel_requested:
                current.status, current.error_code = "cancelled", None
            elif (
                isinstance(error, (TimeoutError, ConnectionError))
                or isinstance(error, AppError)
                and error.status_code in {502, 503, 504}
            ):
                current.status, current.error_code = "failed", "review_unavailable"
            elif isinstance(error, AppError):
                current.status, current.error_code = (
                    "needs_repreview",
                    "preview_invalid" if error.status_code != 422 else "configuration_rejected",
                )
            else:
                # 未知程序错误允许人工同hash重试，永不保存异常正文/Prompt。
                current.status, current.error_code = "failed", "processing_unavailable"
            current.finished_at, current.lease_expires_at = datetime.now(UTC), None
            await batch.finalize(session, row)
            await session.commit()

    async def run_once(self) -> bool:
        item, worked = await self._claim()
        if item is None:
            return worked
        try:
            async with asyncio.timeout(self.review_budget):
                prepared = await application.review_application(item, self.settings)
            async with self.session_factory() as session:
                row = await session.get(AgentTemplateBatch, item.batch_id)
                assert row is not None and item.attempt_token is not None
                # 最终 apply 自己重取锁并重读配置/依赖；操作者来自本项目请求人。
                actor = await batch.active_actor(session, item.requested_by)
                await application.apply_item(session, actor, row, item, item.attempt_token, prepared)
                await batch.finalize(session, row)
                await session.commit()
        except asyncio.CancelledError:
            # 中断未提交工作不落假失败，重启通过有限lease恢复。
            raise
        except Exception as error:
            await self._failure(item, error)
        return True
