"""人工审阅后的不可变交付计划及各段发送结果。"""

import uuid

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class ReplyBatch(TimestampMixin, Base):
    __tablename__ = "agent_reply_batches"
    __table_args__ = (UniqueConstraint("scope_key", "idempotency_key", name="uq_agent_reply_batch_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"))
    authorized_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    state_json: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
