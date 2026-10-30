"""真实 SQL 批次恢复、幂等与权限；复用同域合成 fixture，不接触其他数据库。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select, update
from test_agent_template_application_postgres import env as env_fixture
from test_agent_template_application_postgres import make_preview

from app.agents.management.config_models import AgentConfig
from app.agents.management.templates import application, batch
from app.agents.management.templates.batch_schemas import BatchConfirmation
from app.agents.management.templates.models import AgentTemplate, AgentTemplateBatch, AgentTemplateBatchItem
from app.agents.management.templates.processor import TemplateBatchProcessor
from app.shared.database.base import User, user_roles
from app.shared.exceptions.errors import AppError

env = env_fixture

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="需要显式专属 PostgreSQL")
ALLOWED_TEST_DATABASE_URLS = {
    "postgresql+asyncpg://crm_test:crm_test@localhost:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:5433/crm_test",
    "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_full_test_20261030",
}


@pytest.fixture(autouse=True)
def dedicated_database():
    assert os.getenv("TEST_DATABASE_URL") in ALLOWED_TEST_DATABASE_URLS


def worker(env):
    return TemplateBatchProcessor(env.sessions, env.settings)


async def confirm(env, view, key=None, actor=None):
    async with env.sessions() as db:
        return await batch.confirm_batch(
            db,
            await db.get(User, actor or env.actor),
            BatchConfirmation(preview_id=view.preview_id, confirmation=True),
            key or uuid.uuid4().hex,
        )


async def state(env, view):
    async with env.sessions() as db:
        return await db.get(AgentTemplateBatch, view.preview_id), (
            await db.scalars(select(AgentTemplateBatchItem).where(AgentTemplateBatchItem.batch_id == view.preview_id))
        ).all()


async def test_confirm_same_preview_same_or_new_key_and_conflict(env):
    view = await make_preview(env)
    key = uuid.uuid4().hex
    first = await confirm(env, view, key)
    assert first.id == view.preview_id and first.status == "queued"
    assert (await confirm(env, view, key)).id == first.id
    with pytest.raises(AppError) as changed_key:
        await confirm(env, view)
    assert changed_key.value.status_code == 409
    other = await make_preview(env)
    with pytest.raises(AppError) as exc:
        await confirm(env, other, key)
    assert exc.value.status_code == 409
    b, rows = await state(env, view)
    assert b.confirmation_json == {
        "preview_id": str(b.id),
        "preview_hash": b.preview_hash,
        "confirmed": True,
        "actor_id": str(env.actor),
    }
    assert rows[0].requested_by == env.actor
    env.review.assert_not_awaited()


async def test_background_without_browser_and_concurrent_claim_create_once(env):
    view = await make_preview(env, publish=True)
    await confirm(env, view)
    await asyncio.gather(worker(env).run_once(), worker(env).run_once())
    b, rows = await state(env, view)
    assert b.status == "completed" and rows[0].status == "succeeded"
    assert rows[0].attempt_count == 1
    assert not await worker(env).run_once()
    async with env.sessions() as db:
        configs = (await db.scalars(select(AgentConfig).where(AgentConfig.store_id == env.store))).all()
        assert len(configs) == 1 and configs[0].status == "disabled"
    assert env.review.await_count == 1


@pytest.mark.parametrize("change", ["revoke", "inactive", "archive", "catalog", "hash"])
async def test_current_authority_and_dependencies_before_model(env, monkeypatch, change):
    actor = env.manager if change == "revoke" else env.actor
    view = await make_preview(env, actor=actor, publish=True)
    await confirm(env, view, actor=actor)
    async with env.sessions() as db:
        if change == "revoke":
            await db.execute(delete(user_roles).where(user_roles.c.user_id == actor))
        elif change == "inactive":
            await db.execute(update(User).where(User.id == actor).values(status="disabled"))
        elif change == "archive":
            await db.execute(
                update(AgentTemplate).where(AgentTemplate.id == env.template).values(archived_at=datetime.now(UTC))
            )
        elif change == "hash":
            await db.execute(
                update(AgentTemplateBatchItem)
                .where(AgentTemplateBatchItem.id == view.items[0].id)
                .values(target_config_hash="0" * 64)
            )
        await db.commit()
    if change == "catalog":
        monkeypatch.setattr(application.preview, "catalog_hash", lambda: "changed")
    review = AsyncMock()
    monkeypatch.setattr(application, "review_application", review)
    assert await worker(env).run_once()
    review.assert_not_awaited()
    b, rows = await state(env, view)
    assert b.status == "partial_failed" and rows[0].status == "needs_repreview"
    async with env.sessions() as db:
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None


async def test_expired_claim_recovered_and_late_token_fenced(env, monkeypatch):
    view = await make_preview(env, publish=True)
    await confirm(env, view)
    entered, release = asyncio.Event(), asyncio.Event()
    original = application.review_application

    async def delayed(item, settings):
        entered.set()
        await release.wait()
        return await original(item, settings)

    monkeypatch.setattr(application, "review_application", delayed)
    old = asyncio.create_task(worker(env).run_once())
    await asyncio.wait_for(entered.wait(), 5)
    async with env.sessions() as db:
        row = await db.get(AgentTemplateBatchItem, view.items[0].id)
        token = row.attempt_token
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    monkeypatch.setattr(application, "review_application", original)
    assert await worker(env).run_once()
    release.set()
    await old
    b, rows = await state(env, view)
    assert b.status == "completed" and rows[0].status == "succeeded"
    assert rows[0].attempt_count == 2 and rows[0].attempt_token != token
    async with env.sessions() as db:
        configs = (await db.scalars(select(AgentConfig).where(AgentConfig.store_id == env.store))).all()
        assert len(configs) == 1 and configs[0].published_version == 1


async def test_cancel_inflight_keeps_no_uncommitted_config(env, monkeypatch):
    view = await make_preview(env, publish=True)
    await confirm(env, view)
    entered, release = asyncio.Event(), asyncio.Event()
    original = application.review_application

    async def delayed(item, settings):
        entered.set()
        await release.wait()
        return await original(item, settings)

    monkeypatch.setattr(application, "review_application", delayed)
    task = asyncio.create_task(worker(env).run_once())
    await asyncio.wait_for(entered.wait(), 5)
    async with env.sessions() as db:
        await batch.cancel_batch(db, await db.get(User, env.actor), view.preview_id)
    release.set()
    await task
    b, rows = await state(env, view)
    assert b.status == "cancelled" and rows[0].status == "cancelled"
    async with env.sessions() as db:
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None


async def test_timeout_explicit_same_hash_retry_keeps_confirmation(env, monkeypatch):
    view = await make_preview(env, publish=True)
    await confirm(env, view)
    original_review = application.review_application
    monkeypatch.setattr(application, "review_application", AsyncMock(side_effect=TimeoutError("private prompt")))
    assert await worker(env).run_once()
    b, rows = await state(env, view)
    original_confirmation, original_hash = b.confirmation_json, rows[0].target_config_hash
    assert rows[0].status == "failed" and rows[0].error_code == "review_unavailable"
    async with env.sessions() as db:
        await batch.retry_failed(db, await db.get(User, env.actor), view.preview_id)
    # 发布凭证由真实现有 prepare_publication 生成，只有外部provider是fixture mock。
    monkeypatch.setattr(application, "review_application", original_review)
    assert await worker(env).run_once()
    b, rows = await state(env, view)
    assert b.confirmation_json == original_confirmation and rows[0].target_config_hash == original_hash
    assert rows[0].status == "succeeded" and rows[0].attempt_count == 2


async def multiple(env):
    from app.agents.management.templates import preview
    from app.agents.management.templates.schemas import ApplicationPreviewRequest

    async with env.sessions() as db:
        return await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 1,
                    "items": [{"store_id": str(s), "action": "create"} for s in [env.store, env.other]],
                }
            ),
        )


async def test_cancel_preserves_committed_success_and_stops_rest(env):
    view = await multiple(env)
    await confirm(env, view)
    assert await worker(env).run_once()
    async with env.sessions() as db:
        result = await batch.cancel_batch(db, await db.get(User, env.actor), view.preview_id)
    assert result.status == "cancelled" and result.counts == {"succeeded": 1, "cancelled": 1}
    assert not await worker(env).run_once()
    async with env.sessions() as db:
        assert (
            len((await db.scalars(select(AgentConfig).where(AgentConfig.store_id.in_([env.store, env.other])))).all())
            == 1
        )


async def test_stop_mid_review_releases_session_and_restart_recovers(env, monkeypatch):
    view = await make_preview(env, publish=True)
    await confirm(env, view)
    entered, closed = asyncio.Event(), asyncio.Event()
    original = application.review_application

    async def delayed(item, settings):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            closed.set()

    monkeypatch.setattr(application, "review_application", delayed)
    processor = worker(env)
    processor.poll_seconds = 0.001
    processor.start()
    await asyncio.wait_for(entered.wait(), 5)
    await processor.stop()
    assert closed.is_set()
    _, rows = await state(env, view)
    assert rows[0].status == "running"
    async with env.sessions() as db:
        row = await db.get(AgentTemplateBatchItem, rows[0].id)
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    monkeypatch.setattr(application, "review_application", original)
    assert await worker(env).run_once()
    b, rows = await state(env, view)
    assert b.status == "completed" and rows[0].attempt_count == 2


async def test_revoke_after_review_still_blocks_final_apply(env, monkeypatch):
    view = await make_preview(env, actor=env.manager, publish=True)
    await confirm(env, view, actor=env.manager)
    original = application.review_application

    async def revoked(item, settings):
        prepared = await original(item, settings)
        async with env.sessions() as db:
            await db.execute(delete(user_roles).where(user_roles.c.user_id == env.manager))
            await db.commit()
        return prepared

    monkeypatch.setattr(application, "review_application", revoked)
    assert await worker(env).run_once()
    b, rows = await state(env, view)
    assert b.status == "partial_failed" and rows[0].status == "needs_repreview"
    async with env.sessions() as db:
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None


async def test_retry_updates_only_failed_requested_by_and_no_success_rerun(env):
    view = await multiple(env)
    await confirm(env, view)
    async with env.sessions() as db:
        # 另一个系统管理员显式重试；不向pending项目传播此操作者身份。
        from app.shared.database.base import Role

        admin = await db.scalar(select(Role).where(Role.code == "admin"))
        await db.execute(user_roles.insert().values(user_id=env.manager, role_id=admin.id, store_id=None))
        row = await db.get(AgentTemplateBatchItem, view.items[0].id)
        row.status, row.error_code = "failed", "review_unavailable"
        await db.commit()
    async with env.sessions() as db:
        await batch.retry_failed(db, await db.get(User, env.manager), view.preview_id)
    b, rows = await state(env, view)
    assert b.confirmed_by == env.actor
    assert {r.id: r.requested_by for r in rows} == {view.items[0].id: env.manager, view.items[1].id: env.actor}
    assert await worker(env).run_once() and await worker(env).run_once()
    assert not await worker(env).run_once()
    async with env.sessions() as db:
        with pytest.raises(AppError):
            await batch.retry_failed(db, await db.get(User, env.manager), view.preview_id)


async def test_stale_confirmation_rejected_without_activation(env):
    view = await make_preview(env)
    async with env.sessions() as db:
        template = await db.get(AgentTemplate, env.template)
        template.archived_at = datetime.now(UTC)
        await db.commit()
    with pytest.raises(AppError) as exc:
        await confirm(env, view)
    assert exc.value.status_code == 409
    b, rows = await state(env, view)
    assert b.status == "preview" and b.confirmed_by is None and rows[0].attempt_count == 0


async def test_batch_detail_redacts_frozen_content_after_store_revocation(env):
    view = await make_preview(env, actor=env.manager)
    await confirm(env, view, actor=env.manager)
    async with env.sessions() as db:
        await db.execute(delete(user_roles).where(user_roles.c.user_id == env.manager))
        await db.commit()
    async with env.sessions() as db:
        user = await db.get(User, env.manager)
        result = await batch.get_batch(db, user, view.preview_id, page=1, page_size=1)
        item = result.items[0]
        assert item.store_id is None and item.preview is None and item.agent_id is None
        assert item.store_name == "无权查看店铺" and item.action is None
        listing = await batch.list_batches(db, user, page=1, page_size=1)
        assert listing.pagination.total == 1 and listing.items[0].id == view.preview_id


async def test_http_real_auth_csrf_idempotency_and_scope(env):
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from app.agents.management.router import router
    from app.auth.security import create_access_token
    from app.shared.config.settings import get_settings
    from app.shared.database.session import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def handler(_: Request, error: AppError):
        return JSONResponse(status_code=error.status_code, content={"code": error.numeric_code})

    async def session():
        async with env.sessions() as db:
            yield db

    app.dependency_overrides[get_db_session] = session
    view = await make_preview(env)
    body = {"preview_id": str(view.preview_id), "confirmation": True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/v1/agents/template-batches")).status_code == 401
        client.cookies.set("crm_access_token", create_access_token(env.actor))
        assert (await client.post("/v1/agents/template-batches", json=body)).status_code == 403
        origin = get_settings().cors_origin_list[0]
        client.cookies.set("crm_csrf_token", "synthetic")
        client.headers.update({"Origin": origin, "X-CSRF-Token": "synthetic"})
        assert (await client.post("/v1/agents/template-batches", json=body)).status_code == 422
        client.headers["Idempotency-Key"] = uuid.uuid4().hex
        response = await client.post("/v1/agents/template-batches", json=body)
        assert response.status_code == 200 and response.json()["data"]["status"] == "queued"
        assert (await client.post("/v1/agents/template-batches", json=body)).status_code == 200
        # 换key未建立持久绑定时必须拒绝，不能给调用者虚假的成功幂等承诺。
        second_key = uuid.uuid4().hex
        client.headers["Idempotency-Key"] = second_key
        assert (await client.post("/v1/agents/template-batches", json=body)).status_code == 409
        next_preview = await make_preview(env)
        next_body = {"preview_id": str(next_preview.preview_id), "confirmation": True}
        assert (await client.post("/v1/agents/template-batches", json=next_body)).status_code == 200
        assert (await client.post("/v1/agents/template-batches", json=body)).status_code == 409

        assert (await client.get("/v1/agents/template-batches?page_size=0")).status_code == 422
        client.cookies.set("crm_access_token", create_access_token(env.manager))
        assert (await client.get("/v1/agents/template-batches/" + str(view.preview_id))).status_code == 404
        assert (await client.post("/v1/agents/template-batches/" + str(view.preview_id) + "/cancel")).status_code == 404


async def test_two_confirmed_batches_same_store_only_one_agent(env):
    first, second = await make_preview(env), await make_preview(env)
    await confirm(env, first)
    await confirm(env, second)
    await asyncio.gather(worker(env).run_once(), worker(env).run_once())
    while await worker(env).run_once():
        pass
    async with env.sessions() as db:
        configs = (await db.scalars(select(AgentConfig).where(AgentConfig.store_id == env.store))).all()
        assert len(configs) == 1
    states = [(await state(env, v))[0].status for v in [first, second]]
    assert sorted(states) == ["completed", "partial_failed"]


async def test_frozen_v2_stays_v2_after_v3_and_file_revocation_before_review(env, monkeypatch):
    from app.agents.management.templates import preview
    from app.agents.management.templates.models import AgentTemplateVersion
    from app.agents.management.templates.schemas import ApplicationPreviewRequest
    from app.agents.management.templates.service import config_hash
    from app.knowledge_base.document_models import KnowledgeFileVersion

    v2 = env.config.model_copy(deep=True)
    v2.description = "V2"
    from app.agents.management.templates.schemas import KnowledgeSlot

    v2.knowledge_slots = [KnowledgeSlot(key="policy", name="政策", purpose="依据", required=False)]
    async with env.sessions() as db:
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=2,
                config_json=v2.model_dump(mode="json"),
                content_sha256=config_hash(v2),
            )
        )
        await db.commit()
        view = await preview.create_application_preview(
            db,
            await db.get(User, env.actor),
            env.template,
            ApplicationPreviewRequest.model_validate(
                {"template_version": 2, "items": [{"store_id": str(env.store), "action": "create"}]}
            ),
        )
    await confirm(env, view)
    async with env.sessions() as db:
        v3 = v2.model_copy(update={"description": "V3"})
        db.add(
            AgentTemplateVersion(
                template_id=env.template,
                version=3,
                config_json=v3.model_dump(mode="json"),
                content_sha256=config_hash(v3),
            )
        )
        template = await db.get(AgentTemplate, env.template)
        template.published_version = 3
        await db.commit()
    assert await worker(env).run_once()
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        assert config.description == "V2"
    # 另一店的真实有效文件依赖撤销，必须在模型前拒绝。
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
                            "store_id": str(env.other),
                            "action": "create",
                            "publish": True,
                            "knowledge_mappings": {"policy": [str(env.file_other)]},
                        }
                    ],
                }
            ),
        )
    await confirm(env, view)
    async with env.sessions() as db:
        await db.execute(
            update(KnowledgeFileVersion)
            .where(KnowledgeFileVersion.file_id == env.file_other)
            .values(publication_approval="pending")
        )
        await db.commit()
    review = AsyncMock()
    monkeypatch.setattr(application, "review_application", review)
    assert await worker(env).run_once()
    review.assert_not_awaited()
    assert (await state(env, view))[1][0].status == "needs_repreview"


async def test_changed_dependency_requires_new_parent_preview_and_excludes_success(env):
    from app.agents.management.templates import preview
    from app.agents.management.templates.schemas import ApplicationPreviewRequest

    view = await multiple(env)
    await confirm(env, view)
    assert await worker(env).run_once()
    _, rows = await state(env, view)
    good = next(r for r in rows if r.status == "succeeded")
    failed = next(r for r in rows if r.status == "pending")
    async with env.sessions() as db:
        item = await db.get(AgentTemplateBatchItem, failed.id)
        item.status, item.error_code = "failed", "review_unavailable"
        await db.commit()
        user = await db.get(User, env.actor)
        with pytest.raises(AppError):
            await preview.create_application_preview(
                db,
                user,
                env.template,
                ApplicationPreviewRequest.model_validate(
                    {
                        "template_version": 1,
                        "parent_batch_id": str(view.preview_id),
                        "items": [{"store_id": str(good.store_id), "action": "create"}],
                    }
                ),
            )
        await db.rollback()
        user = await db.get(User, env.actor)
        fresh = await preview.create_application_preview(
            db,
            user,
            env.template,
            ApplicationPreviewRequest.model_validate(
                {
                    "template_version": 1,
                    "parent_batch_id": str(view.preview_id),
                    "items": [{"store_id": str(failed.store_id), "action": "create", "name": "修改后的配置"}],
                }
            ),
        )
    assert fresh.preview_id != view.preview_id and len(fresh.items) == 1
    _, new_rows = await state(env, fresh)
    assert new_rows[0].target_config_hash != failed.target_config_hash
    await confirm(env, fresh)
    # 原父批次仍有可重试failed，但不会自动执行；仅新续接执行新输入。
    assert await worker(env).run_once()
    assert (await state(env, fresh))[1][0].status == "succeeded"


def test_main_disposes_real_pool_between_different_event_loops(monkeypatch):
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app import main
    from app.shared.config.settings import get_settings

    url = os.getenv("TEST_DATABASE_URL")
    assert url in ALLOWED_TEST_DATABASE_URLS
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "session_factory", sessions)
    monkeypatch.setattr(main, "settings", get_settings().model_copy(update={"agent_template_processor_enabled": False}))
    monkeypatch.setattr(main, "build_shared_agent_runtime", lambda _: None)

    async def cycle():
        async with main.lifespan(main.app):
            async with sessions() as db:
                assert await db.scalar(text("select 1")) == 1
        assert engine.sync_engine.pool.checkedout() == 0

    asyncio.run(cycle())
    asyncio.run(cycle())


async def test_real_main_lifespan_runs_confirmed_queue_with_no_browser(env, monkeypatch):
    from app import main

    view = await make_preview(env)
    await confirm(env, view)
    monkeypatch.setattr(main, "session_factory", env.sessions)
    monkeypatch.setattr(main, "engine", env.sessions.kw["bind"])
    from app.shared.config.settings import get_settings

    monkeypatch.setattr(
        main, "settings", get_settings().model_copy(update={"agent_template_processor_poll_seconds": 0.001})
    )
    monkeypatch.setattr(main, "build_shared_agent_runtime", lambda _: None)
    async with main.lifespan(main.app):
        for _ in range(100):
            b, _ = await state(env, view)
            if b.status == "completed":
                break
            await asyncio.sleep(0.01)
        assert b.status == "completed"
        processor = main.app.state.template_batch_processor
    assert processor._task is None


async def test_claim_releases_connection_before_review_and_apply_rolls_back_on_failure(env, monkeypatch):
    view = await make_preview(env)
    await confirm(env, view)
    original_review, original_apply = application.review_application, application.apply_item

    async def detached_review(item, settings):
        assert env.sessions.kw["bind"].sync_engine.pool.checkedout() == 0
        return await original_review(item, settings)

    async def abort_after_write(*args):
        await original_apply(*args)
        raise RuntimeError("private credential prompt")

    monkeypatch.setattr(application, "review_application", detached_review)
    monkeypatch.setattr(application, "apply_item", abort_after_write)
    assert await worker(env).run_once()
    b, rows = await state(env, view)
    assert b.status == "partial_failed" and rows[0].status == "failed"
    assert rows[0].error_code == "processing_unavailable" and "private" not in str(rows[0].result_json)
    async with env.sessions() as db:
        assert await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store)) is None
        await batch.retry_failed(db, await db.get(User, env.actor), view.preview_id)
    monkeypatch.setattr(application, "apply_item", original_apply)
    assert await worker(env).run_once()
    assert (await state(env, view))[1][0].status == "succeeded"


async def test_apply_wins_row_lock_race_cancel_reports_committed_success(env, monkeypatch):
    initial = await make_preview(env)
    await confirm(env, initial)
    assert await worker(env).run_once()
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
    view = await make_preview(
        env,
        action="update",
        agent_id=str(config.id),
        expected_revision=config.draft_revision,
        fields={"description": {"choice": "manual", "value": "新说明"}},
    )
    await confirm(env, view)
    validating = asyncio.Event()
    original = application._validate_item

    async def observe(*args, **kwargs):
        if kwargs.get("lock"):
            validating.set()
        return await original(*args, **kwargs)

    monkeypatch.setattr(application, "_validate_item", observe)

    async def cancel():
        async with env.sessions() as db:
            return await batch.cancel_batch(db, await db.get(User, env.actor), view.preview_id)

    reviewed, release_review = asyncio.Event(), asyncio.Event()
    original_review = application.review_application

    async def pause_review(item, settings):
        result = await original_review(item, settings)
        reviewed.set()
        await release_review.wait()
        return result

    monkeypatch.setattr(application, "review_application", pause_review)
    applying = asyncio.create_task(worker(env).run_once())
    await asyncio.wait_for(reviewed.wait(), 5)
    async with env.sessions() as blocker:
        await blocker.scalar(select(AgentConfig).where(AgentConfig.id == config.id).with_for_update())
        release_review.set()
        await asyncio.wait_for(validating.wait(), 5)
        cancelling = asyncio.create_task(cancel())
        await asyncio.sleep(0.03)
        assert not applying.done() and not cancelling.done()
        await blocker.commit()
    _, result = await asyncio.wait_for(asyncio.gather(applying, cancelling), 5)
    assert result.status == "completed" and result.counts == {"succeeded": 1}
    async with env.sessions() as db:
        assert (await db.get(AgentConfig, config.id)).description == "新说明"


async def test_review_rejection_requires_repreview_and_changed_hash_cannot_retry(env, monkeypatch):
    from app.shared.exceptions.errors import ErrorCode

    view = await make_preview(env, publish=True)
    await confirm(env, view)
    monkeypatch.setattr(
        application,
        "review_application",
        AsyncMock(side_effect=AppError(ErrorCode.VALIDATION_ERROR, "需修改配置", 422)),
    )
    assert await worker(env).run_once()
    b, rows = await state(env, view)
    assert rows[0].status == "needs_repreview" and rows[0].error_code == "configuration_rejected"
    async with env.sessions() as db:
        with pytest.raises(AppError) as exc:
            await batch.retry_failed(db, await db.get(User, env.actor), view.preview_id)
        assert exc.value.status_code == 409
    other = await make_preview(env, publish=True)
    await confirm(env, other)
    monkeypatch.setattr(application, "review_application", AsyncMock(side_effect=TimeoutError()))
    assert await worker(env).run_once()
    async with env.sessions() as db:
        row = await db.get(AgentTemplateBatchItem, other.items[0].id)
        row.target_config_json = {
            **row.target_config_json,
            "config": {**row.target_config_json["config"], "description": "改变输入"},
        }
        await db.commit()
    async with env.sessions() as db:
        with pytest.raises(AppError) as exc:
            await batch.retry_failed(db, await db.get(User, env.actor), other.preview_id)
        assert exc.value.status_code == 409


async def test_claim_validation_preserves_full_lease_budget_before_model(env, monkeypatch):
    view = await make_preview(env)
    await confirm(env, view)
    original_validate = application.validate_preview_item

    async def slow_validation(db, user, row, item):
        await original_validate(db, user, row, item)
        # 模拟数据库校验耗尽初始租约，尚未commit的claim仍由本事务独占。
        item.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    monkeypatch.setattr(application, "validate_preview_item", slow_validation)
    original_review = application.review_application

    async def observe(item, settings):
        assert (item.lease_expires_at - datetime.now(UTC)).total_seconds() >= 179
        return await original_review(item, settings)

    monkeypatch.setattr(application, "review_application", observe)
    assert await worker(env).run_once()
    assert (await state(env, view))[1][0].status == "succeeded"


async def test_locked_template_is_skipped_then_revocation_blocks_before_review(env, monkeypatch):
    view = await make_preview(env, actor=env.manager, publish=True)
    await confirm(env, view, actor=env.manager)
    review = AsyncMock()
    monkeypatch.setattr(application, "review_application", review)
    async with env.sessions() as blocker:
        await blocker.scalar(select(AgentTemplate).where(AgentTemplate.id == env.template).with_for_update())
        assert not await worker(env).run_once()
        review.assert_not_awaited()
        async with env.sessions() as db:
            await db.execute(delete(user_roles).where(user_roles.c.user_id == env.manager))
            await db.commit()
        await blocker.commit()
    assert await worker(env).run_once()
    review.assert_not_awaited()
    assert (await state(env, view))[1][0].status == "needs_repreview"


async def _version_contract_api(env, method, path, *, actor=None, payload=None):
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from app.agents.management.router import router
    from app.auth.security import create_access_token
    from app.shared.config.settings import get_settings
    from app.shared.database.session import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def handler(_: Request, error: AppError):
        return JSONResponse(status_code=error.status_code, content={"code": error.numeric_code})

    async def session():
        async with env.sessions() as db:
            yield db

    app.dependency_overrides[get_db_session] = session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("crm_access_token", create_access_token(actor or env.manager))
        client.cookies.set("crm_csrf_token", "version-contract")
        client.headers.update(
            {
                "Origin": get_settings().cors_origin_list[0],
                "X-CSRF-Token": "version-contract",
                "Idempotency-Key": uuid.uuid4().hex,
            }
        )
        response = await client.request(method, path, json=payload)
        assert response.status_code == 200, response.text
        return response.json()["data"]


async def test_create_batch_http_old_published_version_is_null(env):
    view = await make_preview(env, actor=env.manager, publish=True)
    confirmed = await _version_contract_api(
        env, "POST", "/v1/agents/template-batches", payload={"preview_id": str(view.preview_id), "confirmation": True}
    )
    assert confirmed["items"][0]["old_published_version"] is None
    assert await worker(env).run_once()
    detail = await _version_contract_api(env, "GET", "/v1/agents/template-batches/" + str(view.preview_id))
    assert detail["items"][0]["old_published_version"] is None
    assert detail["items"][0]["result_version"] == 1


async def test_batch_http_old_version_frozen_across_new_publish_and_permission_revocation(env):
    initial = await make_preview(env, actor=env.manager, publish=True)
    await confirm(env, initial, actor=env.manager)
    assert await worker(env).run_once()

    async def publish_description(description):
        async with env.sessions() as db:
            config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        view = await make_preview(
            env,
            actor=env.manager,
            action="update",
            agent_id=str(config.id),
            expected_revision=config.draft_revision,
            publish=True,
            fields={"description": {"choice": "manual", "value": description}},
        )
        await _version_contract_api(
            env,
            "POST",
            "/v1/agents/template-batches",
            payload={"preview_id": str(view.preview_id), "confirmation": True},
        )
        assert await worker(env).run_once()
        return view

    second = await publish_description("第二次发布")
    path = "/v1/agents/template-batches/" + str(second.preview_id)
    detail = await _version_contract_api(env, "GET", path)
    assert detail["items"][0]["status"] == "succeeded"
    assert detail["items"][0]["old_published_version"] == 1
    assert detail["items"][0]["result_version"] == 2
    _, rows = await state(env, second)
    assert rows[0].expected_published_version == 1
    original_hash = rows[0].target_config_hash

    await publish_description("第三次发布")
    async with env.sessions() as db:
        config = await db.scalar(select(AgentConfig).where(AgentConfig.store_id == env.store))
        assert config.published_version == 3
    historical = await _version_contract_api(env, "GET", path)
    assert historical["items"][0]["old_published_version"] == 1
    assert historical["items"][0]["result_version"] == 2
    assert (await state(env, second))[1][0].target_config_hash == original_hash

    async with env.sessions() as db:
        await db.execute(delete(user_roles).where(user_roles.c.user_id == env.manager))
        await db.commit()
    hidden = (await _version_contract_api(env, "GET", path))["items"][0]
    for key in (
        "old_published_version",
        "result_version",
        "agent_id",
        "result_agent_id",
        "store_id",
        "action",
        "preview",
    ):
        assert hidden[key] is None
    assert hidden["store_name"] == "无权查看店铺"
    assert hidden["status"] == "succeeded"
