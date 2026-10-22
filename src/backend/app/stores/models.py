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

    @property
    def alias(self) -> str | None:
        value = (self.metadata_json or {}).get("alias")
        return value if isinstance(value, str) and value else None


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

    @property
    def site(self) -> str | None:
        value = (self.metadata_json or {}).get("region")
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _metadata_time(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo is not None else None
        except ValueError:
            return None

    @property
    def authorization_expires_at(self) -> datetime | None:
        metadata = self.metadata_json or {}
        dates = [
            self._metadata_time(metadata.get("refresh_token_expires_at")),
            self._metadata_time(metadata.get("authorization_expires_at")),
        ]
        valid = [value for value in dates if value is not None]
        return min(valid) if valid else None

    @property
    def authorization_status(self) -> str | None:
        value = (self.metadata_json or {}).get("oauth_status")
        return (
            value
            if isinstance(value, str) and value in {"revoked", "deauthorized", "reauthorization_required", "refreshed"}
            else None
        )

    @property
    def last_authorized_at(self) -> datetime | None:
        return self._metadata_time((self.metadata_json or {}).get("last_authorized_at")) or self.created_at
