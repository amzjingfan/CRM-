"""员工部门及其店铺、成员组织关系；不承载 RBAC 授权。"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin


class Department(TimestampMixin, Base):
    """由管理员维护的组织部门。"""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("name", name="uq_departments_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))


department_stores = Table(
    "department_stores",
    Base.metadata,
    Column("department_id", UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
    Column("store_id", UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True),
)

department_members = Table(
    "department_members",
    Base.metadata,
    Column("department_id", UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
