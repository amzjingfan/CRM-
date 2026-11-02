"""普通消息 Agent 运行与投递之间的可信桥接。"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.automation.models import AutomationDelivery
from app.agents.automation.policy import AUTOMATION_PERMISSIONS, policy_from_store
from app.agents.automation.service import claim_delivery, enqueue_delivery, process_delivery, utc
from app.agents.management.config_models import AgentTask
from app.agents.management.config_repository import find_enabled_config
from app.agents.orchestration.service import RunProgress
from app.agents.runtime.models import AgentRun
from app.agents.tools.access import current_permissions
from app.chat.service import load_automation_context, run_agent_for_message
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import Store


async def process_agent_task(session: AsyncSession, task: AgentTask, settings: Settings) -> None:
    async def cancel(code: str) -> None:
        task.status, task.error_code, task.processed_at = "cancelled", code, datetime.now(UTC)
        await session.commit()

    store = await session.scalar(
        select(Store)
        .where(Store.id == task.store_id, Store.status == "active", Store.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    try:
        policy = policy_from_store(store) if store else None
    except ValueError:
        policy = None
    if (
        policy is None
        or policy.mode == "off"
        or policy.authorized_by is None
        or not task.trace_id.startswith(f"automation:{policy.revision}:")
        or (policy.mode == "auto" and not settings.tiktok_automation_effective_enabled)
    ):
        await cancel("AUTOMATION_POLICY_CHANGED")
        return
    actor = await session.get(User, policy.authorized_by, populate_existing=True)
    try:
        permissions = (
            await current_permissions(session, actor, task.store_id) if actor and actor.status == "active" else set()
        )
    except AppError:
        permissions = set()
    if not AUTOMATION_PERMISSIONS <= permissions:
        await cancel("AUTOMATION_ACTOR_REVOKED")
        return
    conversation, trigger = await load_automation_context(session, task.conversation_id, task.trigger_message_id)
    if (
        conversation.store_id != task.store_id
        or (conversation.metadata_json or {}).get("automation_paused") is True
        or conversation.status != "active"
        or policy.enabled_at is None
        or utc(trigger.created_at) <= policy.enabled_at
        or (
            conversation.last_human_replied_at is not None
            and utc(conversation.last_human_replied_at) >= utc(trigger.created_at)
        )
    ):
        await cancel("AUTOMATION_CONTEXT_CHANGED")
        return
    conversation_revision = (conversation.metadata_json or {}).get("automation_revision", 0)
    config = await find_enabled_config(session, task.store_id)
    if config is None:
        await cancel("AUTOMATION_AGENT_DISABLED")
        return
    run_permissions = (
        permissions if policy.mode == "auto" else permissions & {"workspace.view", "orders.view", "knowledge.view"}
    )
    attempt = task.attempt_count
    await session.commit()
    result = await run_agent_for_message(
        session,
        config,
        conversation,
        trigger,
        task.trace_id,
        run_permissions,
        user=actor,
        reply_progress=RunProgress(reply_plan=True),
    )
    refreshed_task = await session.get(AgentTask, task.id, populate_existing=True, with_for_update=True)
    assert refreshed_task is not None
    task = refreshed_task
    if task.status != "processing" or task.attempt_count != attempt:
        # 租约已由新Worker恢复；旧模型结果不得覆盖新持有者或产生投递。
        return
    task.agent_run_id, task.result_action, task.preview_content = (
        result.agent_run_id,
        result.action.value,
        result.draft_reply,
    )
    task.processed_at = datetime.now(UTC)
    if policy.mode == "preview":
        task.status = "human_review" if result.draft_reply else "no_suggestion"
        await session.commit()
        return
    run = await session.get(AgentRun, result.agent_run_id)
    proof = (run.snapshot_ref or {}).get("automation_eligibility") if run else None
    if not isinstance(proof, dict) or proof.get("eligible") is not True:
        task.status, task.error_code = "human_review", "AUTO_SEND_NOT_APPROVED"
        await session.commit()
        return
    parts = result.reply_parts or ([result.draft_reply] if result.draft_reply else [])
    from app.workspace import service as workspace

    card_parts: list[tuple[str, str | None]] = []
    if result.logistics_order_numbers and actor is not None:
        try:
            for order_number in result.logistics_order_numbers:
                cards = await workspace.get_logistics_card_preview(session, actor, conversation.id, order_number)
                card_parts.extend((item.card.order_id, item.card.package_id) for item in cards)
        except AppError:
            task.status, task.error_code = "human_review", "AUTOMATION_CARD_NOT_VERIFIED"
            await session.commit()
            return
    card_parts = list(dict.fromkeys(card_parts))
    if card_parts and run is not None:
        proof["cards"] = [
            [len(parts) + index, order_id, package_id] for index, (order_id, package_id) in enumerate(card_parts)
        ]
        required = proof.get("required_permissions")
        proof["required_permissions"] = sorted({*(required if isinstance(required, list) else []), "orders.view"})
        run.snapshot_ref = {**(run.snapshot_ref or {}), "automation_eligibility": proof}
    for index, content in enumerate(parts):
        await enqueue_delivery(
            session,
            store_id=task.store_id,
            conversation_id=task.conversation_id,
            source_kind="agent",
            source_key=str(task.trigger_message_id),
            content=content,
            authorized_by=policy.authorized_by,
            policy_revision=policy.revision,
            mode="auto",
            trigger_message_id=task.trigger_message_id,
            agent_run_id=result.agent_run_id,
            part_index=index,
            authorization_json={"conversation_revision": conversation_revision},
        )
    for index, (order_id, package_id) in enumerate(card_parts, start=len(parts)):
        await enqueue_delivery(
            session,
            store_id=task.store_id,
            conversation_id=task.conversation_id,
            source_kind="agent",
            source_key=str(task.trigger_message_id),
            content="Logistics update" if result.reply_language == "en" else "物流信息",
            authorized_by=policy.authorized_by,
            policy_revision=policy.revision,
            mode="auto",
            trigger_message_id=task.trigger_message_id,
            agent_run_id=result.agent_run_id,
            part_index=index,
            message_type="logistics_card",
            card_order_id=order_id,
            card_package_id=package_id,
            authorization_json={"conversation_revision": conversation_revision},
        )
    task.status = "queued"
    await session.commit()


async def process_one_delivery(session: AsyncSession, settings: Settings) -> bool:
    from app.reception.automation import collect_due_reception_deliveries

    await collect_due_reception_deliveries(session, settings)
    row = await claim_delivery(session, settings)
    if row is None:
        return False
    row_id, token = row.id, row.claim_token
    try:
        await process_delivery(session, row, settings)
    except Exception:
        await session.rollback()
        failed = await session.get(AutomationDelivery, row_id, with_for_update=True)
        if failed is not None and failed.claim_token == token:
            failed.status = "unknown" if failed.status == "dispatching" else "failed"
            failed.error_code = (
                "AUTOMATION_RECEIPT_UNKNOWN" if failed.status == "unknown" else "AUTOMATION_DELIVERY_FAILED"
            )
            failed.processed_at = datetime.now(UTC)
            await session.commit()
        raise
    return True
