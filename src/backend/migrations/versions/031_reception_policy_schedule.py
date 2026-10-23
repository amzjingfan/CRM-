"""保存接待策略按店铺时区解释的日期和每日时段，仅供配置展示。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "031_reception_policy_schedule"
down_revision = "030_merge_rag_reception"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reception_policies", sa.Column("schedule", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM reception_policies WHERE schedule IS NOT NULL)")):
        raise RuntimeError("接待策略已有新有效期配置，不能无损降级；请使用部署备份恢复")
    op.drop_column("reception_policies", "schedule")
