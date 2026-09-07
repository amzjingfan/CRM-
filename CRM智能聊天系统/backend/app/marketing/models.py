"""客户评价、营销活动和事件 ORM 模型。"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class CustomerReview(TimestampMixin, Base):
    """标准化后的平台评价，用于中差评触发和转化判断。"""

    __tablename__ = "customer_reviews"
    __table_args__ = (
        UniqueConstraint("store_id", "platform", "external_review_id", name="uq_review_store_platform_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(30))
    external_review_id: Mapped[str] = mapped_column(String(200))
    rating: Mapped[int] = mapped_column(Integer)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class MarketingCampaign(TimestampMixin, Base):
    """店铺级主动营销规则和内容配置。"""

    __tablename__ = "marketing_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    trigger_type: Mapped[str] = mapped_column(String(30))
    action_type: Mapped[str] = mapped_column(String(40))
    content_mode: Mapped[str] = mapped_column(String(20))
    template_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trigger_delay_minutes: Mapped[int] = mapped_column(Integer, default=30)
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24)
    max_contacts_30d: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class MarketingEvent(TimestampMixin, Base):
    """营销触发、执行、失败重试和转化的可追踪事件。"""

    __tablename__ = "marketing_events"
    __table_args__ = (
        CheckConstraint(
            "ai_review_status IS NULL OR ai_review_status IN ('pending','approved','rejected')",
            name="ck_marketing_events_ai_review_status",
        ),
        CheckConstraint(
            "(ai_review_idempotency_key IS NULL AND ai_review_request_hash IS NULL) OR "
            "(ai_review_idempotency_key IS NOT NULL AND ai_review_request_hash IS NOT NULL)",
            name="ck_marketing_events_ai_review_idempotency_pair",
        ),
        Index("idx_marketing_events_store_review", "store_id", "ai_review_status", "created_at"),
        UniqueConstraint(
            "store_id",
            "ai_review_idempotency_key",
            name="uq_marketing_events_store_review_idempotency",
        ),
        UniqueConstraint("campaign_id", "source_type", "source_id", name="uq_marketing_event_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tool_call_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 草稿仅供具备营销权限的员工审核，不进入日志，也不代表平台发送授权。
    ai_draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_draft_agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    ai_review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ai_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 键和请求摘要只服务于人工审核重放，不包含评论原文或营销草稿正文。
    ai_review_idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_review_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
