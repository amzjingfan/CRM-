"""每日运营指标 ORM 模型。"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class MetricDaily(TimestampMixin, Base):
    """按店铺本地自然日保存可重建的运营指标。"""

    __tablename__ = "metric_daily"
    __table_args__ = (
        UniqueConstraint("store_id", "metric_date", name="uq_metric_daily_store_date"),
        Index("idx_metric_daily_store_date", "store_id", "metric_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    aggregation_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregation_version: Mapped[str] = mapped_column(String(30), default="v1", nullable=False)
    session_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transfer_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transfer_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"), nullable=False)
    avg_response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovered_gmv: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    channel_breakdown: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict, nullable=False)
    intent_breakdown: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict, nullable=False)
    rag_run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rag_hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_output_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    p95_first_output_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        default=Decimal("0"),
        nullable=False,
    )
    # 准确率只能来自人工或版本化评测标签；无标签线上流量保持 0/NULL。
    intent_labeled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intent_correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
