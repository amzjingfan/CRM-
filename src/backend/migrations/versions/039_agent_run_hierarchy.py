"""add dynamic Agent parent-child run hierarchy and phase

Revision ID: 039_agent_run_hierarchy
Revises: 038_agent_session_memory
"""

import sqlalchemy as sa
from alembic import op

revision = "039_agent_run_hierarchy"
down_revision = "038_agent_session_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("parent_run_id", sa.UUID(), nullable=True))
    op.add_column("agent_runs", sa.Column("config_version", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("phase", sa.String(length=30), nullable=True))
    op.create_foreign_key(
        "fk_agent_runs_parent",
        "agent_runs",
        "agent_runs",
        ["parent_run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_agent_runs_parent", "agent_runs", ["parent_run_id"])


def downgrade() -> None:
    op.drop_index("idx_agent_runs_parent", table_name="agent_runs")
    op.drop_constraint("fk_agent_runs_parent", "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "phase")
    op.drop_column("agent_runs", "config_version")
    op.drop_column("agent_runs", "parent_run_id")
