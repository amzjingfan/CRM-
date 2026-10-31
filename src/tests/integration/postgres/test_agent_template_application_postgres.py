"""专用 PostgreSQL 验证冻结预览和每店原子应用；模型复核全量替身。"""

import asyncio
import copy
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from _support import require_isolated_postgres_url
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.templates import application, preview
from app.agents.management.templates.models import (
    AgentTemplate,
    AgentTemplateBatch,
    AgentTemplateBatchItem,
    AgentTemplateVersion,
)
from app.agents.management.templates.schemas import ApplicationPreviewRequest, TemplateConfig
from app.agents.management.templates.service import config_hash
from app.agents.management.templates.state import snapshot_hash
from app.agents.prompts.sections import SECTION_TITLES
from app.audit.models import AuditLog
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.shared.database import models as all_models  # noqa: F401
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="需要专用 PostgreSQL")
ALLOWED_TEST_DATABASE_URLS = {
    "postgresql+asyncpg://crm_test:crm_test@localhost:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030",
}
SECTIONS = {key: "只处理授权业务，证据不足交人工。" for key, _ in SECTION_TITLES}


@pytest.fixture
async def env(monkeypatch):
    require_isolated_postgres_url(URL)
    assert URL in ALLOWED_TEST_DATABASE_URLS or URL == os.getenv("AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL")
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor, manager, store, other, template, file_id, file_other, role_id = [uuid.uuid4() for _ in range(8)]
    settings = SimpleNamespace(
        llm_primary_provider="deepseek", llm_primary_model="test-model", llm_fallback_provider="", llm_fallback_model=""
    )
    monkeypatch.setattr(preview, "get_settings", lambda: settings)
    review = AsyncMock(return_value=(10, 2))
    from app.agents.management import service as publish_service

    monkeypatch.setattr(publish_service, "review_configured_prompt", review)
    config = TemplateConfig(
        default_agent_name="客服",
        suggested_code="service",
        model_provider="deepseek",
        model_name="test-model",
        prompt_sections=SECTIONS,
    )
    async with sessions() as db:
        db.add_all([Store(id=i, code=i.hex, name="测试店") for i in (store, other)])
        db.add_all([User(id=i, login_name=i.hex[:16], name="测试", password_hash="test") for i in (actor, manager)])
        db.add(Role(id=role_id, code=role_id.hex, name="仅管理"))
        await db.flush()
        admin = await db.scalar(select(Role).where(Role.code == "admin"))
        permission = await db.scalar(select(Permission).where(Permission.code == "agent.manage"))
        await db.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission.id))
        await db.execute(
            user_roles.insert(),
            [
                {"user_id": actor, "role_id": admin.id, "store_id": None},
                {"user_id": manager, "role_id": role_id, "store_id": store},
            ],
        )
        db.add(
            AgentTemplate(
                id=template,
                code=template.hex,
                name="模板",
                draft_config_json=config.model_dump(mode="json"),
                published_version=1,
                created_by=actor,
            )
        )
        await db.flush()
        db.add(
            AgentTemplateVersion(
                template_id=template,
                version=1,
                config_json=config.model_dump(mode="json"),
                content_sha256=config_hash(config),
            )
        )
        for fid, sid in ((file_id, store), (file_other, other)):
            db.add(
                KnowledgeFile(
                    id=fid, store_id=sid, original_filename="私密名称", filename_key=fid.hex, active_version_number=1
                )
            )
            await db.flush()
            db.add(
                KnowledgeFileVersion(
                    store_id=sid,
                    file_id=fid,
                    version_number=1,
                    source_object_key="synthetic",
                    file_sha256="a" * 64,
                    media_type="text/plain",
                    config_json={},
                    status="ready",
                    publication_approval="approved_for_internal_review",
                    approved_by=actor,
                    approved_at=datetime.now(UTC),
                    created_by=actor,
                )
            )
        await db.commit()
    try:
        yield SimpleNamespace(
            sessions=sessions,
            actor=actor,
            manager=manager,
            store=store,
            other=other,
            template=template,
            file=file_id,
            file_other=file_other,
            settings=settings,
            config=config,
            review=review,
        )
    finally:
        async with sessions() as db:
            await db.execute(delete(AgentTemplateBatch).where(AgentTemplateBatch.template_id == template))
            await db.execute(delete(AuditLog).where(AuditLog.actor_id.in_([actor, manager])))
            await db.execute(delete(Store).where(Store.id.in_([store, other])))
            await db.execute(delete(AgentTemplate).where(AgentTemplate.id == template))
            await db.execute(delete(User).where(User.id.in_([actor, manager])))
            await db.execute(delete(Role).where(Role.id == role_id))
            await db.commit()
        await engine.dispose()


async def make_preview(env, *, actor=None, **changes):
    request = ApplicationPreviewRequest.model_validate(
        {"template_version": 1, "items": [{"store_id": str(env.store), "action": "create", **changes}]}
    )
    async with env.sessions() as db:
        user = await db.get(User, actor or env.actor)
        return await preview.create_application_preview(db, user, env.template, request)


async def claimed(env, view):
    async with env.sessions() as db:
        batch = await db.get(AgentTemplateBatch, view.preview_id)
        item = await db.get(AgentTemplateBatchItem, view.items[0].id)
        batch.status = "running"
        batch.confirmed_by = env.actor
        batch.confirmation_json = {
            "preview_id": str(batch.id),
            "preview_hash": batch.preview_hash,
            "confirmed": True,
            "actor_id": str(env.actor),
        }
        batch.confirmation_hash = snapshot_hash(batch.confirmation_json)
        item.status = "running"
        item.requested_by = env.actor
        item.attempt_token = uuid.uuid4()
        item.lease_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await db.commit()
        return batch, item


async def execute(env, view, *, commit=True):
    batch, item = await claimed(env, view)
    prepared = await application.review_application(item, env.settings)
    async with env.sessions() as db:
        user = await db.get(User, env.actor)
        await application.apply_item(db, user, batch, item, item.attempt_token, prepared)
        if commit:
            await db.commit()
        else:
            await db.rollback()
    return item


async def test_preview_frozen_create_and_caller_rollback_preserve_atomicity(env):
    view = await make_preview(env, publish=True, enable_after_publish=True)
    assert view.items[0].valid
    env.review.assert_not_awaited()
    async with env.sessions() as db:
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None
    item = await execute(env, view, commit=False)
    async with env.sessions() as db:
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None
        assert (await db.get(AgentTemplateBatchItem, item.id)).status == "running"
        user = await db.get(User, env.actor)
        batch = await db.get(AgentTemplateBatch, view.preview_id)
        live = await db.get(AgentTemplateBatchItem, item.id)
        prepared = await application.review_application(item, env.settings)
        await application.apply_item(db, user, batch, live, live.attempt_token, prepared)
        await db.commit()
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        assert config.status == "enabled" and config.published_version == 1 and config.template_id == env.template
        assert (await db.get(AgentTemplateBatchItem, item.id)).status == "succeeded"
        version = await db.scalar(select(AgentConfigVersion).where(AgentConfigVersion.agent_config_id == config.id))
        assert version.template_source_json["template_id"] == str(env.template)


async def test_default_disabled_create_code_collision_and_link_conflict(env):
    view = await make_preview(env)
    await execute(env, view)
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        assert config.status == "disabled" and config.published_version is None
    duplicate = await make_preview(env)
    assert not duplicate.items[0].valid
    assert "already_linked" in {issue.code for issue in duplicate.items[0].issues}


async def test_existing_draft_requires_complete_confirmation_and_same_snapshot_no_new_version(env):
    view = await make_preview(env, publish=True)
    await execute(env, view)
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid, revision = config.id, config.draft_revision
    equal = await make_preview(
        env, action="update", agent_id=str(cid), expected_revision=revision, publish=True, fields={}
    )
    assert equal.items[0].valid and not equal.items[0].has_existing_draft
    await execute(env, equal)
    assert env.review.await_count == 1
    async with env.sessions() as db:
        config = await db.get(AgentConfig, cid)
        assert config.published_version == 1
        config.name = "本店未发布名称"
        config.draft_revision += 1
        await db.commit()
        revision = config.draft_revision
    blocked = await make_preview(
        env, action="update", agent_id=str(cid), expected_revision=revision, publish=True, fields={}
    )
    assert "existing_draft_confirmation_required" in {i.code for i in blocked.items[0].issues}
    accepted = await make_preview(
        env,
        action="update",
        agent_id=str(cid),
        expected_revision=revision,
        publish=True,
        include_existing_draft=True,
        fields={},
    )
    assert accepted.items[0].full_target["name"] == "本店未发布名称"
    await execute(env, accepted)
    async with env.sessions() as db:
        assert (await db.get(AgentConfig, cid)).published_version == 2


async def test_knowledge_required_cross_store_approval_and_dependency_fence(env):
    slot = {"key": "policy", "name": "政策", "purpose": "依据", "required": True}
    config = env.config.model_copy(update={"knowledge_slots": []})
    from app.agents.management.templates.schemas import KnowledgeSlot

    config.knowledge_slots = [KnowledgeSlot(**slot)]
    async with env.sessions() as db:
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=2,
                config_json=config.model_dump(mode="json"),
                content_sha256=config_hash(config),
            )
        )
        await db.commit()

    async def v2(**changes):
        async with env.sessions() as db:
            return await preview.create_application_preview(
                db,
                await db.get(User, env.actor),
                env.template,
                ApplicationPreviewRequest.model_validate(
                    {
                        "template_version": 2,
                        "items": [{"store_id": str(env.store), "action": "create", "publish": True, **changes}],
                    }
                ),
            )

    missing = await v2()
    assert "required_slot_missing" in {i.code for i in missing.items[0].issues}
    assert (await v2(publish=False)).items[0].valid
    denied = await v2(knowledge_mappings={"policy": [str(env.file_other)]})
    assert not denied.items[0].valid and denied.items[0].issues[0].code == "target_unavailable"
    assert "私密" not in denied.model_dump_json()
    good = await v2(knowledge_mappings={"policy": [str(env.file)]})
    batch, item = await claimed(env, good)
    prepared = await application.review_application(item, env.settings)
    async with env.sessions() as db:
        await db.execute(
            update(KnowledgeFileVersion).where(KnowledgeFileVersion.file_id == env.file).values(approved_at=None)
        )
        await db.commit()
    async with env.sessions() as db:
        with pytest.raises(AppError) as error:
            await application.apply_item(db, await db.get(User, env.actor), batch, item, item.attempt_token, prepared)
        assert error.value.status_code == 409
        await db.rollback()
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None


@pytest.mark.parametrize("mutation", ["token", "cancel", "lease", "permission", "template", "snapshot", "catalog"])
async def test_apply_rechecks_all_fences_before_writing(env, mutation, monkeypatch):
    view = await make_preview(env, publish=True)
    batch, item = await claimed(env, view)
    prepared = await application.review_application(item, env.settings)
    token = item.attempt_token
    async with env.sessions() as db:
        if mutation == "token":
            await db.execute(
                update(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.id == item.id)
                .values(attempt_token=uuid.uuid4())
            )
        elif mutation == "cancel":
            await db.execute(
                update(AgentTemplateBatch).where(AgentTemplateBatch.id == batch.id).values(cancel_requested=True)
            )
        elif mutation == "lease":
            await db.execute(
                update(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.id == item.id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        elif mutation == "permission":
            await db.execute(delete(user_roles).where(user_roles.c.user_id == env.actor))
        elif mutation == "template":
            await db.execute(
                update(AgentTemplate).where(AgentTemplate.id == env.template).values(archived_at=datetime.now(UTC))
            )
        elif mutation == "snapshot":
            snap = dict(item.target_config_json)
            snap["publish"] = False
            await db.execute(
                update(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.id == item.id)
                .values(target_config_json=snap)
            )
        elif mutation == "catalog":
            monkeypatch.setattr(
                preview,
                "get_settings",
                lambda: SimpleNamespace(
                    llm_primary_provider="openai",
                    llm_primary_model="new",
                    llm_fallback_provider="",
                    llm_fallback_model="",
                ),
            )
        await db.commit()
    async with env.sessions() as db:
        with pytest.raises(AppError):
            await application.apply_item(db, await db.get(User, env.actor), batch, item, token, prepared)
        await db.rollback()
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None


async def test_no_knowledge_view_can_preserve_bindings_but_cannot_choose_files(env):
    first = await make_preview(env, knowledge_mappings={})
    await execute(env, first)
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        config.knowledge_scope = {**config.knowledge_scope, "file_ids": [str(env.file)]}
        await db.commit()
        cid, revision = config.id, config.draft_revision
    kept = await make_preview(
        env, actor=env.manager, action="update", agent_id=str(cid), expected_revision=revision, fields={}
    )
    assert kept.items[0].valid and kept.items[0].full_target["knowledge_file_ids"] == [str(env.file)]
    # 即使选择原 ID，显式知识选择也要求本店 knowledge.view。
    denied = await make_preview(
        env,
        actor=env.manager,
        action="update",
        agent_id=str(cid),
        expected_revision=revision,
        fields={},
        unbind_removed_file_ids=[str(env.file)],
    )
    assert not denied.items[0].valid and denied.items[0].issues[0].code == "binding_permission_denied"


@pytest.mark.parametrize("resource", ["template", "batch", "knowledge"])
async def test_concurrent_mutation_waits_for_atomic_apply_resource_locks(env, resource):
    view = await make_preview(env)
    if resource == "knowledge":
        from app.agents.management.templates.schemas import KnowledgeSlot

        async with env.sessions() as db:
            cfg = env.config.model_copy(update={"knowledge_slots": [KnowledgeSlot(key="a", name="A", purpose="A")]})
            db.add(
                AgentTemplateVersion(
                    template_id=env.template,
                    version=2,
                    config_json=cfg.model_dump(mode="json"),
                    content_sha256=config_hash(cfg),
                )
            )
            await db.commit()
            view = await preview.create_application_preview(
                db,
                await db.get(User, env.actor),
                env.template,
                ApplicationPreviewRequest.model_validate(
                    {
                        "template_version": 2,
                        "items": [
                            {
                                "store_id": str(env.store),
                                "action": "create",
                                "knowledge_mappings": {"a": [str(env.file)]},
                            }
                        ],
                    }
                ),
            )
    batch, item = await claimed(env, view)
    async with env.sessions() as writer:
        await application.apply_item(writer, await writer.get(User, env.actor), batch, item, item.attempt_token, None)
        started = asyncio.Event()

        async def archive():
            async with env.sessions() as other:
                started.set()
                if resource == "template":
                    await other.execute(
                        update(AgentTemplate)
                        .where(AgentTemplate.id == env.template)
                        .values(archived_at=datetime.now(UTC))
                    )
                elif resource == "batch":
                    await other.execute(
                        update(AgentTemplateBatch)
                        .where(AgentTemplateBatch.id == batch.id)
                        .values(cancel_requested=True)
                    )
                else:
                    await other.execute(
                        update(KnowledgeFileVersion)
                        .where(KnowledgeFileVersion.file_id == env.file)
                        .values(approved_at=None)
                    )
                await other.commit()

        task = asyncio.create_task(archive())
        await started.wait()
        await asyncio.sleep(0.05)
        assert not task.done()
        await writer.commit()
        await asyncio.wait_for(task, timeout=3)


async def test_adopt_preserves_local_reply_profile_and_partial_baseline_updates(env):
    cid = uuid.uuid4()
    async with env.sessions() as db:
        db.add(
            AgentConfig(
                id=cid,
                store_id=env.store,
                name="本店",
                code="local",
                description="本店描述",
                draft_model_provider="deepseek",
                draft_model_name="test-model",
                draft_prompt_sections=SECTIONS,
                enabled_tools=[],
                knowledge_scope={"agent_type": "service", "file_ids": [], "reply_profile": {"brand_name": "本店品牌"}},
            )
        )
        await db.commit()
    adopted = await make_preview(env, action="adopt", agent_id=str(cid), expected_revision=1)
    assert adopted.items[0].full_target["description"] == "本店描述"
    await execute(env, adopted)
    async with env.sessions() as db:
        agent = await db.get(AgentConfig, cid)
        before = agent.template_state_json
        assert before["fields"]["description"]["local_override"] is True
        assert agent.knowledge_scope["reply_profile"]["brand_name"] == "本店品牌"
        revision = agent.draft_revision
        changed = env.config.model_copy(update={"agent_type": "operations", "description": "模板新描述"})
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=2,
                config_json=changed.model_dump(mode="json"),
                content_sha256=config_hash(changed),
            )
        )
        await db.commit()
    async with env.sessions() as db:
        view = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 2,
                    "items": [
                        {
                            "store_id": str(env.store),
                            "action": "update",
                            "agent_id": str(cid),
                            "expected_revision": revision,
                            "fields": {"agent_type": {"choice": "template"}},
                        }
                    ],
                }
            ),
        )
    await execute(env, view)
    async with env.sessions() as db:
        agent = await db.get(AgentConfig, cid)
        assert agent.template_state_json["fields"]["description"] == before["fields"]["description"]
        assert agent.template_state_json["fields"]["agent_type"]["applied_template_version"] == 2
        assert agent.description == "本店描述"


async def test_file_multi_sources_removed_slot_extra_and_manual_unbind_never_revived(env):
    from app.agents.management.templates.schemas import KnowledgeSlot

    slots = [KnowledgeSlot(key=key, name=key, purpose=key) for key in ("a", "b")]
    cfg = env.config.model_copy(update={"knowledge_slots": slots})
    async with env.sessions() as db:
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=2,
                config_json=cfg.model_dump(mode="json"),
                content_sha256=config_hash(cfg),
            )
        )
        await db.commit()
        user = await db.get(User, env.actor)
        first = await preview.create_application_preview(
            db,
            user,
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 2,
                    "items": [
                        {
                            "store_id": str(env.store),
                            "action": "create",
                            "knowledge_mappings": {"a": [str(env.file)], "b": [str(env.file)]},
                        }
                    ],
                }
            ),
        )
    await execute(env, first)
    async with env.sessions() as db:
        agent = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid, revision = agent.id, agent.draft_revision
        assert agent.knowledge_scope["file_ids"] == [str(env.file)]
        cfg = env.config
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=3,
                config_json=cfg.model_dump(mode="json"),
                content_sha256=config_hash(cfg),
            )
        )
        await db.commit()
        removed = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 3,
                    "items": [
                        {
                            "store_id": str(env.store),
                            "action": "update",
                            "agent_id": str(cid),
                            "expected_revision": revision,
                            "fields": {"knowledge_slots": {"choice": "template"}},
                        }
                    ],
                }
            ),
        )
    await execute(env, removed)
    async with env.sessions() as db:
        agent = await db.get(AgentConfig, cid)
        assert agent.knowledge_scope["file_ids"] == [str(env.file)]
        assert agent.template_state_json["extra_file_ids"] == [str(env.file)]
        # 普通管理手工解绑不重写历史映射，下次不得恢复旧引用。
        agent.knowledge_scope = {**agent.knowledge_scope, "file_ids": []}
        agent.draft_revision += 1
        await db.commit()
        user = await db.get(User, env.actor)
        kept = await preview.create_application_preview(
            db,
            user,
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 2,
                    "items": [
                        {
                            "store_id": str(env.store),
                            "action": "update",
                            "agent_id": str(cid),
                            "expected_revision": agent.draft_revision,
                            "fields": {"knowledge_slots": {"choice": "template"}},
                        }
                    ],
                }
            ),
        )
        assert kept.items[0].full_target["knowledge_file_ids"] == []
        assert kept.items[0].mappings == {"a": [], "b": []}


async def test_model_review_has_no_locks_and_revision_change_fences_apply(env, monkeypatch):
    view = await make_preview(env)
    await execute(env, view)
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid, revision = config.id, config.draft_revision
    view = await make_preview(
        env,
        action="update",
        agent_id=str(cid),
        expected_revision=revision,
        publish=True,
        include_existing_draft=True,
        fields={},
    )
    batch, item = await claimed(env, view)
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_review(**kwargs):
        entered.set()
        await release.wait()
        return 10, 2

    from app.agents.management import service

    monkeypatch.setattr(service, "review_configured_prompt", slow_review)
    reviewing = asyncio.create_task(application.review_application(item, env.settings))
    await entered.wait()
    async with env.sessions() as db:
        await db.execute(
            update(AgentConfig)
            .where(AgentConfig.id == cid)
            .values(draft_revision=revision + 1, description="另一次编辑")
        )
        await asyncio.wait_for(db.commit(), timeout=2)
    release.set()
    prepared = await reviewing
    async with env.sessions() as db:
        with pytest.raises(AppError):
            await application.apply_item(db, await db.get(User, env.actor), batch, item, item.attempt_token, prepared)
        await db.rollback()
        assert (await db.get(AgentConfig, cid)).published_version is None


async def test_normal_publish_freezes_actual_local_source_and_read_view(env, monkeypatch):
    from app.agents.management import config_service, service

    first = await make_preview(env)
    await execute(env, first)
    async with env.sessions() as db:
        agent = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid = agent.id
        agent.description = "普通编辑后的本店内容"
        agent.draft_revision += 1
        await db.commit()
        monkeypatch.setattr(service, "get_settings", lambda: env.settings)
        version = await service.publish_agent(
            db, store_id=env.store, config_id=cid, expected_revision=agent.draft_revision, publisher_id=env.actor
        )
        assert version.template_source_json["fields"]["description"]["actual_value"] == "普通编辑后的本店内容"
        assert version.template_source_json["fields"]["description"]["local_override"] is True
        loaded = await config_service.get_config(db, await db.get(User, env.actor), cid)
        assert config_service.config_view(loaded).published_template_source_json == version.template_source_json


async def test_normal_publication_preserves_explicit_local_override_source(env, monkeypatch):
    from app.agents.management import service

    first = await make_preview(env)
    await execute(env, first)
    async with env.sessions() as db:
        agent = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid, revision = agent.id, agent.draft_revision
        changed = env.config.model_copy(update={"description": "模板新描述"})
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=2,
                config_json=changed.model_dump(mode="json"),
                content_sha256=config_hash(changed),
            )
        )
        await db.commit()
        kept = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 2,
                    "items": [
                        {
                            "store_id": str(env.store),
                            "action": "update",
                            "agent_id": str(cid),
                            "expected_revision": revision,
                            "fields": {"description": {"choice": "local"}},
                        }
                    ],
                }
            ),
        )
    await execute(env, kept)
    async with env.sessions() as db:
        agent = await db.get(AgentConfig, cid)
        assert agent.template_state_json["fields"]["description"]["local_override"] is True
        monkeypatch.setattr(service, "get_settings", lambda: env.settings)
        version = await service.publish_agent(
            db, store_id=env.store, config_id=cid, expected_revision=agent.draft_revision, publisher_id=env.actor
        )
        assert version.template_source_json["fields"]["description"]["local_override"] is True


async def test_preview_http_csrf_extra_rejection_and_no_cross_store_details(env):
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from app.agents.management.router import router
    from app.auth.dependencies import get_current_user
    from app.shared.config.settings import get_settings
    from app.shared.database.session import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/v1")

    async def actor():
        async with env.sessions() as db:
            return await db.get(User, env.manager)

    async def session():
        async with env.sessions() as db:
            yield db

    @app.exception_handler(AppError)
    async def error_handler(request: Request, error: AppError):
        return JSONResponse(status_code=error.status_code, content={"message": error.message})

    app.dependency_overrides[get_current_user] = actor
    app.dependency_overrides[get_db_session] = session
    path = f"/v1/agents/templates/{env.template}/application-previews"
    payload = {"template_version": 1, "items": [{"store_id": str(env.store), "action": "create"}]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post(path, json=payload)).status_code == 403
        client.cookies.set("crm_csrf_token", "csrf")
        headers = {"Origin": get_settings().cors_origin_list[0], "X-CSRF-Token": "wrong"}
        assert (await client.post(path, json=payload, headers=headers)).status_code == 403
        headers["X-CSRF-Token"] = "csrf"
        good = await client.post(path, json=payload, headers=headers)
        assert good.status_code == 200, good.text
        assert good.json()["data"]["items"][0]["valid"] is True
        payload["items"][0]["template_state_json"] = {}
        assert (await client.post(path, json=payload, headers=headers)).status_code == 422
        payload["items"] = [{"store_id": str(env.other), "action": "create"}]
        denied = await client.post(path, json=payload, headers=headers)
        assert denied.status_code == 404 and "私密名称" not in denied.text


@pytest.mark.parametrize("mutation", ["signature", "manifest_id", "manifest_hash", "confirmed", "actor"])
async def test_confirmation_must_be_bound_to_frozen_preview(env, mutation):
    view = await make_preview(env)
    batch, item = await claimed(env, view)
    async with env.sessions() as db:
        live = await db.get(AgentTemplateBatch, batch.id)
        confirmation = dict(live.confirmation_json)
        if mutation == "signature":
            live.confirmation_hash = "f" * 64
        else:
            key, value = {
                "manifest_id": ("preview_id", str(uuid.uuid4())),
                "manifest_hash": ("preview_hash", "f" * 64),
                "confirmed": ("confirmed", False),
                "actor": ("actor_id", str(env.manager)),
            }[mutation]
            confirmation[key] = value
            live.confirmation_json = confirmation
            live.confirmation_hash = snapshot_hash(confirmation)
        await db.commit()
    async with env.sessions() as db:
        with pytest.raises(AppError):
            await application.apply_item(db, await db.get(User, env.actor), batch, item, item.attempt_token, None)


async def test_draft_detach_preserves_published_source_until_next_publish(env, monkeypatch):
    from app.agents.management import config_service, service

    first = await make_preview(env, publish=True)
    await execute(env, first)
    async with env.sessions() as db:
        agent = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid = agent.id
        agent.template_id = None
        agent.template_state_json = None
        agent.draft_revision += 1
        await db.commit()
    async with env.sessions() as db:
        user = await db.get(User, env.actor)
        agent = await config_service.get_config(db, user, cid)
        assert config_service.config_view(agent).published_template_source_json["template_id"] == str(env.template)
        # 本用例验证列表来源投影；只在此店为合成管理角色补明确查看授权。
        assert await config_service.get_configs(db, await db.get(User, env.manager)) == []
        manager_role = await db.scalar(
            select(user_roles.c.role_id).where(user_roles.c.user_id == env.manager, user_roles.c.store_id == env.store)
        )
        view_permission = await db.scalar(select(Permission.id).where(Permission.code == "agent.view"))
        await db.execute(role_permissions.insert().values(role_id=manager_role, permission_id=view_permission))
        await db.commit()
        listed = await config_service.get_configs(db, await db.get(User, env.manager))
        assert next(item for item in listed if item.id == cid).published_template_source_json["template_id"] == str(
            env.template
        )
        monkeypatch.setattr(service, "get_settings", lambda: env.settings)
        await service.publish_agent(
            db, store_id=env.store, config_id=cid, expected_revision=agent.draft_revision, publisher_id=env.actor
        )
    async with env.sessions() as db:
        agent = await config_service.get_config(db, await db.get(User, env.actor), cid)
        assert config_service.config_view(agent).published_template_source_json is None
        old = await db.scalar(
            select(AgentConfigVersion).where(AgentConfigVersion.agent_config_id == cid, AgentConfigVersion.version == 1)
        )
        assert old.template_source_json["template_id"] == str(env.template)


async def test_lease_expiring_while_waiting_for_config_lock_cannot_commit(env):
    first = await make_preview(env)
    await execute(env, first)
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        cid, revision = config.id, config.draft_revision
    view = await make_preview(env, action="update", agent_id=str(cid), expected_revision=revision, fields={})
    batch, item = await claimed(env, view)
    async with env.sessions() as blocker:
        await blocker.scalar(select(AgentConfig).where(AgentConfig.id == cid).with_for_update())
        async with env.sessions() as db:
            await db.execute(
                update(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.id == item.id)
                .values(lease_expires_at=datetime.now(UTC) + timedelta(seconds=0.3))
            )
            await db.commit()

        async def applying():
            async with env.sessions() as db:
                await application.apply_item(db, await db.get(User, env.actor), batch, item, item.attempt_token, None)
                await db.commit()

        task = asyncio.create_task(applying())
        await asyncio.sleep(0.5)
        await blocker.rollback()
        with pytest.raises(AppError):
            await asyncio.wait_for(task, timeout=3)
    async with env.sessions() as db:
        assert (await db.get(AgentConfig, cid)).draft_revision == revision


@pytest.mark.parametrize("bad", ["invalid_manual", "archived_file", "cross_store_agent"])
async def test_one_authorized_invalid_store_does_not_hide_other_store_preview(env, bad):
    changes = {"fields": {"tool_names": {"choice": "manual", "value": ["unknown-tool"]}}}
    if bad == "archived_file":
        # 初次关联有既存文件，归档后只影响本店这一行。
        cid = uuid.uuid4()
        async with env.sessions() as db:
            db.add(
                AgentConfig(
                    id=cid,
                    store_id=env.store,
                    name="旧配置",
                    code="old",
                    draft_prompt_sections=SECTIONS,
                    enabled_tools=[],
                    knowledge_scope={"file_ids": [str(env.file)]},
                )
            )
            await db.execute(
                update(KnowledgeFile).where(KnowledgeFile.id == env.file).values(archived_at=datetime.now(UTC))
            )
            await db.commit()
        changes = {"action": "adopt", "agent_id": str(cid), "expected_revision": 1}
    elif bad == "cross_store_agent":
        changes = {"action": "adopt", "agent_id": str(uuid.uuid4()), "expected_revision": 1}
    async with env.sessions() as db:
        view = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 1,
                    "items": [
                        {"store_id": str(env.store), "action": "create", **changes},
                        {"store_id": str(env.other), "action": "create"},
                    ],
                }
            ),
        )
        assert len(view.items) == 2
        assert not view.items[0].valid and view.items[0].issues
        assert view.items[1].valid
        assert view.items[0].request.agent_id == (uuid.UUID(changes["agent_id"]) if "agent_id" in changes else None)
        assert await db.scalar(select(AgentConfig.id).where(AgentConfig.store_id == env.other)) is None
        assert (await db.get(AgentTemplateBatchItem, view.items[0].id)).agent_config_id is None
        assert (
            len(
                (
                    await db.scalars(
                        select(AgentTemplateBatchItem).where(AgentTemplateBatchItem.batch_id == view.preview_id)
                    )
                ).all()
            )
            == 2
        )


async def test_registered_unavailable_tool_is_warning_and_retired_local_tool_can_be_replaced(env):
    warned = await make_preview(
        env, publish=True, fields={"tool_names": {"choice": "manual", "value": ["query_order"]}}
    )
    assert warned.items[0].valid
    assert "tool_unavailable" in {warning.code for warning in warned.items[0].warnings}
    cid = uuid.uuid4()
    async with env.sessions() as db:
        db.add(
            AgentConfig(
                id=cid,
                store_id=env.store,
                name="旧工具",
                code="retired",
                enabled_tools=["retired_tool"],
                draft_prompt_sections=SECTIONS,
                knowledge_scope={"file_ids": []},
            )
        )
        await db.commit()
    invalid = await make_preview(env, action="adopt", agent_id=str(cid), expected_revision=1)
    assert not invalid.items[0].valid
    repaired = await make_preview(
        env, action="adopt", agent_id=str(cid), expected_revision=1, fields={"tool_names": {"choice": "template"}}
    )
    assert repaired.items[0].valid and repaired.items[0].full_target["enabled_tools"] == []
    tool_diff = next(diff for diff in repaired.items[0].diffs if diff.field == "tool_names")
    assert tool_diff.local == ["retired_tool"]
    collision = await make_preview(env, code="retired")
    assert "code_conflict" in {issue.code for issue in collision.items[0].issues}


async def test_concurrent_normal_create_is_atomic_repreview_conflict(env, monkeypatch):
    view = await make_preview(env)
    batch, item = await claimed(env, view)
    validated = asyncio.Event()
    original = application._validate_item

    async def after_validation(*args, **kwargs):
        result = await original(*args, **kwargs)
        validated.set()
        return result

    monkeypatch.setattr(application, "_validate_item", after_validation)
    async with env.sessions() as normal_writer:
        normal_writer.add(AgentConfig(store_id=env.store, name="另一次普通创建", code="service"))
        await normal_writer.flush()

        async def applying():
            async with env.sessions() as db:
                await application.apply_item(db, await db.get(User, env.actor), batch, item, item.attempt_token, None)
                await db.commit()

        task = asyncio.create_task(applying())
        await asyncio.wait_for(validated.wait(), timeout=3)
        assert not task.done()
        await normal_writer.commit()
        with pytest.raises(AppError) as error:
            await asyncio.wait_for(task, timeout=3)
        assert error.value.status_code == 409
    async with env.sessions() as db:
        assert (await db.get(AgentTemplateBatchItem, item.id)).status == "running"
        assert await db.scalar(select(AgentConfig).where(AgentConfig.template_id == env.template)) is None


@pytest.mark.parametrize("bindings", ["replace_mapped", "shared_source", "empty"])
async def test_normal_publish_projects_actual_knowledge_sources_without_mutating_draft(env, monkeypatch, bindings):
    from app.agents.management import config_service, service
    from app.agents.management.schemas import AgentConfigUpdate
    from app.agents.management.templates.schemas import KnowledgeSlot

    added, shared, config_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    target = env.config.model_copy(
        update={"knowledge_slots": [KnowledgeSlot(key="policy", name="政策", purpose="依据")]}
    )
    async with env.sessions() as db:
        for file_id in (added, shared):
            db.add(
                KnowledgeFile(
                    id=file_id,
                    store_id=env.store,
                    original_filename="合成资料",
                    filename_key=file_id.hex,
                    active_version_number=1,
                )
            )
            await db.flush()
            db.add(
                KnowledgeFileVersion(
                    store_id=env.store,
                    file_id=file_id,
                    version_number=1,
                    source_object_key="synthetic",
                    file_sha256="b" * 64,
                    media_type="text/plain",
                    config_json={},
                    status="ready",
                    publication_approval="approved_for_internal_review",
                    approved_by=env.actor,
                    approved_at=datetime.now(UTC),
                    created_by=env.actor,
                )
            )
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=2,
                config_json=target.model_dump(mode="json"),
                content_sha256=config_hash(target),
            )
        )
        db.add(
            AgentConfig(
                id=config_id,
                store_id=env.store,
                name="有手工文件的Agent",
                code="service",
                draft_model_provider="deepseek",
                draft_model_name="test-model",
                draft_prompt_sections=SECTIONS,
                knowledge_scope={"agent_type": "service", "file_ids": [str(shared)]},
            )
        )
        await db.commit()
        adopted = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 2,
                    "items": [
                        {
                            "store_id": str(env.store),
                            "action": "adopt",
                            "agent_id": str(config_id),
                            "expected_revision": 1,
                            "fields": {"knowledge_slots": {"choice": "template"}},
                            "knowledge_mappings": {"policy": [str(env.file), str(shared)]},
                        }
                    ],
                }
            ),
        )
    assert adopted.items[0].valid
    await execute(env, adopted)
    monkeypatch.setattr(service, "get_settings", lambda: env.settings)
    async with env.sessions() as db:
        agent = await db.get(AgentConfig, config_id)
        draft_state = copy.deepcopy(agent.template_state_json)
        assert draft_state["extra_file_ids"] == [str(shared)]
        first = await service.publish_agent(
            db, store_id=env.store, config_id=config_id, expected_revision=agent.draft_revision, publisher_id=env.actor
        )
        original_source = copy.deepcopy(first.template_source_json)
        requested = {"replace_mapped": [added, shared], "shared_source": [env.file, shared], "empty": []}[bindings]
        await config_service.update_config(
            db,
            await db.get(User, env.actor),
            config_id,
            AgentConfigUpdate(expected_revision=agent.draft_revision, knowledge_file_ids=requested),
        )
        assert agent.template_state_json == draft_state
        second = await service.publish_agent(
            db, store_id=env.store, config_id=config_id, expected_revision=agent.draft_revision, publisher_id=env.actor
        )
        expected_mapped = sorted(str(item) for item in requested if item in {env.file, shared})
        expected_extras = sorted(str(item) for item in requested if item in {added, shared})
        assert second.file_ids == sorted(str(item) for item in requested)
        assert second.template_source_json["knowledge_mappings"] == {"policy": expected_mapped}
        assert second.template_source_json["extra_file_ids"] == expected_extras
        source_ids = set(second.template_source_json["extra_file_ids"]) | set(
            second.template_source_json["knowledge_mappings"]["policy"]
        )
        assert source_ids == set(second.file_ids)
        assert agent.template_state_json == draft_state
        assert first.template_source_json == original_source
    async with env.sessions() as db:
        agent = await db.get(AgentConfig, config_id)
        assert agent.template_state_json == draft_state
        old = await db.scalar(
            select(AgentConfigVersion).where(
                AgentConfigVersion.agent_config_id == config_id, AgentConfigVersion.version == 1
            )
        )
        assert old.template_source_json == original_source
        viewed = await config_service.get_config(db, await db.get(User, env.actor), config_id)
        assert config_service.config_view(viewed).published_template_source_json == second.template_source_json
