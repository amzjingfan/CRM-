"""为低敏审计事件补充端到端追踪标识。

Revision ID: 003_kb_audit_trace
Revises: 002_kb_governance
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_kb_audit_trace"
down_revision: str | None = "002_kb_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立响应 trace_id 与审计事件的一对一关联。"""
    op.add_column(
        "kb_audit_events",
        sa.Column(
            "trace_id",
            sa.String(length=36),
            nullable=False,
            server_default="migration-unknown",
        ),
    )
    op.alter_column("kb_audit_events", "trace_id", server_default=None)
    op.create_index(op.f("ix_kb_audit_events_trace_id"), "kb_audit_events", ["trace_id"])


def downgrade() -> None:
    """回退追踪标识字段，不改动其他低敏审计数据。"""
    op.drop_index(op.f("ix_kb_audit_events_trace_id"), table_name="kb_audit_events")
    op.drop_column("kb_audit_events", "trace_id")
