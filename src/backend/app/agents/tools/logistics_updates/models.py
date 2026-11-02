"""物流基线和通知台账；迁移及集中注册由集成任务统一维护。"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class LogisticsObservationRow(Base):
    __tablename__ = "agent_logistics_observations"
    __table_args__ = (Index("idx_agent_logistics_observations_store_order", "store_id", "order_id"),)

    scope_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    package_id: Mapped[str] = mapped_column(String(200), nullable=False)
    latest_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LogisticsNotification(Base):
    __tablename__ = "agent_logistics_notifications"
    __table_args__ = (
        Index("idx_agent_logistics_notifications_store_state", "store_id", "state"),
        Index("idx_agent_logistics_notifications_scope", "store_id", "scope_key"),
        Index("idx_agent_logistics_notifications_recovery", "state", "review_lease_expires_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    scope_key: Mapped[str] = mapped_column(
        ForeignKey("agent_logistics_observations.scope_key", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    context_json: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    authorization_json: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, server_default="{}", nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="preview")
    delivery_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_claim_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    review_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LogisticsNotificationPolicy(Base):
    __tablename__ = "agent_logistics_notification_policies"
    __table_args__ = (
        CheckConstraint("mode IN ('preview', 'external')", name="ck_logistics_policy_mode"),
        CheckConstraint("NOT enabled OR enabled_at IS NOT NULL", name="ck_logistics_policy_enabled_cutoff"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("agent_configs.id", ondelete="SET NULL"))
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="preview", server_default="preview", nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LogisticsOrderScan(Base):
    __tablename__ = "agent_logistics_order_scans"
    __table_args__ = (Index("idx_logistics_order_scans_due", "next_poll_at", "claimed_until"),)

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reason: Mapped[str | None] = mapped_column(String(80))
