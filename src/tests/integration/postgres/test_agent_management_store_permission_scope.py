"""部门会话范围不授予 Agent 配置权限；真实 JWT、HTTP、角色与 PostgreSQL。"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from _support import require_isolated_postgres_url
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management import config_service, debug
from app.agents.management import router as agent_http
from app.agents.management import service as publication
from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.templates.models import AgentTemplate
from app.agents.orchestration.aggregator import ReviewedSuggestion
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.orchestration.service import DynamicRunResult
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.runtime.models import AgentRun
from app.agents.runtime.state import RunPhase
from app.audit.models import AuditLog
from app.auth import security
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.config.settings import Settings
from app.shared.database import models as all_models  # noqa: F401
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.database.session import get_db_session
from app.shared.exceptions.errors import AppError
from app.stores.models import Store
from app.users.models import Department, department_members, department_stores
from app.workspace.router import router as workspace_router

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="需要显式隔离 PostgreSQL")
ALLOWED_URLS = {
    "postgresql+asyncpg://crm_test:crm_test@localhost:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030",
}
SECTIONS = {key: "只处理授权业务，证据不足交人工。" for key, _ in SECTION_TITLES}


@pytest.fixture
async def api(monkeypatch):
    require_isolated_postgres_url(URL)
    assert URL in ALLOWED_URLS or URL == os.getenv("AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL")
    engine = create_async_engine(URL)
    # 服务正常 commit；外层事务在 finally 回滚全部自有身份，不触及保留 fixture。
    async with engine.connect() as connection:
        outer = await connection.begin()
        sessions = async_sessionmaker(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        stores = [uuid.uuid4() for _ in range(3)]
        configs = [uuid.uuid4() for _ in stores]
        users = {name: uuid.uuid4() for name in ("supervisor", "mixed", "view_b", "manage_b", "both_b", "admin")}
        department, customer, conversation = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        template_id = uuid.uuid4()
        settings = Settings(_env_file=None).model_copy(
            update={
                "jwt_secret_key": "synthetic-agent-scope-test-secret-32-bytes",
                "llm_primary_provider": "deepseek",
                "llm_primary_model": "synthetic-scope-model",
                "llm_fallback_provider": "",
                "llm_fallback_model": "",
                "agent_debug_enabled": True,
                "agent_v2_debug_enabled": True,
                "agent_debug_timeout_seconds": 5,
            }
        )
        for module in (security, config_service, publication, agent_http, debug):
            monkeypatch.setattr(module, "get_settings", lambda: settings)
        review = AsyncMock(return_value=(2, 1))
        monkeypatch.setattr(publication, "review_configured_prompt", review)
        monkeypatch.setattr(agent_http, "consume_chat_query", AsyncMock(return_value=True))

        async def semantic_protocol(**kwargs):
            agent = kwargs["agents"][0]
            return DynamicRunResult(
                phase=RunPhase.REVIEW_READY,
                route=RoutePlan((RoutedAgent(agent.id, "合成复核"),), 1, 1, 1),
                specialists=(SpecialistResult(agent.id, "仅供人工复核"),),
                suggestion=ReviewedSuggestion("仅供人工复核", "human_review", None, (agent.id,), (), 1, 1),
                reason_code=None,
            )

        monkeypatch.setattr(debug, "execute_model_run", semantic_protocol)
        try:
            async with sessions() as db:
                roles = dict((await db.execute(select(Role.code, Role.id))).all())
                permissions = dict((await db.execute(select(Permission.code, Permission.id))).all())
                view_role, manage_role = uuid.uuid4(), uuid.uuid4()
                db.add_all(
                    [
                        Role(id=view_role, code=view_role.hex, name="仅 Agent 查看"),
                        Role(id=manage_role, code=manage_role.hex, name="仅 Agent 管理"),
                    ]
                )
                db.add_all([Store(id=sid, code=sid.hex, name="权限合成店") for sid in stores])
                db.add_all(
                    [
                        User(id=uid, login_name=uid.hex[:16], name=name, password_hash="synthetic")
                        for name, uid in users.items()
                    ]
                )
                db.add(Department(id=department, name=department.hex))
                await db.flush()
                await db.execute(
                    role_permissions.insert(),
                    [
                        {"role_id": view_role, "permission_id": permissions["agent.view"]},
                        {"role_id": manage_role, "permission_id": permissions["agent.manage"]},
                    ],
                )
                grants = [(name, roles["supervisor"], stores[0]) for name in ("supervisor", "mixed", "view_b")]
                grants += [(name, manage_role, stores[2]) for name in ("mixed", "view_b")]
                grants += [(name, view_role, stores[1]) for name in ("view_b", "both_b")]
                grants += [(name, manage_role, stores[1]) for name in ("manage_b", "both_b")]
                grants += [("admin", roles["admin"], None)]
                await db.execute(
                    user_roles.insert(),
                    [{"user_id": users[name], "role_id": role, "store_id": sid} for name, role, sid in grants],
                )
                await db.execute(
                    department_stores.insert(), [{"department_id": department, "store_id": sid} for sid in stores[:2]]
                )
                await db.execute(
                    department_members.insert(),
                    [
                        {"department_id": department, "user_id": users[name]}
                        for name in ("supervisor", "mixed", "view_b")
                    ],
                )
                db.add(Customer(id=customer, store_id=stores[1], name="合成客户"))
                db.add(AgentTemplate(id=template_id, code=template_id.hex, name="权限合成模板"))
                await db.flush()
                for sid, cid in zip(stores, configs, strict=True):
                    db.add(
                        AgentConfig(
                            id=cid,
                            store_id=sid,
                            name="客服",
                            code="service",
                            draft_model_provider="deepseek",
                            draft_model_name="synthetic-scope-model",
                            draft_prompt_sections=SECTIONS,
                            published_version=1,
                            status="enabled",
                            template_id=template_id if sid == stores[1] else None,
                        )
                    )
                await db.flush()
                for sid, cid in zip(stores, configs, strict=True):
                    db.add(
                        AgentConfigVersion(
                            store_id=sid,
                            agent_config_id=cid,
                            version=1,
                            name="客服",
                            code="service",
                            agent_type="service",
                            model_provider="deepseek",
                            model_name="synthetic-scope-model",
                            prompt_sections=SECTIONS,
                            tool_names=[],
                            file_ids=[],
                            ready_for_v2=True,
                        )
                    )
                db.add(
                    Conversation(
                        id=conversation,
                        store_id=stores[1],
                        customer_id=customer,
                        platform="tiktok",
                        external_conversation_id=conversation.hex,
                        assigned_user_id=users["admin"],
                    )
                )
                await db.flush()
                db.add(
                    Message(
                        store_id=stores[1],
                        conversation_id=conversation,
                        customer_id=customer,
                        platform="tiktok",
                        external_message_id=uuid.uuid4().hex,
                        role="user",
                        direction="inbound",
                        content="合成部门会话",
                        status="received",
                    )
                )
                await db.commit()
            app = FastAPI()
            app.include_router(agent_http.router, prefix="/v1")
            app.include_router(workspace_router, prefix="/v1")

            @app.exception_handler(AppError)
            async def app_error(_: Request, error: AppError):
                return JSONResponse(status_code=error.status_code, content={"message": error.message})

            async def db_dependency():
                async with sessions() as db:
                    yield db

            app.dependency_overrides[get_db_session] = db_dependency
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                yield SimpleNamespace(
                    client=client,
                    sessions=sessions,
                    stores=stores,
                    configs=configs,
                    users=users,
                    conversation=conversation,
                    token=lambda name: security.create_access_token(users[name]),
                )
        finally:
            await outer.rollback()
    await engine.dispose()


def headers(api, actor):
    return {"Authorization": f"Bearer {api.token(actor)}"}


async def owned_state(api):
    async with api.sessions() as db:
        queries = [
            select(AgentConfig.__table__).where(AgentConfig.store_id.in_(api.stores)).order_by(AgentConfig.id),
            select(AgentConfigVersion.__table__)
            .where(AgentConfigVersion.store_id.in_(api.stores))
            .order_by(AgentConfigVersion.id),
            select(AgentRun.__table__).where(AgentRun.store_id.in_(api.stores)).order_by(AgentRun.id),
            select(AuditLog.__table__).where(AuditLog.actor_id.in_(api.users.values())).order_by(AuditLog.id),
        ]
        return [list((await db.execute(query)).mappings()) for query in queries]


@pytest.mark.parametrize("actor", ["supervisor", "mixed"])
async def test_department_supervisor_can_read_b_conversation_but_not_b_agent(api, actor):
    response = await api.client.get(f"/v1/workspace/sessions/{api.conversation}/messages", headers=headers(api, actor))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["messages"][0]["content"] == "合成部门会话"
    listed = await api.client.get("/v1/agents", headers=headers(api, actor))
    assert listed.status_code == 200, listed.text
    visible = {row["id"] for row in listed.json()["data"]}
    assert str(api.configs[0]) in visible
    assert str(api.configs[1]) not in visible, "部门会话范围泄漏了 B Agent 草稿"


@pytest.mark.parametrize(
    "actor,allowed", [("supervisor", False), ("mixed", False), ("view_b", True), ("both_b", True), ("admin", True)]
)
@pytest.mark.parametrize("suffix", ["", "/logs"])
async def test_agent_detail_and_logs_require_target_store_view(api, actor, allowed, suffix):
    response = await api.client.get(f"/v1/agents/{api.configs[1]}{suffix}", headers=headers(api, actor))
    assert response.status_code == (200 if allowed else 404), response.text


@pytest.mark.parametrize("actor", ["view_b", "both_b", "admin"])
async def test_agent_list_keeps_explicit_view_and_global_admin_access(api, actor):
    response = await api.client.get("/v1/agents", headers=headers(api, actor))
    assert response.status_code == 200, response.text
    assert str(api.configs[1]) in {row["id"] for row in response.json()["data"]}


WRITE_ACTIONS = [
    "create",
    "update",
    "enable",
    "disable",
    "delete",
    "publish",
    "toggle",
    "debug_single",
    "debug_store",
    "detach",
]


async def write_request(api, actor, action):
    path = f"/v1/agents/{api.configs[1]}"
    kwargs = {"headers": headers(api, actor)}
    if action == "create":
        return await api.client.post(
            "/v1/agents", json={"store_id": str(api.stores[1]), "name": "新建", "code": "new_agent"}, **kwargs
        )
    if action == "update":
        return await api.client.patch(path, json={"description": "修改", "expected_revision": 1}, **kwargs)
    if action == "delete":
        return await api.client.delete(path, **kwargs)
    if action == "publish":
        return await api.client.post(path + "/publish", json={"expected_revision": 1}, **kwargs)
    if action.startswith("debug_"):
        return await api.client.post(
            path + "/debug", json={"message": "合成调试", "mode": action.removeprefix("debug_")}, **kwargs
        )
    if action == "detach":
        return await api.client.post(path + "/detach-template", json={"expected_revision": 1}, **kwargs)
    return await api.client.post(path + "/" + action, **kwargs)


@pytest.mark.parametrize("actor", ["mixed", "view_b", "manage_b", "both_b", "admin"])
@pytest.mark.parametrize("action", WRITE_ACTIONS)
async def test_agent_writes_require_manage_on_target_store_not_global_union(api, actor, action):
    if action == "delete":
        async with api.sessions() as db:
            (await db.get(AgentConfig, api.configs[1])).status = "disabled"
            await db.commit()
    before = await owned_state(api)
    response = await write_request(api, actor, action)
    after = await owned_state(api)
    allowed = actor in {"manage_b", "both_b", "admin"}
    if not allowed:
        assert after == before, "跨店管理请求已提交配置、版本、运行或审计"
        assert response.status_code == 404, response.text
    else:
        assert response.status_code == (204 if action == "delete" else 200), response.text
        if action.startswith("debug_"):
            assert response.json()["data"]["send_performed"] is False
        if action != "enable":
            assert after != before


async def test_manage_only_actor_cannot_read_but_can_detach_return_projection(api):
    for path in ("/v1/agents", f"/v1/agents/{api.configs[1]}", f"/v1/agents/{api.configs[1]}/logs"):
        assert (await api.client.get(path, headers=headers(api, "manage_b"))).status_code == 403
    response = await write_request(api, "manage_b", "detach")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["id"] == str(api.configs[1])


async def test_auto_preview_policy_requires_store_permissions_and_revision(api):
    path = f"/v1/agents/auto-reply-preview?store_id={api.stores[1]}"
    admin = headers(api, "admin")
    initial = await api.client.get(path, headers=admin)
    assert initial.status_code == 200, initial.text
    assert initial.json()["data"]["enabled"] is False
    assert initial.json()["data"]["revision"] == 0
    denied = await api.client.put(
        path,
        headers=headers(api, "both_b"),
        json={
            "enabled": True,
            "expected_revision": 0,
        },
    )
    assert denied.status_code == 404, denied.text
    enabled = await api.client.put(path, headers=admin, json={"enabled": True, "expected_revision": 0})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["data"]["enabled"] is True
    assert enabled.json()["data"]["send_performed"] is False
    stale = await api.client.put(path, headers=admin, json={"enabled": False, "expected_revision": 0})
    assert stale.status_code == 409, stale.text
    disabled = await api.client.put(path, headers=admin, json={"enabled": False, "expected_revision": 1})
    assert disabled.status_code == 200, disabled.text
    async with api.sessions() as db:
        store = await db.get(Store, api.stores[1])
        assert store.metadata_json["agent_auto_reply_preview"]["enabled"] is False


async def test_actual_auth_and_cookie_csrf_guards_remain(api):
    assert (await api.client.get("/v1/agents")).status_code == 401
    api.client.cookies.set("crm_access_token", api.token("admin"))
    response = await api.client.patch(f"/v1/agents/{api.configs[1]}", json={"description": "拒绝"})
    assert response.status_code == 403
