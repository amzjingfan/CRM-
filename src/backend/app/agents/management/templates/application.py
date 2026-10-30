"""模型在事务外复核；每店应用由调用者提交唯一短事务。"""

import uuid
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.service import (
    PreparedPublication,
    config_snapshot,
    prepare_publication,
    running_snapshot,
    write_publication,
)
from app.agents.management.templates import preview
from app.agents.management.templates.knowledge import knowledge_dependencies
from app.agents.management.templates.models import AgentTemplate, AgentTemplateBatch, AgentTemplateBatchItem
from app.agents.management.templates.state import snapshot_hash
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


def _conflict(message: str) -> None:
    raise AppError(ErrorCode.RESOURCE_CONFLICT, message, 409)


async def _flush_application(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise AppError(
                ErrorCode.RESOURCE_CONFLICT, "Agent 编码、模板关联或发布版本发生并发冲突，请重新预览", 409
            ) from error
        raise


def _publication_needed(snapshot: dict[str, object]) -> bool:
    return (
        bool(snapshot["publish"])
        and running_snapshot(cast(dict[str, JsonValue], snapshot["config"])) != snapshot["published_snapshot"]
    )


async def review_application(item: AgentTemplateBatchItem, settings: Settings) -> PreparedPublication | None:
    """只读取已脱离会话的冻结内容；调用方必须先结束读事务再调用模型。"""
    if snapshot_hash(item.target_config_json) != item.target_config_hash or not item.target_config_json.get("valid"):
        _conflict("应用快照无效，请重新预览")
    if not _publication_needed(item.target_config_json):
        return None
    return await prepare_publication(cast(dict[str, JsonValue], item.target_config_json["config"]), settings)


async def _validate_item(
    session: AsyncSession, user: User, batch: AgentTemplateBatch, item: AgentTemplateBatchItem, *, lock: bool
) -> AgentConfig | None:
    await preview.authorize_store(session, user, item.store_id)
    if item.batch_id != batch.id or batch.cancel_requested or batch.status in {"cancelled", "canceled"}:
        _conflict("批次已取消或项目不属于此批次")
    if snapshot_hash(batch.preview_json) != batch.preview_hash:
        _conflict("批次预览快照校验失败")
    if (
        batch.preview_json.get("template_id") != str(batch.template_id)
        or batch.preview_json.get("template_version") != batch.template_version
    ):
        _conflict("批次模板与冻结预览不一致")
    manifest = batch.preview_json.get("items", [])
    if not isinstance(manifest, list) or not any(
        isinstance(row, dict)
        and row.get("id") == str(item.id)
        and row.get("target_config_hash") == item.target_config_hash
        for row in manifest
    ):
        _conflict("项目不在冻结批次中")
    snapshot = item.target_config_json
    if not snapshot.get("valid") or snapshot_hash(snapshot) != item.target_config_hash:
        _conflict("应用快照无效，请重新预览")
    if (
        snapshot.get("store_id") != str(item.store_id)
        or snapshot.get("agent_id") != (str(item.agent_config_id) if item.agent_config_id else None)
        or any(
            snapshot.get(key) != getattr(item, key)
            for key in ("expected_revision", "expected_published_version", "expected_status")
        )
    ):
        _conflict("项目目标或原始版本与冻结预览不一致")
    _, version, _ = await preview.template_version(session, batch.template_id, batch.template_version)
    if version.content_sha256 != snapshot.get("template_hash") or preview.catalog_hash() != snapshot.get(
        "catalog_hash"
    ):
        _conflict("模板或模型工具目录依赖已变化，请重新预览")
    config = None
    if item.agent_config_id is not None:
        statement = (
            select(AgentConfig)
            .where(
                AgentConfig.id == item.agent_config_id,
                AgentConfig.store_id == item.store_id,
                AgentConfig.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        config = await session.scalar(statement)
        if config is None:
            _conflict("Agent 已不存在")
        assert config is not None
        if (
            config.draft_revision != item.expected_revision
            or config.published_version != item.expected_published_version
            or config.status != item.expected_status
            or config_snapshot(config) != snapshot.get("original_config")
        ):
            _conflict("Agent 已变化，请重新预览")
        if snapshot["action"] == "adopt" and config.template_id is not None:
            _conflict("Agent 已关联模板")
        if snapshot["action"] == "update" and config.template_id != batch.template_id:
            _conflict("Agent 模板关联已变化")
    full_target = cast(dict[str, JsonValue], snapshot["config"])
    linked = await session.scalar(
        select(AgentConfig.id).where(
            AgentConfig.store_id == item.store_id,
            AgentConfig.template_id == batch.template_id,
            AgentConfig.deleted_at.is_(None),
        )
    )
    collision = await session.scalar(
        select(AgentConfig.id).where(
            AgentConfig.store_id == item.store_id,
            AgentConfig.code == full_target["code"],
            AgentConfig.deleted_at.is_(None),
        )
    )
    if (linked is not None and (config is None or linked != config.id)) or (
        collision is not None and (config is None or collision != config.id)
    ):
        _conflict("Agent 编码或模板关联已冲突，请重新预览")
    if snapshot["binding_requested"] and item.store_id not in await allowed_store_ids(session, user, "knowledge.view"):
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有本店知识绑定权限", 403)
    dependencies, issues = await knowledge_dependencies(
        session,
        item.store_id,
        cast(list[str], full_target["knowledge_file_ids"]),
        publish=bool(snapshot["publish"]),
        lock=lock,
    )
    if issues or dependencies != snapshot.get("dependencies"):
        _conflict("知识有效版本或审批已变化，请重新预览")
    # 等待配置/文件锁后再读授权，防止等待期间的撤权仍被早先结果覆盖。
    await preview.authorize_store(session, user, item.store_id)
    if snapshot["binding_requested"] and item.store_id not in await allowed_store_ids(session, user, "knowledge.view"):
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有本店知识绑定权限", 403)
    return config


async def validate_preview_item(
    session: AsyncSession, user: User, batch: AgentTemplateBatch, item: AgentTemplateBatchItem
) -> None:
    """确认和重试可复用的现时校验，不提交、不调用模型。"""
    await _validate_item(session, user, batch, item, lock=False)


async def apply_item(
    session: AsyncSession,
    user: User,
    batch: AgentTemplateBatch,
    item: AgentTemplateBatchItem,
    attempt_token: uuid.UUID,
    prepared_publication: PreparedPublication | None,
) -> None:
    """Template→Batch→Item→Config→Knowledge 锁序；任何异常由调用者回滚。"""
    template_id, batch_id, item_id = batch.template_id, batch.id, item.id
    await session.scalar(
        select(AgentTemplate)
        .where(AgentTemplate.id == template_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked_batch = await session.scalar(
        select(AgentTemplateBatch)
        .where(AgentTemplateBatch.id == batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked_item = await session.scalar(
        select(AgentTemplateBatchItem)
        .where(AgentTemplateBatchItem.id == item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_batch is None or locked_item is None:
        _conflict("应用项目不存在")
    assert locked_batch is not None and locked_item is not None
    batch, item = locked_batch, locked_item
    if batch.template_id != template_id:
        _conflict("批次模板已变化")
    now = datetime.now(UTC)
    confirmation = batch.confirmation_json
    if (
        batch.confirmed_by is None
        or batch.status not in {"running", "queued"}
        or snapshot_hash(confirmation) != batch.confirmation_hash
        or confirmation.get("preview_id") != str(batch.id)
        or confirmation.get("preview_hash") != batch.preview_hash
        or confirmation.get("confirmed") is not True
        or confirmation.get("actor_id") != str(batch.confirmed_by)
    ):
        _conflict("批次尚未确认或不可执行")
    if (
        item.status != "running"
        or item.attempt_token != attempt_token
        or item.lease_expires_at is None
        or item.lease_expires_at <= now
        or item.requested_by != user.id
    ):
        _conflict("执行令牌或租约已失效")
    config = await _validate_item(session, user, batch, item, lock=True)
    # 获取配置和知识锁可能等待到租约过期，必须在真正写入前重新围栏。
    if item.lease_expires_at is None or item.lease_expires_at <= datetime.now(UTC):
        _conflict("执行租约已失效")
    snapshot = item.target_config_json
    target = cast(dict[str, JsonValue], snapshot["config"])
    needs_publication = _publication_needed(snapshot)
    if needs_publication and prepared_publication is None:
        _conflict("发布缺少准确模型复核凭证")
    if config is None:
        config = AgentConfig(
            id=uuid.uuid4(),
            store_id=item.store_id,
            name=str(target["name"]),
            code=str(target["code"]),
            created_by=user.id,
            status="disabled",
            draft_revision=1,
        )
        session.add(config)
    else:
        config.draft_revision += 1
    config.name, config.code, config.description = (
        str(target["name"]),
        str(target["code"]),
        cast(str | None, target["description"]),
    )
    config.draft_model_provider, config.draft_model_name = (
        cast(str | None, target["model_provider"]),
        cast(str | None, target["model_name"]),
    )
    config.draft_prompt_sections = cast(dict[str, str], target["prompt_sections"])
    config.enabled_tools = cast(list[str], target["enabled_tools"])
    scope = dict(config.knowledge_scope or {})
    scope.update(
        {"mode": "bound_files_only", "agent_type": target["agent_type"], "file_ids": target["knowledge_file_ids"]}
    )
    if target["reply_profile"] is not None:
        scope["reply_profile"] = target["reply_profile"]
    config.knowledge_scope = scope
    config.template_id = batch.template_id
    config.template_state_json = cast(dict[str, object], snapshot["template_state"])
    await _flush_application(session)
    if item.lease_expires_at is None or item.lease_expires_at <= datetime.now(UTC):
        _conflict("执行租约已失效")
    if needs_publication:
        assert prepared_publication is not None
        write_publication(session, config, user.id, prepared_publication)
    if snapshot["enable_after_publish"]:
        config.status = "enabled"
    item.status = "succeeded"
    item.result_agent_config_id, item.result_version = config.id, config.published_version
    item.result_json = {
        "agent_id": str(config.id),
        "version": config.published_version,
        "draft_revision": config.draft_revision,
        "published": needs_publication,
        "target_config_hash": item.target_config_hash,
    }
    item.finished_at = now
    item.error_code = None
    session.add(
        AuditLog(
            store_id=item.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.template.apply",
            resource_type="agent_config",
            resource_id=config.id,
            after_data={
                "batch_id": str(batch.id),
                "item_id": str(item.id),
                "template_id": str(batch.template_id),
                "template_version": batch.template_version,
                **item.result_json,
            },
            result="succeeded",
        )
    )
    await _flush_application(session)
