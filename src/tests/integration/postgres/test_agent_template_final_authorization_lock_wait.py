"""真实 PostgreSQL 等锁后现时授权；只替换外部模型复核协议。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text
from test_agent_template_application_postgres import env as env_fixture
from test_agent_template_application_postgres import make_preview
from test_agent_template_batches import confirm
from test_agent_templates import api as api_fixture
from test_agent_templates import create

from app.agents.management.config_models import AgentConfig
from app.agents.management.templates import batch, service
from app.agents.management.templates.batch_schemas import BatchConfirmation
from app.agents.management.templates.lifecycle_schemas import TemplateFromAgent, TemplateUpdate
from app.agents.management.templates.models import (
    AgentTemplate,
    AgentTemplateBatch,
    AgentTemplateBatchItem,
    AgentTemplateVersion,
)
from app.audit.models import AuditLog
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

api = api_fixture
env = env_fixture
pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="需要显式专属 PostgreSQL")


async def snapshot(sessions, queries):
    async with sessions() as db:
        return [list((await db.execute(query)).mappings()) for query in queries]


async def after_observed_wait(sessions, model, row_id, operation, mutate):
    """以 pg_blocking_pids 证明请求已被真实行锁阻挡，再提交独立撤权事务。"""
    async with sessions() as blocker:
        await blocker.scalar(select(model).where(model.id == row_id).with_for_update())
        blocker_pid = await blocker.scalar(text("SELECT pg_backend_pid()"))
        pending = asyncio.create_task(operation())
        try:
            async with asyncio.timeout(10):
                while True:
                    async with sessions() as monitor:
                        waiting = await monitor.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                "AND wait_event_type='Lock' AND :blocker = ANY(pg_blocking_pids(pid))"
                            ),
                            {"blocker": blocker_pid},
                        )
                    if waiting:
                        break
                    assert not pending.done(), "请求未等待指定数据库锁"
                    await asyncio.sleep(0.02)
            async with sessions() as mutation:
                await mutate(mutation)
                await mutation.commit()
            await blocker.rollback()
            return await asyncio.wait_for(pending, 10)
        finally:
            await blocker.rollback()
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)


R1_CASES = [
    (action, change)
    for action in ("update", "publish", "archive", "restore", "from-agent")
    for change in ("revoke", "disable", "unchanged")
]
R1_CASES += [("from-agent", change) for change in ("store_disable", "store_delete")]


@pytest.mark.parametrize(("action", "change"), R1_CASES)
async def test_template_writes_recheck_live_authority_after_lock_wait(api, action, change):
    template = await create(api)
    template_id = uuid.UUID(template["id"])
    revision = 1
    if action == "restore":
        async with api.sessions() as db:
            restored = await service.set_template_archived(
                db, await db.get(User, api.admin), template_id, revision, archived=True
            )
            revision = restored.draft_revision
    queries = [
        select(AgentTemplate.__table__).where(AgentTemplate.created_by == api.admin).order_by(AgentTemplate.id),
        select(AgentTemplateVersion.__table__).where(AgentTemplateVersion.template_id == template_id),
        select(AuditLog.__table__).where(AuditLog.actor_id == api.admin).order_by(AuditLog.id),
        select(AgentConfig.__table__).where(AgentConfig.id == api.source),
    ]
    before = await snapshot(api.sessions, queries)

    async def operation():
        async with api.sessions() as db:
            actor = await db.get(User, api.admin)  # 保留认证时 ORM 缓存，撤权由另一个会话提交。
            try:
                if action == "update":
                    return await service.update_template(
                        db, actor, template_id, TemplateUpdate(expected_revision=revision, name="更新")
                    )
                if action == "publish":
                    return await service.publish_template(db, actor, template_id, revision)
                if action in {"archive", "restore"}:
                    return await service.set_template_archived(
                        db, actor, template_id, revision, archived=action == "archive"
                    )
                return await service.template_from_agent(
                    db,
                    actor,
                    TemplateFromAgent(
                        code=f"t{uuid.uuid4().hex}", name="提取", source_agent_id=api.source, source_draft_revision=3
                    ),
                )
            except AppError as error:
                return error

    async def mutate(db):
        if change == "revoke":
            await db.execute(
                delete(user_roles).where(user_roles.c.user_id == api.admin, user_roles.c.store_id.is_(None))
            )
        elif change == "disable":
            (await db.get(User, api.admin)).status = "disabled"
        elif change.startswith("store_"):
            shop = await db.get(Store, api.store)
            if change == "store_disable":
                shop.status = "disabled"
            else:
                shop.deleted_at = datetime.now(UTC)

    result = await after_observed_wait(
        api.sessions,
        AgentConfig if action == "from-agent" else AgentTemplate,
        api.source if action == "from-agent" else template_id,
        operation,
        mutate,
    )
    after = await snapshot(api.sessions, queries)
    if change == "unchanged":
        assert not isinstance(result, AppError)
        assert after != before
    else:
        assert after == before, "失效授权在等锁后仍提交了模板、版本、源配置或成功审计"
        assert isinstance(result, AppError) and result.status_code == (404 if change.startswith("store_") else 403)


R2_CASES = [
    (action, lock, "revoke") for action in ("confirm", "cancel", "retry") for lock in ("template", "batch", "item")
]
R2_CASES += [
    (action, "item", change) for action in ("confirm", "cancel", "retry") for change in ("disable", "creator", "admin")
]


@pytest.mark.parametrize(("action", "lock", "change"), R2_CASES)
async def test_batch_writes_recheck_owner_admin_after_last_lock(env, action, lock, change):
    # 非创建者同时拥有全局 admin 与本店 manage；撤全局行后逐店授权仍合法。
    async with env.sessions() as db:
        admin = await db.scalar(select(Role).where(Role.code == "admin"))
        scoped_role = await db.scalar(select(user_roles.c.role_id).where(user_roles.c.user_id == env.manager))
        await db.execute(
            user_roles.insert(),
            [
                {"user_id": env.manager, "role_id": admin.id, "store_id": None},
                {"user_id": env.actor, "role_id": scoped_role, "store_id": env.store},
            ],
        )
        await db.commit()
    view = await make_preview(env)
    if action != "confirm":
        await confirm(env, view)
        async with env.sessions() as db:
            item = await db.get(AgentTemplateBatchItem, view.items[0].id)
            row = await db.get(AgentTemplateBatch, view.preview_id)
            item.attempt_token, item.lease_expires_at = uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=5)
            item.attempt_count = 1
            if action == "retry":
                item.status, item.error_code = "failed", "review_unavailable"
                row.status = "partial_failed"
            else:
                item.status, row.status = "running", "running"
            await db.commit()
    queries = [
        select(AgentTemplateBatch.__table__).where(AgentTemplateBatch.id == view.preview_id),
        select(AgentTemplateBatchItem.__table__).where(AgentTemplateBatchItem.batch_id == view.preview_id),
        select(AuditLog.__table__).where(AuditLog.resource_id == view.preview_id).order_by(AuditLog.id),
    ]
    before = await snapshot(env.sessions, queries)
    actor_id = env.actor if change == "creator" else env.manager

    async def operation():
        async with env.sessions() as db:
            actor = await db.get(User, actor_id)
            try:
                if action == "confirm":
                    return await batch.confirm_batch(
                        db, actor, BatchConfirmation(preview_id=view.preview_id, confirmation=True), uuid.uuid4().hex
                    )
                if action == "cancel":
                    return await batch.cancel_batch(db, actor, view.preview_id)
                return await batch.retry_failed(db, actor, view.preview_id)
            except AppError as error:
                return error

    async def mutate(db):
        if change in {"revoke", "creator"}:
            await db.execute(
                delete(user_roles).where(user_roles.c.user_id == actor_id, user_roles.c.store_id.is_(None))
            )
        elif change == "disable":
            (await db.get(User, actor_id)).status = "disabled"

    model, key = {
        "template": (AgentTemplate, env.template),
        "batch": (AgentTemplateBatch, view.preview_id),
        "item": (AgentTemplateBatchItem, view.items[0].id),
    }[lock]
    result = await after_observed_wait(env.sessions, model, key, operation, mutate)
    after = await snapshot(env.sessions, queries)
    if change in {"creator", "admin"}:
        assert not isinstance(result, AppError)
        assert after != before
        assert result.status == ("cancelled" if action == "cancel" else "queued")
    else:
        assert after == before, "无权写请求已改变批次/项目/token/requested_by/确认或成功审计"
        assert isinstance(result, AppError) and result.status_code == (403 if change == "disable" else 404)
