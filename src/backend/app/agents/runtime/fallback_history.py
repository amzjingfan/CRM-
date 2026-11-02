"""正式建议与只读调试共用的可信第三轮历史判定。"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestration.fallback import UNRESOLVED_REASONS, prior_question_reasons
from app.agents.runtime.models import AgentRun
from app.agents.runtime.snapshot import RunSnapshot
from app.conversations.models import Conversation, Message


async def fallback_due_from_history(
    session: AsyncSession,
    snapshot: RunSnapshot,
    source_message_ids: Sequence[uuid.UUID],
    *,
    current_message_id: uuid.UUID | None = None,
) -> bool:
    previous = tuple(dict.fromkeys(item for item in source_message_ids if item != current_message_id))[-2:]
    if len(previous) != 2 or snapshot.debug_without_conversation or not set(previous) <= set(snapshot.message_ids):
        return False
    trusted = tuple(
        (
            await session.scalars(
                select(Message.id)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(
                    Message.id.in_(previous),
                    Message.store_id == snapshot.store_id,
                    Message.conversation_id == snapshot.conversation_id,
                    Message.customer_id == snapshot.customer_id,
                    Message.direction == "inbound",
                    Message.role == "user",
                    Message.external_message_id != "",
                    Conversation.store_id == snapshot.store_id,
                    Conversation.customer_id == snapshot.customer_id,
                    Message.platform == Conversation.platform,
                )
            )
        ).all()
    )
    if set(trusted) != set(previous):
        return False
    runs = (
        await session.scalars(
            select(AgentRun)
            .where(
                AgentRun.store_id == snapshot.store_id,
                AgentRun.conversation_id == snapshot.conversation_id,
                AgentRun.parent_run_id.is_(None),
                AgentRun.trigger_message_id.in_(previous),
                AgentRun.input_summary.like("mode=formal-v2%"),
            )
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        )
    ).all()
    reasons = prior_question_reasons(previous, runs)
    return len(reasons) == 2 and all(reason in UNRESOLVED_REASONS for reason in reasons)
