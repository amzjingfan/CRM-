"""执行器独立验证持久资格、来源、现权、正文与远端窗口。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.automation.eligibility import content_hash
from app.agents.automation.models import AutomationDelivery
from app.agents.automation.policy import AUTOMATION_PERMISSIONS, policy_from_store
from app.agents.automation.service import payload_hash, utc
from app.agents.management.config_models import AgentConfig
from app.agents.management.repository import list_enabled_agents
from app.agents.runtime.models import AgentRun
from app.agents.tools.access import current_permissions
from app.agents.tools.logistics_updates.authorization import verified_remote_window
from app.conversations.models import Conversation, Message
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.shared.config.settings import Settings
from app.shared.database.base import User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store
from app.tools.contracts import SendPlatformMessageArguments, ToolInvocation


async def current_customer_files(
    session: AsyncSession, store_id: uuid.UUID, references: object, *, lock: bool = False
) -> bool:
    if not isinstance(references, list):
        return False
    for reference in references:
        if not isinstance(reference, list) or len(reference) != 2:
            return False
        try:
            file_id = uuid.UUID(str(reference[0]))
        except ValueError:
            return False
        statement = (
            select(KnowledgeFileVersion.id)
            .join(
                KnowledgeFile,
                and_(
                    KnowledgeFile.id == KnowledgeFileVersion.file_id,
                    KnowledgeFile.store_id == KnowledgeFileVersion.store_id,
                ),
            )
            .where(
                KnowledgeFile.store_id == store_id,
                KnowledgeFile.id == file_id,
                KnowledgeFile.active_version_number == reference[1],
                KnowledgeFile.archived_at.is_(None),
                KnowledgeFile.deleted_at.is_(None),
                KnowledgeFileVersion.version_number == reference[1],
                KnowledgeFileVersion.status == "ready",
                KnowledgeFileVersion.publication_approval == "approved_for_public_reply",
                KnowledgeFileVersion.approved_by.is_not(None),
                KnowledgeFileVersion.approved_at.is_not(None),
            )
        )
        if lock:
            statement = statement.with_for_update(of=(KnowledgeFile, KnowledgeFileVersion))
        valid = await session.scalar(statement)
        if valid is None:
            return False
    return True


async def authorize_agent_card(
    session: AsyncSession, row: AutomationDelivery, proof: dict[str, object], actor: User
) -> bool:
    from app.workspace import service as workspace

    cards = proof.get("cards")
    if (
        row.message_type != "logistics_card"
        or not row.card_order_id
        or not isinstance(cards, list)
        or [row.part_index, row.card_order_id, row.card_package_id] not in cards
    ):
        return False
    try:
        current = await workspace.get_logistics_card_preview(session, actor, row.conversation_id, row.card_order_id)
    except AppError:
        return False
    return any(
        item.card.order_id == row.card_order_id and item.card.package_id == row.card_package_id for item in current
    )


async def authorize_delivery(
    session: AsyncSession,
    row: AutomationDelivery,
    settings: Settings,
    *,
    require_external: bool = True,
    verify_remote: bool = True,
) -> bool:
    if require_external and (
        not settings.tiktok_automation_effective_enabled or settings.app_env == "production" or row.mode != "auto"
    ):
        return False
    if row.payload_hash != payload_hash(
        store_id=row.store_id,
        conversation_id=row.conversation_id,
        content=row.content,
        message_type=row.message_type,
        card_order_id=row.card_order_id,
        card_package_id=row.card_package_id,
    ):
        return False
    conversation = await session.scalar(
        select(Conversation)
        .where(
            Conversation.id == row.conversation_id,
            Conversation.store_id == row.store_id,
            Conversation.platform == "tiktok",
            Conversation.status.in_(("active", "transferred")),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    store = await session.scalar(
        select(Store)
        .where(Store.id == row.store_id, Store.status == "active", Store.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    if (
        conversation is None
        or store is None
        or (conversation.metadata_json or {}).get("automation_paused") is True
        or row.authorized_by is None
    ):
        return False
    final_local = require_external and not verify_remote
    actor = await session.get(User, row.authorized_by, populate_existing=True, with_for_update=final_local)
    if actor is None or actor.status != "active":
        return False
    if final_local:
        # 与人员修改的 User→授权行顺序一致；DELETE/UPDATE 撤权也必须等待此投递事务结束。
        await session.execute(
            select(user_roles.c.id).where(user_roles.c.user_id == actor.id).order_by(user_roles.c.id).with_for_update()
        )
        await session.execute(
            select(role_permissions.c.role_id, role_permissions.c.permission_id)
            .where(role_permissions.c.role_id.in_(select(user_roles.c.role_id).where(user_roles.c.user_id == actor.id)))
            .order_by(role_permissions.c.role_id, role_permissions.c.permission_id)
            .with_for_update()
        )
    try:
        permissions = await current_permissions(session, actor, row.store_id)
    except AppError:
        return False
    if "workspace.reply" not in permissions:
        return False
    if row.source_kind == "agent":
        try:
            policy = policy_from_store(store)
        except ValueError:
            return False
        if (
            policy.mode != row.mode
            or policy.revision != row.policy_revision
            or policy.authorized_by != row.authorized_by
            or not AUTOMATION_PERMISSIONS <= permissions
        ):
            return False
        trigger = await session.scalar(
            select(Message).where(
                Message.id == row.trigger_message_id,
                Message.store_id == row.store_id,
                Message.conversation_id == row.conversation_id,
                Message.customer_id == conversation.customer_id,
                Message.direction == "inbound",
                Message.role == "user",
            )
        )
        if trigger is None or policy.enabled_at is None or utc(trigger.created_at) <= policy.enabled_at:
            return False
        if conversation.last_human_replied_at is not None and utc(conversation.last_human_replied_at) >= utc(
            trigger.created_at
        ):
            return False
        if row.authorization_json.get("conversation_revision") != (conversation.metadata_json or {}).get(
            "automation_revision", 0
        ):
            return False
        run = await session.scalar(
            select(AgentRun)
            .where(
                AgentRun.id == row.agent_run_id,
                AgentRun.store_id == row.store_id,
                AgentRun.conversation_id == row.conversation_id,
                AgentRun.trigger_message_id == row.trigger_message_id,
                AgentRun.status == "succeeded",
            )
            .execution_options(populate_existing=True)
        )
        proof = (run.snapshot_ref or {}).get("automation_eligibility") if run is not None else None
        if (
            not isinstance(proof, dict)
            or proof.get("eligible") is not True
            or proof.get("review_version") != "independent-evidence-privacy-v1"
            or row.message_type not in {"text", "logistics_card"}
        ):
            return False
        if conversation.status == "transferred":
            from app.agents.orchestration.fallback import fixed_fallback_copy

            language = proof.get("reply_language")
            fixed = fixed_fallback_copy(language if isinstance(language, str) else None)
            if proof.get("review_basis") != "fixed_fallback" or fixed is None or fixed[1] != row.content:
                return False
        hashes = proof.get("content_hashes")
        if row.message_type == "text":
            if (
                not isinstance(hashes, list)
                or row.part_index >= len(hashes)
                or hashes[row.part_index] != content_hash(row.content)
            ):
                return False
        elif "orders.view" not in permissions:
            return False
        elif verify_remote:
            if not await authorize_agent_card(session, row, proof, actor):
                return False
        elif [row.part_index, row.card_order_id, row.card_package_id] not in (proof.get("cards") or []):
            return False
        required = proof.get("required_permissions")
        if not isinstance(required, list) or not set(required) <= permissions:
            return False
        if final_local:
            await session.execute(
                select(AgentConfig.id)
                .where(AgentConfig.store_id == row.store_id)
                .order_by(AgentConfig.id)
                .with_for_update()
            )
        agents = await list_enabled_agents(session, row.store_id)
        current_versions = {(str(agent.id), agent.config_version) for agent in agents}
        references = proof.get("agent_versions")
        if (
            not isinstance(references, list)
            or not references
            or any(
                not isinstance(item, list) or len(item) != 2 or tuple(item) not in current_versions
                for item in references
            )
        ):
            return False
        if require_external and not await current_customer_files(
            session, row.store_id, proof.get("file_versions"), lock=final_local
        ):
            return False
    elif row.source_kind in {"welcome", "timeout"}:
        from app.reception.automation import authorize_reception_delivery

        if not await authorize_reception_delivery(session, row, settings):
            return False
    else:
        return False
    if require_external and verify_remote:
        grant, identity, window = await verified_remote_window(session, settings, conversation)
        if not (grant and identity and window):
            return False
        # 所有远端窗口/卡片等待结束后重读可变本地证明，并持锁直到发送结果提交。
        return await authorize_delivery(session, row, settings, require_external=True, verify_remote=False)
    return True


async def authorize_persisted_send(
    session: AsyncSession,
    settings: Settings,
    invocation: ToolInvocation,
    arguments: SendPlatformMessageArguments,
    *,
    verify_remote: bool = True,
) -> AutomationDelivery | None:
    context = invocation.context
    if (
        not context.automation_delivery_id
        or not context.automation_claim_token
        or context.human_confirmed
        or context.actor_type not in {"agent", "job"}
        or arguments.media_token
    ):
        return None
    row = await session.scalar(
        select(AutomationDelivery)
        .where(AutomationDelivery.id == context.automation_delivery_id, AutomationDelivery.store_id == context.store_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        row is None
        or row.status != "dispatching"
        or row.claim_token != context.automation_claim_token
        or row.claimed_until is None
        or utc(row.claimed_until) <= datetime.now(UTC)
        or invocation.idempotency_key != f"automation:{row.id}"
        or row.authorized_by != context.actor_id
        or row.agent_run_id != context.agent_run_id
        or context.actor_type != ("agent" if row.source_kind == "agent" else "job")
    ):
        return None
    if (row.conversation_id, row.content, row.message_type, row.card_order_id, row.card_package_id) != (
        arguments.conversation_id,
        arguments.content,
        arguments.message_type,
        arguments.card_order_id,
        arguments.card_package_id,
    ):
        return None
    return row if await authorize_delivery(session, row, settings, verify_remote=verify_remote) else None
