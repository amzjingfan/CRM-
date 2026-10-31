"""选择接口的真实 HTTP 合成数据回归，授权不替换。"""

import asyncio
import copy
import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from _support import require_isolated_postgres_url
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.router import router
from app.agents.management.templates import application
from app.agents.management.templates.diff import config_fields
from app.agents.management.templates.models import (
    AgentTemplate,
    AgentTemplateBatch,
    AgentTemplateBatchItem,
    AgentTemplateVersion,
)
from app.agents.management.templates.schemas import TemplateConfig
from app.agents.management.templates.service import config_hash
from app.agents.management.templates.state import resolve_fields
from app.audit.models import AuditLog
from app.auth.security import create_access_token
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.database.session import get_db_session
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="需要专用 PostgreSQL")
ALLOWED_TEST_DATABASE_URLS = {
    "postgresql+asyncpg://crm_test:crm_test@localhost:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030",
}


@pytest.fixture
async def api():
    require_isolated_postgres_url(URL)
    assert URL in ALLOWED_TEST_DATABASE_URLS or URL == os.getenv("AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL")
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    admin, scoped, viewer = [uuid.uuid4() for _ in range(3)]
    stores = [uuid.uuid4() for _ in range(107)]
    roles = [uuid.uuid4() for _ in range(3)]
    template_id, agent_id, file_id = [uuid.uuid4() for _ in range(3)]
    bound_file = uuid.uuid4()
    other_agent, deleted_agent, inactive_agent = [uuid.uuid4() for _ in range(3)]
    prefix = uuid.uuid4().hex[:12]
    template = TemplateConfig(default_agent_name="客服", suggested_code="service", description="V1")
    _, state, _, _, _ = resolve_fields(template, config_fields(template), None, 1, {}, "create")
    published_source = {"template_id": str(template_id), "template_version": 1, "state": copy.deepcopy(state)}
    async with sessions() as db:
        db.add_all(
            [User(id=i, login_name=i.hex[:16], name="合成", password_hash="test") for i in (admin, scoped, viewer)]
        )
        db.add_all(
            [
                Store(
                    id=s,
                    code=f"{prefix}-{i:03}",
                    name=f"{prefix}-店{i:03}",
                    status="disabled" if i == 105 else "active",
                    deleted_at=datetime.now(UTC) if i == 106 else None,
                )
                for i, s in enumerate(stores)
            ]
        )
        db.add_all([Role(id=r, code=r.hex, name="合成权限") for r in roles])
        await db.flush()
        admin_role = await db.scalar(select(Role).where(Role.code == "admin"))
        for rid, code in zip(roles, ("agent.manage", "agent.view", "knowledge.view"), strict=True):
            permission = await db.scalar(select(Permission).where(Permission.code == code))
            await db.execute(role_permissions.insert().values(role_id=rid, permission_id=permission.id))
        await db.execute(
            user_roles.insert(),
            [
                {"user_id": admin, "role_id": admin_role.id, "store_id": None},
                *[
                    {"user_id": scoped, "role_id": roles[0], "store_id": s}
                    for s in (stores[0], stores[1], stores[105], stores[106])
                ],
                {"user_id": scoped, "role_id": roles[1], "store_id": stores[2]},
                {"user_id": scoped, "role_id": roles[2], "store_id": stores[1]},
                {"user_id": viewer, "role_id": roles[1], "store_id": stores[0]},
            ],
        )
        db.add(
            AgentTemplate(
                id=template_id,
                code=template_id.hex,
                name="共享名称",
                published_version=1,
                draft_config_json={"private": "private draft"},
                created_by=admin,
            )
        )
        await db.flush()
        db.add(
            AgentTemplateVersion(
                template_id=template_id,
                version=1,
                config_json=template.model_dump(mode="json"),
                content_sha256=config_hash(template),
            )
        )
        db.add(
            AgentConfig(
                id=agent_id,
                store_id=stores[0],
                name="本店",
                code="service",
                description="V1",
                template_id=template_id,
                template_state_json=state,
                draft_revision=4,
                published_version=1,
                status="enabled",
                enabled_tools=[],
                draft_prompt_sections={"identity": "私有prompt"},
                knowledge_scope={
                    "agent_type": "service",
                    "file_ids": [str(bound_file)],
                    "reply_profile": {"tone": "friendly"},
                },
            )
        )
        db.add(
            AgentConfig(
                id=deleted_agent, store_id=stores[0], name="已删除", code="deleted", deleted_at=datetime.now(UTC)
            )
        )
        await db.flush()
        db.add(
            AgentConfigVersion(
                store_id=stores[0],
                agent_config_id=agent_id,
                version=1,
                name="运行名称",
                code="service",
                agent_type="service",
                prompt_sections={"identity": "运行正文"},
                tool_names=[],
                file_ids=[str(bound_file)],
                template_source_json=published_source,
            )
        )
        db.add_all(
            [
                AgentConfig(id=other_agent, store_id=stores[2], name="另店", code="other"),
                AgentConfig(id=inactive_agent, store_id=stores[105], name="停用店", code="inactive"),
                KnowledgeFile(
                    id=bound_file, store_id=stores[0], original_filename="本店文件", filename_key=bound_file.hex
                ),
            ]
        )
        for i in range(5):
            fid = file_id if i == 0 else uuid.uuid4()
            db.add(
                KnowledgeFile(
                    id=fid,
                    store_id=stores[1],
                    original_filename=f"知识{i}",
                    filename_key=fid.hex,
                    active_version_number=None if i == 1 else 1,
                    archived_at=datetime.now(UTC) if i == 3 else None,
                    deleted_at=datetime.now(UTC) if i == 4 else None,
                )
            )
            await db.flush()
            if i != 1:
                db.add(
                    KnowledgeFileVersion(
                        store_id=stores[1],
                        file_id=fid,
                        version_number=1,
                        source_object_key="private/path",
                        file_sha256="a" * 64,
                        media_type="text/plain",
                        config_json={},
                        status="ready",
                        publication_approval="approved_for_internal_review" if i != 2 else "draft",
                        approved_by=admin if i != 2 else None,
                        approved_at=datetime.now(UTC) if i != 2 else None,
                        created_by=admin,
                    )
                )
            if i == 0:
                db.add(
                    KnowledgeFileVersion(
                        store_id=stores[1],
                        file_id=fid,
                        version_number=2,
                        source_object_key="pending/path",
                        file_sha256="b" * 64,
                        media_type="text/plain",
                        config_json={},
                        status="review_required",
                        publication_approval="draft",
                        created_by=admin,
                    )
                )
        await db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def app_error(_: Request, error: AppError):
        return JSONResponse(status_code=error.status_code, content={"message": error.message})

    async def db_dependency():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db_session] = db_dependency
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        def actor(uid):
            client.cookies.set("crm_access_token", create_access_token(uid))

        actor(admin)
        try:
            yield SimpleNamespace(
                client=client,
                actor=actor,
                sessions=sessions,
                admin=admin,
                scoped=scoped,
                viewer=viewer,
                stores=stores,
                agent=agent_id,
                template=template_id,
                config=template,
                state=state,
                published_source=published_source,
                file=file_id,
                prefix=prefix,
                other_agent=other_agent,
                deleted_agent=deleted_agent,
                inactive_agent=inactive_agent,
            )
        finally:
            async with sessions() as db:
                await db.execute(delete(AgentTemplateBatch).where(AgentTemplateBatch.template_id == template_id))
                await db.execute(delete(AuditLog).where(AuditLog.actor_id.in_([admin, scoped, viewer])))
                await db.execute(delete(Store).where(Store.id.in_(stores)))
                await db.execute(delete(AgentTemplate).where(AgentTemplate.id == template_id))
                await db.execute(delete(User).where(User.id.in_([admin, scoped, viewer])))
                await db.execute(delete(Role).where(Role.id.in_(roles)))
                await db.commit()
    await engine.dispose()


async def test_application_stores_use_each_permission_row_and_stable_search_pages(api):
    api.actor(api.scoped)
    url = "/v1/agents/templates/application-stores"
    first = await api.client.get(url, params={"page_size": 1, "search": api.prefix})
    assert first.status_code == 200, first.text
    one = first.json()["data"]
    assert one["pagination"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
    assert one["items"][0]["id"] == str(api.stores[0])
    assert one["items"][0]["can_view_knowledge"] is False
    assert len(one["items"][0]["agents"]) == 1
    assert set(one["items"][0]["agents"][0]) == {
        "id",
        "name",
        "code",
        "template_id",
        "draft_revision",
        "published_version",
        "status",
    }
    second = await api.client.get(url, params={"page_size": 1, "page": 2, "search": api.prefix})
    assert second.json()["data"]["items"][0]["id"] == str(api.stores[1])
    assert second.json()["data"]["items"][0]["can_view_knowledge"] is True
    assert (await api.client.get(url, params={"page": 0})).status_code == 422
    assert (await api.client.get(url, params={"page_size": 101})).status_code == 422
    api.actor(api.admin)
    admin = (await api.client.get(url, params={"search": api.prefix, "page_size": 100})).json()["data"]
    assert admin["pagination"]["total"] == 105
    tail = (await api.client.get(url, params={"search": api.prefix, "page_size": 100, "page": 2})).json()["data"]
    assert len(tail["items"]) == 5


async def test_knowledge_selection_uses_active_approved_version_and_intersected_scope(api):
    api.actor(api.scoped)
    url = f"/v1/agents/templates/application-stores/{api.stores[1]}/knowledge-files"
    response = await api.client.get(url, params={"search": "知识", "page_size": 2})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["pagination"]["total"] == 3
    assert data["items"][0] == {
        "id": str(api.file),
        "name": "知识0",
        "active_version_number": 1,
        "status": "ready",
        "publication_approval": "approved_for_internal_review",
        "can_publish": True,
    }
    assert data["items"][1]["active_version_number"] is None
    assert data["items"][1]["can_publish"] is False
    tail = (await api.client.get(url, params={"search": "知识", "page_size": 2, "page": 2})).json()["data"]
    assert tail["items"][0]["can_publish"] is False
    assert "private/path" not in response.text and "pending/path" not in response.text
    for store in (api.stores[0], api.stores[2], api.stores[105], api.stores[106], uuid.uuid4()):
        denied = await api.client.get(f"/v1/agents/templates/application-stores/{store}/knowledge-files")
        assert denied.status_code == 404
        assert api.prefix not in denied.text
    async with api.sessions() as db:
        version = await db.scalar(
            select(KnowledgeFileVersion).where(
                KnowledgeFileVersion.file_id == api.file, KnowledgeFileVersion.version_number == 1
            )
        )
        version.approved_at = None
        await db.commit()
    revoked = (await api.client.get(url)).json()["data"]["items"][0]
    assert revoked["can_publish"] is False


async def test_source_separates_manual_draft_review_history_and_running_origin_without_writes(api):
    api.actor(api.viewer)
    url = f"/v1/agents/{api.agent}/template-source"
    initial = await api.client.get(url)
    assert initial.status_code == 200, initial.text
    data = initial.json()["data"]
    assert data["published"] == {"version": 1, "template_source_json": api.published_source}
    assert data["draft"]["name"] == "共享名称" and "private draft" not in initial.text
    assert next(f for f in data["draft"]["fields"] if f["field"] == "prompt_sections.identity")["local_override"]
    async with api.sessions() as db:
        config = await db.get(AgentConfig, api.agent)
        config.description = "保留本店值"
        state = copy.deepcopy(config.template_state_json)
        state["fields"]["description"]["last_reviewed_template_version"] = 2
        state["fields"]["description"]["local_override"] = True
        config.template_state_json = state
        template = await db.get(AgentTemplate, api.template)
        template.published_version = 2
        template.archived_at = datetime.now(UTC)
        v2 = api.config.model_copy(update={"description": "V2", "prompt_sections": {"identity": "V2角色"}})
        db.add(
            AgentTemplateVersion(
                template_id=api.template,
                version=2,
                config_json=v2.model_dump(mode="json"),
                content_sha256=config_hash(v2),
            )
        )
        await db.commit()
        before = copy.deepcopy(config.template_state_json)
    data = (await api.client.get(url)).json()["data"]
    assert data["draft"]["archived"] is True
    fields = {f["field"]: f for f in data["draft"]["fields"]}
    assert fields["description"] == {
        "field": "description",
        "local_override": True,
        "applied_template_version": 1,
        "last_reviewed_template_version": 2,
        "aligned": False,
        "pending_review": False,
    }
    assert fields["prompt_sections.identity"]["pending_review"] is True
    async with api.sessions() as db:
        template = await db.get(AgentTemplate, api.template)
        template.published_version = 3
        v3 = v2.model_copy(update={"description": "V3"})
        db.add(
            AgentTemplateVersion(
                template_id=api.template,
                version=3,
                config_json=v3.model_dump(mode="json"),
                content_sha256=config_hash(v3),
            )
        )
        await db.commit()
    newer = (await api.client.get(url)).json()["data"]
    assert next(f for f in newer["draft"]["fields"] if f["field"] == "description")["pending_review"]
    assert newer["published"] == data["published"]
    async with api.sessions() as db:
        assert (await db.get(AgentConfig, api.agent)).template_state_json == before
    api.actor(api.scoped)
    assert (await api.client.get(url)).status_code == 404


async def test_detach_locks_revision_preserves_body_history_and_is_idempotent(api):
    url = f"/v1/agents/{api.agent}/detach-template"
    api.actor(api.scoped)
    assert (await api.client.post(url, json={"expected_revision": 4})).status_code == 403
    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": "synthetic-csrf"}
    api.client.cookies.set("crm_csrf_token", "synthetic-csrf")
    assert (await api.client.post(url, headers=headers, json={"expected_revision": 3})).status_code == 409
    assert (
        await api.client.post(url, headers=headers, json={"expected_revision": 4, "publish": True})
    ).status_code == 422
    async with api.sessions() as db:
        before = await db.get(AgentConfig, api.agent)
        body = (
            before.name,
            before.description,
            before.code,
            before.draft_prompt_sections,
            before.knowledge_scope,
            before.enabled_tools,
            before.status,
            before.published_version,
            before.draft_model_provider,
            before.draft_model_name,
        )
    response = await api.client.post(url, headers=headers, json={"expected_revision": 4})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["draft_revision"] == 5 and data["template_id"] is None and data["template_state_json"] is None
    assert data["published_template_source_json"] == api.published_source
    repeat = await api.client.post(url, headers=headers, json={"expected_revision": 5})
    assert repeat.status_code == 200 and repeat.json()["data"]["draft_revision"] == 5
    assert (await api.client.post(url, headers=headers, json={"expected_revision": 4})).status_code == 409
    async with api.sessions() as db:
        after = await db.get(AgentConfig, api.agent)
        assert (
            after.name,
            after.description,
            after.code,
            after.draft_prompt_sections,
            after.knowledge_scope,
            after.enabled_tools,
            after.status,
            after.published_version,
            after.draft_model_provider,
            after.draft_model_name,
        ) == body
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == api.agent, AuditLog.action == "agent.template.detach")
            )
            == 1
        )
        versions = (
            await db.scalars(select(AgentConfigVersion).where(AgentConfigVersion.agent_config_id == api.agent))
        ).all()
        assert len(versions) == 1 and versions[0].template_source_json == api.published_source
    api.actor(api.viewer)
    source = (await api.client.get(f"/v1/agents/{api.agent}/template-source")).json()["data"]
    assert source["draft"] is None and source["published"]["template_source_json"] == api.published_source
    assert (await api.client.post(url, headers=headers, json={"expected_revision": 5})).status_code in {403, 404}


async def test_scoped_source_and_detach_hide_foreign_deleted_inactive_and_unlinked_sources(api):
    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": "synthetic-csrf"}
    api.client.cookies.set("crm_csrf_token", "synthetic-csrf")
    api.actor(api.scoped)
    denied = await api.client.post(
        f"/v1/agents/{api.other_agent}/detach-template", headers=headers, json={"expected_revision": 1}
    )
    assert denied.status_code == 404
    api.actor(api.admin)
    for cid in (api.deleted_agent, api.inactive_agent, uuid.uuid4()):
        assert (await api.client.get(f"/v1/agents/{cid}/template-source")).status_code == 404
        assert (
            await api.client.post(f"/v1/agents/{cid}/detach-template", headers=headers, json={"expected_revision": 1})
        ).status_code == 404
    unlinked = (await api.client.get(f"/v1/agents/{api.other_agent}/template-source")).json()["data"]
    assert unlinked["draft"] is None and unlinked["published"] is None


async def test_detach_invalidates_existing_batch_preview_without_changing_snapshot(api):
    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": "synthetic-csrf"}
    api.client.cookies.set("crm_csrf_token", "synthetic-csrf")
    preview = await api.client.post(
        f"/v1/agents/templates/{api.template}/application-previews",
        headers=headers,
        json={
            "template_version": 1,
            "items": [
                {
                    "store_id": str(api.stores[0]),
                    "agent_id": str(api.agent),
                    "action": "update",
                    "expected_revision": 4,
                    "fields": {},
                }
            ],
        },
    )
    assert preview.status_code == 200, preview.text
    view = preview.json()["data"]
    assert view["items"][0]["valid"], view
    async with api.sessions() as db:
        batch = await db.get(AgentTemplateBatch, uuid.UUID(view["preview_id"]))
        item = await db.get(AgentTemplateBatchItem, uuid.UUID(view["items"][0]["id"]))
        frozen = copy.deepcopy(item.target_config_json)
        actor = await db.get(User, api.admin)
        await application.validate_preview_item(db, actor, batch, item)
    assert (
        await api.client.post(f"/v1/agents/{api.agent}/detach-template", headers=headers, json={"expected_revision": 4})
    ).status_code == 200
    async with api.sessions() as db:
        batch = await db.get(AgentTemplateBatch, uuid.UUID(view["preview_id"]))
        item = await db.get(AgentTemplateBatchItem, uuid.UUID(view["items"][0]["id"]))
        actor = await db.get(User, api.admin)
        with pytest.raises(AppError) as error:
            await application.validate_preview_item(db, actor, batch, item)
        assert error.value.status_code == 409
        assert item.target_config_json == frozen


@pytest.mark.parametrize("change", ["store_disable", "store_delete", "user_disable", "revoke"])
async def test_detach_rechecks_live_access_after_observed_agent_lock_wait(api, change):
    api.actor(api.scoped)
    api.client.cookies.set("crm_csrf_token", "synthetic-csrf")
    async with api.sessions() as blocker:
        await blocker.scalar(select(AgentConfig).where(AgentConfig.id == api.agent).with_for_update())
        blocker_pid = await blocker.scalar(text("SELECT pg_backend_pid()"))
        before = dict(
            (await blocker.execute(select(AgentConfig.__table__).where(AgentConfig.id == api.agent))).mappings().one()
        )
        pending = asyncio.create_task(
            api.client.post(
                f"/v1/agents/{api.agent}/detach-template",
                headers={"Origin": "http://localhost:3000", "X-CSRF-Token": "synthetic-csrf"},
                json={"expected_revision": 4},
            )
        )
        try:
            # 必须观测到本测试持锁事务实际挡住HTTP请求，不能靠固定sleep假定时序。
            waiting = False
            for _ in range(100):
                async with api.sessions() as monitor:
                    waiting = bool(
                        await monitor.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE datname=current_database() AND wait_event_type='Lock' "
                                "AND :blocker_pid = ANY(pg_blocking_pids(pid)) "
                                "AND query LIKE '%FOR UPDATE OF agent_configs%'"
                            ),
                            {"blocker_pid": blocker_pid},
                        )
                    )
                if waiting:
                    break
                await asyncio.sleep(0.05)
            assert waiting, "detach未进入被本事务阻挡的Agent行锁等待"
            async with api.sessions() as mutation:
                if change == "user_disable":
                    actor = await mutation.get(User, api.scoped)
                    actor.status = "disabled"
                elif change == "revoke":
                    await mutation.execute(
                        delete(user_roles).where(
                            user_roles.c.user_id == api.scoped, user_roles.c.store_id == api.stores[0]
                        )
                    )
                else:
                    store = await mutation.get(Store, api.stores[0])
                    if change == "store_delete":
                        store.deleted_at = datetime.now(UTC)
                    else:
                        store.status = "disabled"
                await mutation.commit()
            await blocker.rollback()
            response = await asyncio.wait_for(pending, timeout=10)
        finally:
            await blocker.rollback()
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
    assert response.status_code == 404, response.text
    async with api.sessions() as verify:
        after = dict(
            (await verify.execute(select(AgentConfig.__table__).where(AgentConfig.id == api.agent))).mappings().one()
        )
        assert after == before
        assert after["draft_revision"] == 4 and after["template_id"] == api.template
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == api.agent, AuditLog.action == "agent.template.detach")
            )
            == 0
        )
