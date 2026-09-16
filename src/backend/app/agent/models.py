"""Agent 运行追踪 ORM 模型。"""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class AgentRun(TimestampMixin, Base):
    """保存一次 Agent 执行的模型、Prompt、置信度、耗时和最终动作。"""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('auto_reply', 'human_review', 'transfer_human', 'failed')",
            name="ck_agent_runs_action",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'timeout')",
            name="ck_agent_runs_status",
        ),
        CheckConstraint(
            "intent_confidence IS NULL OR (intent_confidence >= 0 AND intent_confidence <= 1)",
            name="ck_agent_runs_intent_confidence",
        ),
        CheckConstraint(
            "retrieval_score IS NULL OR (retrieval_score >= 0 AND retrieval_score <= 1)",
            name="ck_agent_runs_retrieval_score",
        ),
        CheckConstraint(
            "final_confidence IS NULL OR (final_confidence >= 0 AND final_confidence <= 1)",
            name="ck_agent_runs_final_confidence",
        ),
        Index("idx_agent_runs_conversation_created", "conversation_id", "created_at"),
        Index("idx_agent_runs_store_created", "store_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intent_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    retrieval_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    final_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_output_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
