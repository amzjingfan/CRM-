"""单客服部按店铺接待配置，默认不启用自动分配。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class ReceptionStoreConfig(TimestampMixin, Base):
    """一间店铺最多由一个部门配置自动接待。"""

    __tablename__ = "reception_store_configs"

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)


class ReceptionAgentConfig(TimestampMixin, Base):
    """一名客服在一间店铺的接待资格、容量与短期在线证据。"""

    __tablename__ = "reception_agent_configs"
    __table_args__ = (CheckConstraint("capacity BETWEEN 1 AND 1000", name="ck_reception_agent_capacity"),)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    auto_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    accepting: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=20, server_default=text("20"), nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
