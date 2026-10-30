"""已发布 Agent 配置的不可变版本快照。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class AgentConfigVersion(Base):
    """一次发布写入一行；运行引用此行而非可编辑草稿。"""

    __tablename__ = "agent_config_versions"
    __table_args__ = (
        UniqueConstraint("agent_config_id", "version", name="uq_agent_config_versions_number"),
        Index("idx_agent_config_versions_store_config", "store_id", "agent_config_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    prompt_sections: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_names: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    file_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    ready_for_v2: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    template_source_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
