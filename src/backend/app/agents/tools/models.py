"""Agent 生成的内部协作记录，不属于平台消息或实际转交。"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class AgentCollaborationEntry(TimestampMixin, Base):
    __tablename__ = "agent_collaboration_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('handoff_request', 'internal_note')", name="ck_agent_collaboration_kind"),
        UniqueConstraint(
            "store_id", "conversation_id", "agent_run_id", "kind", "content_hash", name="uq_agent_collaboration_replay"
        ),
        Index("ix_agent_collaboration_conversation", "store_id", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
