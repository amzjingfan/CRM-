"""独立于营销执行表的基础接待配置模型。"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base, TimestampMixin


class ReceptionGroup(TimestampMixin, Base):
    __tablename__ = "reception_groups"
    __table_args__ = (
        CheckConstraint("scope IN ('personal', 'team')", name="ck_reception_groups_scope"),
        CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL) OR (scope = 'team' AND owner_user_id IS NULL)",
            name="ck_reception_groups_owner",
        ),
        Index("ix_reception_groups_scope_order", "store_id", "scope", "owner_user_id", "sort_order", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReceptionReply(TimestampMixin, Base):
    __tablename__ = "reception_replies"
    __table_args__ = (
        CheckConstraint("scope IN ('personal', 'team')", name="ck_reception_replies_scope"),
        CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL) OR (scope = 'team' AND owner_user_id IS NULL)",
            name="ck_reception_replies_owner",
        ),
        Index(
            "uq_reception_replies_personal_shortcut",
            "store_id",
            "owner_user_id",
            "shortcut",
            unique=True,
            postgresql_where=text("scope = 'personal'"),
        ),
        Index(
            "uq_reception_replies_team_shortcut",
            "store_id",
            "shortcut",
            unique=True,
            postgresql_where=text("scope = 'team'"),
        ),
        Index("ix_reception_replies_order", "store_id", "scope", "owner_user_id", "sort_order", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reception_groups.id", ondelete="RESTRICT"), nullable=False)
    shortcut: Mapped[str] = mapped_column(String(8), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    site_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    messages: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReceptionPolicy(TimestampMixin, Base):
    __tablename__ = "reception_policies"
    __table_args__ = (
        CheckConstraint("kind IN ('timeout', 'welcome')", name="ck_reception_policies_kind"),
        CheckConstraint("delivery_mode IN ('off', 'preview', 'auto')", name="ck_reception_policies_delivery_mode"),
        CheckConstraint("welcome_idle_hours BETWEEN 1 AND 720", name="ck_reception_policies_welcome_idle"),
        CheckConstraint("revision >= 1", name="ck_reception_policies_revision"),
        CheckConstraint(
            "(kind = 'timeout' AND timeout_minutes BETWEEN 1 AND 43200) OR "
            "(kind = 'welcome' AND timeout_minutes IS NULL)",
            name="ck_reception_policies_timeout",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_from < valid_to", name="ck_reception_policies_dates"
        ),
        Index("ix_reception_policies_kind_order", "kind", "sort_order", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="preview")
    welcome_idle_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timeout_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    stores: Mapped[list["ReceptionPolicyStore"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def store_ids(self) -> list[uuid.UUID]:
        return sorted(item.store_id for item in self.stores)


class ReceptionPolicyStore(Base):
    __tablename__ = "reception_policy_stores"
    __table_args__ = (Index("ix_reception_policy_stores_store_id", "store_id"),)

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reception_policies.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    policy: Mapped[ReceptionPolicy] = relationship(back_populates="stores")


class ReceptionConversationState(TimestampMixin, Base):
    """由可信入站建立的计时器，不扫描历史消息来重放欢迎。"""

    __tablename__ = "reception_conversation_states"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unanswered_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    unanswered_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    timeout_policy_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReceptionMutation(Base):
    """同一用户的配置写入键与已提交响应，同事务支持安全重放。"""

    __tablename__ = "reception_mutations"
    __table_args__ = (UniqueConstraint("actor_id", "key_hash", name="uq_reception_mutations_actor_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    response_body: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    store_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
