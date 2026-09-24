"""第三方 Webhook 与 OAuth 短期任务 ORM 模型。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class WebhookEvent(TimestampMixin, Base):
    """先落库再异步处理的第三方事件。"""

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("platform", "external_event_id", name="uq_webhook_platform_event"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(30))
    channel_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channel_accounts.id", ondelete="SET NULL"), nullable=True
    )
    external_event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100))
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_hash: Mapped[str] = mapped_column(String(128))
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="received")
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TikTokOAuthJob(TimestampMixin, Base):
    """一次性授权回调任务；state 和 code 仅以短期认证密文暂存。"""

    __tablename__ = "tiktok_oauth_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    state_cipher: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    code_cipher: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
