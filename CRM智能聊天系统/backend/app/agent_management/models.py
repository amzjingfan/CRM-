"""Agent 运营配置和可靠任务 ORM 模型。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class AgentConfig(TimestampMixin, Base):
    """店铺级运营配置；模型、Prompt 和阈值仍由 AI 运行配置只读提供。"""

    __tablename__ = "agent_configs"
    __table_args__ = (
        Index(
            "uq_agent_configs_store_code_active",
            "store_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_agent_configs_one_enabled_per_store",
            "store_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status = 'enabled'"),
        ),
        Index("idx_agent_configs_store_status", "store_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="disabled", nullable=False)
    enabled_tools: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    knowledge_scope: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        default=lambda: {"mode": "store_ready_faq"},
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTask(TimestampMixin, Base):
    """入站消息到 Agent 自动决策之间的可靠任务。"""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        Index("idx_agent_tasks_due", "status", "next_attempt_at", "created_at"),
        Index("idx_agent_tasks_store_created", "store_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    trigger_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
