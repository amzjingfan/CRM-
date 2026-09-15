"""店铺和第三方平台账号 ORM 模型。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class Store(TimestampMixin, Base):
    """CRM 数据隔离的最小租户单元。"""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelAccount(TimestampMixin, Base):
    """店铺在外部平台上的授权账号；只保存密钥引用，不保存明文密钥。"""

    __tablename__ = "channel_accounts"
    __table_args__ = (
        UniqueConstraint("platform", "external_store_id", name="uq_channel_platform_store"),
        Index(
            "uq_channel_accounts_store_tiktok",
            "store_id",
            unique=True,
            postgresql_where=text("platform = 'tiktok'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(30))
    external_store_id: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    access_token_ref: Mapped[str] = mapped_column(String(500))
    refresh_token_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="connected")
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, default=dict)
