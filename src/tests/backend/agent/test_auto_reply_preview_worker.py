"""后台预演只能留下坐席草稿，不调用平台发送。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.core.schemas import AgentAction
from app.agents.management.config_models import AgentTask
from app.chat import worker
from app.shared.database.base import User
from app.stores.models import Store


@pytest.mark.asyncio
async def test_global_send_disabled_claims_only_preview_tasks() -> None:
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    from app.shared.config.settings import Settings

    await worker.claim_task(session, Settings(_env_file=None))
    statement = session.scalar.await_args.args[0]
    compiled = statement.compile(compile_kwargs={"literal_binds": True})
    assert "agent_tasks.mode = 'preview'" in str(compiled)


@pytest.mark.asyncio
async def test_preview_task_uses_current_actor_permissions_and_never_sends(
    monkeypatch,
) -> None:
    store_id, actor_id = uuid.uuid4(), uuid.uuid4()
    store = Store(
        id=store_id,
        name="测试店",
        code="test",
        status="active",
        metadata_json={
            "agent_auto_reply_preview": {
                "enabled": True,
                "revision": 1,
                "actor_id": str(actor_id),
            }
        },
    )
    actor = User(
        id=actor_id,
        login_name="preview-actor",
        name="坐席",
        password_hash="synthetic",
        status="active",
    )
    task = AgentTask(
        id=uuid.uuid4(),
        store_id=store_id,
        agent_config_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        trace_id="test",
        mode="preview",
        status="processing",
        attempt_count=1,
    )
    config = SimpleNamespace(id=task.agent_config_id, status="enabled", deleted_at=None)
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=store),
        get=AsyncMock(side_effect=lambda model, *_args, **_kwargs: actor if model is User else task),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(worker, "find_enabled_config", AsyncMock(return_value=config))
    monkeypatch.setattr(
        worker,
        "current_permissions",
        AsyncMock(
            return_value={
                "agent.manage",
                "workspace.view",
                "workspace.reply",
                "orders.view",
                "knowledge.view",
            }
        ),
    )
    monkeypatch.setattr(
        worker,
        "load_automation_context",
        AsyncMock(
            return_value=(
                SimpleNamespace(store_id=store_id),
                SimpleNamespace(id=task.trigger_message_id, content="Where is my parcel?"),
            )
        ),
    )
    run = AsyncMock(
        return_value=SimpleNamespace(
            agent_run_id=uuid.uuid4(),
            action=AgentAction.HUMAN_REVIEW,
            draft_reply="Latest status: in transit.",
        )
    )
    monkeypatch.setattr(worker, "run_agent_for_message", run)
    from app.tools.executor import SqlAlchemyToolExecutor

    monkeypatch.setattr(
        SqlAlchemyToolExecutor,
        "execute",
        AsyncMock(side_effect=AssertionError("preview attempted platform send")),
    )

    await worker.process_task(session, task, SimpleNamespace(auto_reply_enabled=False))
    assert task.status == "human_review"
    assert task.preview_content == "Latest status: in transit."
    assert task.result_action == "human_review"
    assert run.await_args.kwargs["user"].id == actor_id
    assert "workspace.reply" not in run.await_args.args[5]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_disabling_store_policy_cancels_queued_preview_before_model(
    monkeypatch,
) -> None:
    store_id = uuid.uuid4()
    store = Store(id=store_id, name="测试店", code="test", status="active", metadata_json={})
    task = AgentTask(
        id=uuid.uuid4(),
        store_id=store_id,
        agent_config_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        trace_id="test",
        mode="preview",
        status="processing",
        attempt_count=1,
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=store), commit=AsyncMock())
    run = AsyncMock()
    monkeypatch.setattr(worker, "run_agent_for_message", run)
    await worker.process_task(session, task, SimpleNamespace(auto_reply_enabled=False))
    assert task.status == "preview_cancelled"
    run.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["order_card", "product_card", "image", "video"])
async def test_reception_never_uses_display_placeholder_for_welcome_or_timeout_language(kind):
    from app.reception.automation import on_reception_inbound
    from app.shared.config.settings import Settings

    session = SimpleNamespace(scalar=AsyncMock(side_effect=AssertionError("nontext is context only")))
    assert (
        await on_reception_inbound(
            session,
            SimpleNamespace(id=uuid.uuid4(), store_id=uuid.uuid4()),
            SimpleNamespace(message_type=kind),
            Settings(_env_file=None),
        )
        == []
    )
    session.scalar.assert_not_awaited()
