"""为 AI 营销草稿审核增加持久化幂等边界。"""

import sqlalchemy as sa
from alembic import op

revision = "023_marketing_review_idempotency"
down_revision = "022_ai_marketing_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """保存审核键和请求摘要，并限制同一店铺内的键只能使用一次。"""
    op.add_column(
        "marketing_events",
        sa.Column("ai_review_idempotency_key", sa.String(200), nullable=True),
    )
    op.add_column(
        "marketing_events",
        sa.Column("ai_review_request_hash", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "ck_marketing_events_ai_review_idempotency_pair",
        "marketing_events",
        "(ai_review_idempotency_key IS NULL AND ai_review_request_hash IS NULL) OR "
        "(ai_review_idempotency_key IS NOT NULL AND ai_review_request_hash IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_marketing_events_store_review_idempotency",
        "marketing_events",
        ["store_id", "ai_review_idempotency_key"],
    )


def downgrade() -> None:
    """移除审核幂等字段，不改变已经形成的人工审核终态。"""
    op.drop_constraint(
        "uq_marketing_events_store_review_idempotency",
        "marketing_events",
        type_="unique",
    )
    op.drop_constraint(
        "ck_marketing_events_ai_review_idempotency_pair",
        "marketing_events",
        type_="check",
    )
    op.drop_column("marketing_events", "ai_review_request_hash")
    op.drop_column("marketing_events", "ai_review_idempotency_key")
