"""隔离 PostgreSQL 上验证真实模板 HTTP、授权和版本边界。"""

import os
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from _support import require_isolated_postgres_url
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.router import router
from app.agents.management.templates import service
from app.agents.management.templates.models import AgentTemplate, AgentTemplateVersion
from app.agents.prompts.sections import SECTION_TITLES
from app.audit.models import AuditLog
from app.auth.dependencies import get_current_user
from app.shared.database.base import (
    Permission,
    Role,
    User,
    role_permissions,
    user_roles,
)
from app.shared.database.session import get_db_session
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="需要显式隔离 PostgreSQL")
ALLOWED_TEST_DATABASE_URLS = {
    "postgresql+asyncpg://crm_test:crm_test@localhost:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030",
}
SECTIONS = {key: "只处理授权业务，证据不足交人工。" for key, _ in SECTION_TITLES}


@pytest.fixture
async def api(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[SimpleNamespace]:
    require_isolated_postgres_url(URL)
    assert URL in ALLOWED_TEST_DATABASE_URLS or URL == os.getenv("AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL")
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = [uuid.uuid4() for _ in range(6)]
    admin_id, scoped_id, viewer_id, store_id, other_id, source_id = ids
    role_id = uuid.uuid4()
    async with sessions() as db:
        admin_role = await db.scalar(select(Role).where(Role.code == "admin"))
        assert admin_role is not None
        permission = await db.scalar(select(Permission).where(Permission.code == "agent.view"))
        assert permission is not None
        db.add_all(
            [
                Store(id=store_id, code=store_id.hex, name="授权店"),
                Store(id=other_id, code=other_id.hex, name="另店"),
            ]
        )
        db.add_all([User(id=i, login_name=f"t{i.hex[:12]}", name="测试", password_hash="test") for i in ids[:3]])
        db.add(Role(id=role_id, code=f"t{role_id.hex}", name="模板查看"))
        await db.flush()
        await db.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission.id))
        await db.execute(
            user_roles.insert(),
            [
                {"user_id": admin_id, "role_id": admin_role.id, "store_id": None},
                {"user_id": scoped_id, "role_id": admin_role.id, "store_id": store_id},
                {"user_id": viewer_id, "role_id": role_id, "store_id": store_id},
            ],
        )
        db.add(
            AgentConfig(
                id=source_id,
                store_id=store_id,
                name="源草稿",
                code="source",
                draft_revision=3,
                draft_model_provider="deepseek",
                draft_model_name="test-model",
                draft_prompt_sections=SECTIONS,
                knowledge_scope={
                    "agent_type": "operations",
                    "file_ids": [str(uuid.uuid4())],
                    "reply_profile": {"private": True},
                },
                enabled_tools=[],
            )
        )
        await db.flush()
        db.add(
            AgentConfigVersion(
                store_id=store_id,
                agent_config_id=source_id,
                version=1,
                name="源版本",
                code="source_v1",
                agent_type="service",
                model_provider="deepseek",
                model_name="test-model",
                prompt_sections=SECTIONS,
                tool_names=[],
                file_ids=[str(uuid.uuid4())],
            )
        )
        await db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def app_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"message": error.message})

    async def db_dependency():
        async with sessions() as db:
            yield db

    async def actor(request: Request):
        async with sessions() as db:
            return await db.get(User, uuid.UUID(request.headers.get("X-Actor", str(admin_id))))

    app.dependency_overrides[get_db_session] = db_dependency
    app.dependency_overrides[get_current_user] = actor

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            llm_primary_provider="deepseek",
            llm_primary_model="test-model",
            llm_fallback_provider="",
            llm_fallback_model="",
        ),
    )
    review = AsyncMock(return_value=(10, 2))
    monkeypatch.setattr(service, "review_configured_prompt", review)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as client:
        yield SimpleNamespace(
            client=client,
            sessions=sessions,
            admin=admin_id,
            scoped=scoped_id,
            viewer=viewer_id,
            store=store_id,
            other=other_id,
            source=source_id,
            review=review,
        )
    async with sessions() as db:
        await db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids[:3])))
        await db.execute(delete(Store).where(Store.id.in_([store_id, other_id])))
        await db.execute(delete(AgentTemplate).where(AgentTemplate.created_by == admin_id))
        await db.execute(delete(User).where(User.id.in_(ids[:3])))
        await db.execute(delete(Role).where(Role.id == role_id))
        await db.commit()
    await engine.dispose()


async def create(api, **changes):
    body = {
        "code": f"t{uuid.uuid4().hex}",
        "name": "客服模板",
        "config": {
            "default_agent_name": "客服",
            "suggested_code": "service",
            "model_provider": "deepseek",
            "model_name": "test-model",
            "prompt_sections": SECTIONS,
            "knowledge_slots": [
                {
                    "key": "policy",
                    "name": "政策",
                    "purpose": "政策依据",
                    "required": True,
                }
            ],
        },
        **changes,
    }
    result = await api.client.post("/v1/agents/templates", json=body)
    assert result.status_code == 200, result.text
    return result.json()["data"]


async def test_permissions_csrf_static_routes_and_hidden_drafts(api):
    for who in (api.scoped, api.viewer):
        response = await api.client.post(
            "/v1/agents/templates",
            json={"code": "blocked", "name": "拒绝"},
            headers={"X-Actor": str(who)},
        )
        assert response.status_code == 403
    template = await create(api)
    path = f"/v1/agents/templates/{template['id']}"
    assert (await api.client.get(path, headers={"X-Actor": str(api.viewer)})).status_code == 404
    listed = (await api.client.get("/v1/agents/templates", headers={"X-Actor": str(api.viewer)})).json()["data"]
    assert listed == {"items": [], "can_manage": False}
    assert (await api.client.get("/v1/agents/templates")).json()["data"]["can_manage"] is True
    api.client.headers.pop("Authorization")
    assert (await api.client.post(path + "/publish", json={"expected_revision": 1})).status_code == 403
    from app.shared.config.settings import get_settings

    origin = get_settings().cors_origin_list[0]
    api.client.cookies.set("crm_csrf_token", "test-csrf")
    assert (
        await api.client.post(
            path + "/publish", json={"expected_revision": 1}, headers={"Origin": origin, "X-CSRF-Token": "wrong"}
        )
    ).status_code == 403
    assert (
        await api.client.post(
            path + "/publish", json={"expected_revision": 1}, headers={"Origin": origin, "X-CSRF-Token": "test-csrf"}
        )
    ).status_code == 200


async def test_publish_immutable_draft_edit_archive_restore_and_conflicts(api):
    template = await create(api)
    path = f"/v1/agents/templates/{template['id']}"
    assert (
        await api.client.post("/v1/agents/templates", json={"code": template["code"], "name": "重复"})
    ).status_code == 409
    published = await api.client.post(path + "/publish", json={"expected_revision": 1})
    assert published.status_code == 200, published.text
    assert published.json()["data"]["published_version"] == 1
    assert api.review.await_count == 1
    changed = await api.client.patch(
        path,
        json={
            "expected_revision": 2,
            "config": {"default_agent_name": "新草稿", "suggested_code": "service"},
        },
    )
    assert changed.status_code == 200
    read = (await api.client.get(path, headers={"X-Actor": str(api.viewer)})).json()["data"]
    assert read["draft_revision"] is None and read["config"]["default_agent_name"] == "客服"
    assert read["can_manage"] is False
    versions = (await api.client.get(path + "/versions")).json()["data"]
    assert versions[0]["version"] == 1 and versions[0]["config"]["default_agent_name"] == "客服"
    assert (await api.client.patch(path, json={"expected_revision": 2, "name": "过期"})).status_code == 409
    assert (await api.client.post(path + "/archive", json={"expected_revision": 3})).status_code == 200
    assert (await api.client.get(path, headers={"X-Actor": str(api.viewer)})).status_code == 404
    assert (await api.client.post(path + "/publish", json={"expected_revision": 4})).status_code == 409
    assert (await api.client.post(path + "/restore", json={"expected_revision": 4})).status_code == 200
    assert (await api.client.get(path, headers={"X-Actor": str(api.viewer)})).status_code == 200
    async with api.sessions() as db:
        version = await db.scalar(
            select(AgentTemplateVersion).where(AgentTemplateVersion.template_id == uuid.UUID(template["id"]))
        )
        assert version.config_json["default_agent_name"] == "客服"
        source = await db.get(AgentConfig, api.source)
        assert source.draft_revision == 3 and source.template_id is None


async def test_from_agent_exact_selection_strips_store_fields_and_checks_access(api):
    body = {
        "code": f"t{uuid.uuid4().hex}",
        "name": "提取",
        "source_agent_id": str(api.source),
        "source_version": 1,
    }
    result = await api.client.post("/v1/agents/templates/from-agent", json=body)
    assert result.status_code == 200, result.text
    config = result.json()["data"]["config"]
    assert config["default_agent_name"] == "源版本" and config["suggested_code"] == "source_v1"
    assert config["knowledge_slots"] == [] and "file_ids" not in str(config) and "reply_profile" not in str(config)
    body.pop("source_version")
    body.update(code=f"t{uuid.uuid4().hex}", source_draft_revision=2)
    assert (await api.client.post("/v1/agents/templates/from-agent", json=body)).status_code == 409
    body["source_draft_revision"] = 3
    response = await api.client.post("/v1/agents/templates/from-agent", json=body)
    assert response.status_code == 200 and response.json()["data"]["config"]["default_agent_name"] == "源草稿"
    async with api.sessions() as db:
        source = await db.get(AgentConfig, api.source)
        source.store_id = api.other
        store = await db.get(Store, api.other)
        store.status = "disabled"
        await db.commit()
    body["code"] = f"t{uuid.uuid4().hex}"
    assert (await api.client.post("/v1/agents/templates/from-agent", json=body)).status_code == 404


async def test_review_outside_transaction_race_and_failure_leave_no_version(api):
    template = await create(api)
    template_id = uuid.UUID(template["id"])
    path = f"/v1/agents/templates/{template_id}"

    async def race(**kwargs):
        async with api.sessions() as db:
            # 若发布持有模板锁，此独立写入会超时，不能完成模型复核。
            from sqlalchemy import text

            await db.execute(text("SET LOCAL lock_timeout = '1000ms'"))
            row = await db.get(AgentTemplate, template_id)
            row.draft_revision += 1
            await db.commit()
        return (1, 1)

    api.review.side_effect = race
    assert (await api.client.post(path + "/publish", json={"expected_revision": 1})).status_code == 409
    api.review.side_effect = AppError("THIRD_PARTY_ERROR", "复核失败", 503)
    assert (await api.client.post(path + "/publish", json={"expected_revision": 2})).status_code == 503
    async with api.sessions() as db:
        assert (
            await db.scalar(select(AgentTemplateVersion).where(AgentTemplateVersion.template_id == template_id)) is None
        )


async def test_counts_filter_stores_and_respect_reviewed_local_overrides(api):
    from app.agents.management.templates.diff import config_fields
    from app.agents.management.templates.schemas import TemplateConfig

    template = await create(api)
    path = f"/v1/agents/templates/{template['id']}"
    assert (await api.client.post(path + "/publish", json={"expected_revision": 1})).status_code == 200
    fields = config_fields(TemplateConfig.model_validate(template["config"]))
    state = {
        "schema_version": 1,
        "fields": {
            key: {
                "baseline_value": value,
                "applied_template_version": 1,
                "last_reviewed_template_version": 1,
                "local_override": True,
            }
            for key, value in fields.items()
        },
    }
    async with api.sessions() as db:
        source = await db.get(AgentConfig, api.source)
        source.template_id = uuid.UUID(template["id"])
        source.template_state_json = state
        db.add(AgentConfig(store_id=api.other, name="另店关联", code="linked", template_id=uuid.UUID(template["id"])))
        await db.commit()
    user = {"X-Actor": str(api.viewer)}
    read = (await api.client.get(path, headers=user)).json()["data"]
    assert read["linked_store_count"] == 1 and read["update_count"] == 0
    read = (await api.client.get(path)).json()["data"]
    assert read["linked_store_count"] == 2 and read["update_count"] == 1
    # 只改创建名称不进入十二字段差异；已审阅本店覆盖也不应重复提示。
    config = {**template["config"], "default_agent_name": "不同创建名"}
    assert (await api.client.patch(path, json={"expected_revision": 2, "config": config})).status_code == 200
    assert (await api.client.post(path + "/publish", json={"expected_revision": 3})).status_code == 200
    assert (await api.client.get(path, headers=user)).json()["data"]["update_count"] == 0
    config["description"] = "模板说明已变化"
    assert (await api.client.patch(path, json={"expected_revision": 4, "config": config})).status_code == 200
    assert (await api.client.post(path + "/publish", json={"expected_revision": 5})).status_code == 200
    assert (await api.client.get(path, headers=user)).json()["data"]["update_count"] == 1
    async with api.sessions() as db:
        source = await db.get(AgentConfig, api.source)
        updated_state = {
            **state,
            "fields": {key: {**value, "last_reviewed_template_version": 3} for key, value in state["fields"].items()},
        }
        source.template_state_json = updated_state
        await db.commit()
    assert (await api.client.get(path, headers=user)).json()["data"]["update_count"] == 0
    # 下一版本只改创建名称，已保留的本店覆盖不应因旧baseline而重新提示。
    config["default_agent_name"] = "另一个创建名"
    assert (await api.client.patch(path, json={"expected_revision": 6, "config": config})).status_code == 200
    assert (await api.client.post(path + "/publish", json={"expected_revision": 7})).status_code == 200
    assert (await api.client.get(path, headers=user)).json()["data"]["update_count"] == 0
    # 即使变回最初应用基线，只要不同于最后审阅的版本，也属于新变化。
    config["description"] = None
    assert (await api.client.patch(path, json={"expected_revision": 8, "config": config})).status_code == 200
    assert (await api.client.post(path + "/publish", json={"expected_revision": 9})).status_code == 200
    assert (await api.client.get(path, headers=user)).json()["data"]["update_count"] == 1


@pytest.mark.parametrize("mutation", ["hash", "archive", "revoke"])
async def test_publish_final_recheck_rejects_changed_hash_archive_or_revoked_admin(api, mutation):
    template = await create(api)
    template_id = uuid.UUID(template["id"])

    async def change_during_review(**kwargs):
        async with api.sessions() as db:
            row = await db.get(AgentTemplate, template_id)
            if mutation == "hash":
                row.draft_config_json = {**row.draft_config_json, "description": "变更"}
            elif mutation == "archive":
                from datetime import UTC, datetime

                row.archived_at = datetime.now(UTC)
            else:
                await db.execute(delete(user_roles).where(user_roles.c.user_id == api.admin))
            await db.commit()
        return (1, 1)

    api.review.side_effect = change_during_review
    response = await api.client.post(f"/v1/agents/templates/{template_id}/publish", json={"expected_revision": 1})
    assert response.status_code == (403 if mutation == "revoke" else 409), response.text
    async with api.sessions() as db:
        assert (
            await db.scalar(select(AgentTemplateVersion).where(AgentTemplateVersion.template_id == template_id)) is None
        )


async def test_all_write_routes_deny_store_admin_and_publish_rejects_incomplete_draft(api):
    template = await create(api)
    path = f"/v1/agents/templates/{template['id']}"
    headers = {"X-Actor": str(api.scoped)}
    assert (
        await api.client.patch(path, json={"expected_revision": 1, "name": "拒绝"}, headers=headers)
    ).status_code == 403
    for action in ("publish", "archive", "restore"):
        assert (
            await api.client.post(path + "/" + action, json={"expected_revision": 1}, headers=headers)
        ).status_code == 403
    assert (
        await api.client.post(
            "/v1/agents/templates/from-agent",
            json={"name": "拒绝", "code": "denied", "source_agent_id": str(api.source), "source_version": 1},
            headers=headers,
        )
    ).status_code == 403
    changed = await api.client.patch(
        path, json={"expected_revision": 1, "config": {"default_agent_name": "未配置", "suggested_code": "empty"}}
    )
    assert changed.status_code == 200
    assert (await api.client.post(path + "/publish", json={"expected_revision": 2})).status_code == 422
    api.review.assert_not_awaited()
    # 非管理员有agent.view但无任何店铺授权仍只能看到共享发布库，不泄露关联计数。
    async with api.sessions() as db:
        audit = (await db.scalars(select(AuditLog).where(AuditLog.resource_id == uuid.UUID(template["id"])))).all()
        assert audit and all(set(item.after_data) <= {"revision", "version", "config_hash"} for item in audit)


async def test_global_catalog_without_any_authorized_store_matches_registered_tools(api):
    from app.agents.management.config_service import runtime_view
    from app.agents.tools.metadata import GROUPS, TOOL_METADATA

    async with api.sessions() as db:
        # viewer仍有agent.view角色，但角色作用域为空且不是admin，所以没有任何可访问店铺。
        from sqlalchemy import update

        await db.execute(update(user_roles).where(user_roles.c.user_id == api.viewer).values(store_id=None))
        await db.commit()
    response = await api.client.get("/v1/agents/templates/catalog", headers={"X-Actor": str(api.viewer)})
    assert response.status_code == 200, response.text
    catalog = response.json()["data"]
    assert catalog["model_options"] == runtime_view().model_options
    assert catalog["prompt_sections"] == [{"key": key, "title": title} for key, title in SECTION_TITLES]
    assert catalog["groups"] == [group.model_dump() for group in GROUPS]
    assert catalog["tools"] == [
        {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "category": tool.category,
            "operation": tool.operation,
            "requires_context": tool.requires_context,
        }
        for tool in TOOL_METADATA.values()
    ]
    assert all("availability" not in tool and "scopes" not in tool for tool in catalog["tools"])


@pytest.mark.parametrize("history_kind", ["missing", "invalid", "hash"])
async def test_missing_or_invalid_reviewed_snapshot_counts_as_pending(api, history_kind):
    from app.agents.management.templates.diff import config_fields
    from app.agents.management.templates.schemas import TemplateConfig

    template = await create(api)
    template_id = uuid.UUID(template["id"])
    target = TemplateConfig.model_validate(template["config"])
    async with api.sessions() as db:
        row = await db.get(AgentTemplate, template_id)
        row.published_version = 2
        if history_kind == "hash":
            db.add(
                AgentTemplateVersion(
                    template_id=template_id, version=1, config_json=template["config"], content_sha256="a" * 64
                )
            )
        if history_kind == "invalid":
            db.add(AgentTemplateVersion(template_id=template_id, version=1, config_json={}, content_sha256="a" * 64))
        db.add(
            AgentTemplateVersion(
                template_id=template_id,
                version=2,
                config_json=template["config"],
                content_sha256=service.config_hash(target),
            )
        )
        source = await db.get(AgentConfig, api.source)
        source.template_id = template_id
        source.template_state_json = {
            "schema_version": 1,
            "fields": {
                key: {
                    "baseline_value": value,
                    "applied_template_version": 1,
                    "last_reviewed_template_version": 1,
                    "local_override": True,
                }
                for key, value in config_fields(target).items()
            },
        }
        await db.commit()
    response = await api.client.get(f"/v1/agents/templates/{template_id}")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["update_count"] == 1
    async with api.sessions() as db:
        row = await db.get(AgentTemplate, template_id)
        row.published_version = 1
        await db.commit()
    # 当前发布指针本身无有效快照时失败关闭，不用损坏内容伪装可用模板。
    assert (await api.client.get(f"/v1/agents/templates/{template_id}")).status_code == 409
