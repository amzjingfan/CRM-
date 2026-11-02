"""普通自动消息投递账本；unknown 永不自动重试。"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class AutomationDelivery(TimestampMixin, Base):
    __tablename__ = "automation_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "conversation_id",
            "source_kind",
            "source_key",
            "part_index",
            name="uq_automation_delivery_source_part",
        ),
        CheckConstraint("source_kind IN ('agent', 'welcome', 'timeout')", name="ck_automation_delivery_source"),
        CheckConstraint("mode IN ('preview', 'auto')", name="ck_automation_delivery_mode"),
        CheckConstraint(
            "status IN ('pending', 'claimed', 'dispatching', 'previewed', 'succeeded', "
            "'cancelled', 'failed', 'unknown')",
            name="ck_automation_delivery_status",
        ),
        CheckConstraint("part_index >= 0 AND attempt_count >= 0", name="ck_automation_delivery_counts"),
        Index("idx_automation_delivery_due", "status", "not_before", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    part_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="text", nullable=False)
    card_order_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    card_package_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    remote_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
