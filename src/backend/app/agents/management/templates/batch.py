"""确认、取消和失败重试拥有短事务；不在 HTTP 中执行模型。"""

import math
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.templates import application, preview
from app.agents.management.templates.batch_schemas import (
    BatchConfirmation,
    BatchItemView,
    BatchListView,
    BatchPagination,
    BatchSummary,
    BatchView,
)
from app.agents.management.templates.models import AgentTemplate, AgentTemplateBatch, AgentTemplateBatchItem
from app.agents.management.templates.service import can_manage_templates
from app.agents.management.templates.state import snapshot_hash
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store

RETRYABLE_ERRORS = frozenset({"review_unavailable", "processing_unavailable"})


def conflict() -> None:
    raise AppError(ErrorCode.RESOURCE_CONFLICT, "批次或预览已失效，请重新预览", 409)


async def active_actor(session: AsyncSession, actor_id: uuid.UUID | None) -> User:
    user = await session.scalar(
        select(User).where(User.id == actor_id, User.status == "active").execution_options(populate_existing=True)
    )
    if user is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "执行用户不可用", 403)
    return user


async def accessible(session: AsyncSession, user: User, batch_id: uuid.UUID) -> AgentTemplateBatch:
    user = await active_actor(session, user.id)
    row = await session.get(AgentTemplateBatch, batch_id)
    if row is None or (row.created_by != user.id and not await can_manage_templates(session, user)):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "批次不存在", 404)
    return row


async def lock_batch(
    session: AsyncSession, row: AgentTemplateBatch, *, skip_locked: bool = False
) -> AgentTemplateBatch | None:
    # 全部路径共用 Template→Batch→Item，模型期间绝不持有这些锁。
    template = await session.scalar(
        select(AgentTemplate).where(AgentTemplate.id == row.template_id).with_for_update(skip_locked=skip_locked)
    )
    if template is None:
        return None
    locked = await session.scalar(
        select(AgentTemplateBatch)
        .where(AgentTemplateBatch.id == row.id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )

    return locked


async def locked_items(session: AsyncSession, row: AgentTemplateBatch) -> list[AgentTemplateBatchItem]:
    return list(
        (
            await session.scalars(
                select(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.batch_id == row.id)
                .order_by(AgentTemplateBatchItem.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )


def audit(session: AsyncSession, user: User, row: AgentTemplateBatch, action: str, count: int) -> None:
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=user.id,
            action=action,
            resource_type="agent_template_batch",
            resource_id=row.id,
            after_data={"item_count": count},
            result="succeeded",
        )
    )


async def finalize(session: AsyncSession, row: AgentTemplateBatch) -> None:
    await session.flush()
    statuses = list(
        (
            await session.scalars(
                select(AgentTemplateBatchItem.status).where(AgentTemplateBatchItem.batch_id == row.id)
            )
        ).all()
    )
    if any(status in {"pending", "running"} for status in statuses):
        return
    row.status = (
        "cancelled"
        if row.cancel_requested
        else ("partial_failed" if any(status in {"failed", "needs_repreview"} for status in statuses) else "completed")
    )
    row.finished_at = datetime.now(UTC)


def pagination(page: int, page_size: int, total: int) -> BatchPagination:
    return BatchPagination(page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size))


async def summary(session: AsyncSession, row: AgentTemplateBatch) -> BatchSummary:
    counts = Counter(
        (
            await session.scalars(
                select(AgentTemplateBatchItem.status).where(AgentTemplateBatchItem.batch_id == row.id)
            )
        ).all()
    )
    return BatchSummary(
        id=row.id,
        template_id=row.template_id,
        template_version=row.template_version,
        parent_batch_id=row.parent_batch_id,
        status=row.status,
        cancel_requested=row.cancel_requested,
        counts=dict(counts),
        created_at=row.created_at,
        confirmed_at=row.confirmed_at,
        finished_at=row.finished_at,
        processor_enabled=get_settings().agent_template_processor_enabled,
    )


async def get_batch(
    session: AsyncSession, user: User, batch_id: uuid.UUID, *, page: int = 1, page_size: int = 50
) -> BatchView:
    row = await accessible(session, user, batch_id)
    visible = await allowed_store_ids(session, user, "agent.manage") | await allowed_store_ids(
        session, user, "agent.view"
    )
    items = list(
        (
            await session.scalars(
                select(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.batch_id == row.id)
                .order_by(AgentTemplateBatchItem.created_at, AgentTemplateBatchItem.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    total = (
        await session.scalar(
            select(func.count()).select_from(AgentTemplateBatchItem).where(AgentTemplateBatchItem.batch_id == row.id)
        )
        or 0
    )
    names = {
        key: name
        for key, name in (
            await session.execute(
                select(Store.id, Store.name).where(Store.id.in_({i.store_id for i in items} & visible))
            )
        ).all()
    }
    result = []
    for item in items:
        allowed = item.store_id in visible
        result.append(
            BatchItemView(
                id=item.id,
                store_id=item.store_id if allowed else None,
                store_name=names.get(item.store_id, "无权查看店铺"),
                status=item.status,
                action=str(item.target_config_json.get("action")) if allowed else None,
                agent_id=item.agent_config_id if allowed else None,
                result_agent_id=item.result_agent_config_id if allowed else None,
                old_published_version=item.expected_published_version if allowed else None,
                result_version=item.result_version if allowed else None,
                error_code=item.error_code,
                retryable=item.status == "failed" and item.error_code in RETRYABLE_ERRORS,
                started_at=item.started_at,
                finished_at=item.finished_at,
                attempt_count=item.attempt_count,
                preview=cast(JsonValue, item.target_config_json.get("view")) if allowed else None,
            )
        )
    return BatchView(
        **(await summary(session, row)).model_dump(), items=result, pagination=pagination(page, page_size, total)
    )


async def list_batches(session: AsyncSession, user: User, *, page: int = 1, page_size: int = 20) -> BatchListView:
    await active_actor(session, user.id)
    statement = select(AgentTemplateBatch)
    if not await can_manage_templates(session, user):
        statement = statement.where(AgentTemplateBatch.created_by == user.id)
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = (
        await session.scalars(
            statement.order_by(AgentTemplateBatch.created_at.desc(), AgentTemplateBatch.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return BatchListView(
        items=[await summary(session, row) for row in rows], pagination=pagination(page, page_size, total)
    )


async def confirm_batch(session: AsyncSession, user: User, payload: BatchConfirmation, key: str) -> BatchView:
    if not key.strip() or len(key) > 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Idempotency-Key 不合法", 422)
    found = await accessible(session, user, payload.preview_id)
    row = await lock_batch(session, found)
    assert row is not None
    duplicate = await session.scalar(
        select(AgentTemplateBatch).where(
            AgentTemplateBatch.created_by == row.created_by, AgentTemplateBatch.idempotency_key == key
        )
    )
    if duplicate is not None and duplicate.id != row.id:
        conflict()
    if row.status != "preview":
        if row.confirmed_by is None or row.idempotency_key != key:
            conflict()
        return await get_batch(session, user, row.id)
    items = await locked_items(session, row)
    # 最后一个项目锁也可能等待；逐店管理权限不能替代批次创建者/现时管理员资格。
    await accessible(session, user, row.id)
    if not items:
        conflict()
    try:
        for item in items:
            await application.validate_preview_item(session, user, row, item)
    except AppError as error:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "预览依赖或权限已变化，请重新预览", 409) from error
    row.status, row.idempotency_key = "queued", key
    row.confirmed_by, row.confirmed_at = user.id, datetime.now(UTC)
    row.confirmation_json = {
        "preview_id": str(row.id),
        "preview_hash": row.preview_hash,
        "confirmed": True,
        "actor_id": str(user.id),
    }
    row.confirmation_hash = snapshot_hash(row.confirmation_json)
    for item in items:
        item.requested_by = user.id
    audit(session, user, row, "agent.template.batch.confirm", len(items))
    batch_id = row.id
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已被其他预览使用", 409) from error
    return await get_batch(session, user, batch_id)


async def cancel_batch(session: AsyncSession, user: User, batch_id: uuid.UUID) -> BatchView:
    found = await accessible(session, user, batch_id)
    row = await lock_batch(session, found)
    assert row is not None
    items = await locked_items(session, row)
    await accessible(session, user, row.id)
    for item in items:
        await preview.authorize_store(session, user, item.store_id)
    if row.status not in {"completed", "partial_failed", "cancelled"}:
        row.cancel_requested, row.cancelled_at = True, datetime.now(UTC)
        for item in items:
            if item.status in {"pending", "running"}:
                item.status, item.finished_at = "cancelled", datetime.now(UTC)
                item.attempt_token, item.lease_expires_at = None, None
        await finalize(session, row)
        audit(session, user, row, "agent.template.batch.cancel", len(items))
        await session.commit()
    return await get_batch(session, user, batch_id)


async def retry_failed(session: AsyncSession, user: User, batch_id: uuid.UUID) -> BatchView:
    found = await accessible(session, user, batch_id)
    row = await lock_batch(session, found)
    assert row is not None
    if row.cancel_requested or row.confirmed_by is None:
        conflict()
    items = [
        item
        for item in await locked_items(session, row)
        if item.status == "failed" and item.error_code in RETRYABLE_ERRORS
    ]
    await accessible(session, user, row.id)
    for item in items:
        await preview.authorize_store(session, user, item.store_id)
        try:
            await application.validate_preview_item(session, user, row, item)
        except AppError as error:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "失败项目依赖已变化，请重新预览续接", 409) from error
    if not items:
        conflict()
    for item in items:
        item.status, item.requested_by = "pending", user.id
        item.error_code, item.finished_at = None, None
        item.attempt_token, item.lease_expires_at = None, None
    row.status, row.finished_at = "queued", None
    audit(session, user, row, "agent.template.batch.retry", len(items))
    await session.commit()
    return await get_batch(session, user, batch_id)
