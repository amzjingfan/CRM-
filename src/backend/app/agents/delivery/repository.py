"""短事务行锁保证同一计划只领取一次；不在平台网络调用期间持锁。"""

import uuid
from copy import deepcopy
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.delivery.batches import (
    BatchState,
    PartState,
    check_request,
    claim_part,
    finish_part,
    new_state,
    reject_part,
)
from app.agents.delivery.contracts import ReplyBatchRequest
from app.agents.delivery.models import ReplyBatch
from app.conversations.models import Message
from app.workspace.schemas import MessageView


class SqlBatchStore:
    def __init__(self, session: AsyncSession, store_id: uuid.UUID, conversation_id: uuid.UUID, actor_id: uuid.UUID):
        self.session = session
        self.store_id, self.conversation_id, self.actor_id = store_id, conversation_id, actor_id

    async def _row(self, scope: str, key: str) -> ReplyBatch | None:
        row = await self.session.scalar(
            select(ReplyBatch)
            .where(
                ReplyBatch.scope_key == scope,
                ReplyBatch.idempotency_key == key,
                ReplyBatch.store_id == self.store_id,
                ReplyBatch.conversation_id == self.conversation_id,
                ReplyBatch.authorized_by == self.actor_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        return row

    async def start(self, scope: str, key: str, payload: ReplyBatchRequest) -> BatchState:
        row = await self._row(scope, key)
        if row is None:
            state = new_state(payload)
            row = ReplyBatch(
                id=uuid.UUID(cast(str, state["id"])),
                scope_key=scope,
                idempotency_key=key,
                store_id=self.store_id,
                conversation_id=self.conversation_id,
                authorized_by=self.actor_id,
                payload_json=payload.model_dump(mode="json"),
                state_json=state,
            )
            self.session.add(row)
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                row = await self._row(scope, key)
                if row is None:
                    raise
        state = deepcopy(row.state_json)
        check_request(state, payload)
        await self.session.commit()
        return state

    async def read(self, scope: str, key: str) -> BatchState:
        row = await self._row(scope, key)
        assert row is not None
        state = deepcopy(row.state_json)
        # 复用原消息人工对账结果，平台unknown未被明确解决前绝不自动重试。
        for part in cast(list[PartState], state["parts"]):
            if part["status"] != "unknown":
                continue
            attempt_key = f"reply:{state['id']}:{part['index']}:{part['attempt']}"
            message = await self.session.scalar(
                select(Message).where(
                    Message.store_id == self.store_id,
                    Message.conversation_id == self.conversation_id,
                    Message.idempotency_key == attempt_key,
                    Message.status.in_(("sent", "failed")),
                )
            )
            if message is not None:
                from app.workspace.service import _message_view

                finish_part(state, cast(int, part["index"]), attempt_key, _message_view(message))
        row.state_json = state
        await self.session.commit()
        return deepcopy(state)

    async def claim(self, scope: str, key: str, index: int) -> str | None:
        row = await self._row(scope, key)
        assert row is not None
        state = deepcopy(row.state_json)
        attempt_key = claim_part(state, index)
        row.state_json = state
        await self.session.commit()
        return attempt_key

    async def finish(self, scope: str, key: str, index: int, attempt_key: str, message: MessageView) -> None:
        row = await self._row(scope, key)
        assert row is not None
        state = deepcopy(row.state_json)
        finish_part(state, index, attempt_key, message)
        row.state_json = state
        await self.session.commit()

    async def reject(self, scope: str, key: str, index: int, attempt_key: str, code: str) -> None:
        row = await self._row(scope, key)
        assert row is not None
        state = deepcopy(row.state_json)
        reject_part(state, index, attempt_key, code)
        row.state_json = state
        await self.session.commit()
