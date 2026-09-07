"""允许平台写结果以 unknown 终态等待人工对账。"""

import sqlalchemy as sa
from alembic import op

revision = "021_message_unknown"
down_revision = "020_knowledge_safety"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """扩展消息状态约束，不改写任何既有消息。"""
    op.drop_constraint("ck_messages_status", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_status",
        "messages",
        "status IN ('received', 'processing', 'sent', 'delivered', 'failed', 'unknown')",
    )


def downgrade() -> None:
    """回滚前把无法由旧契约表示的 unknown 安全降级为 failed。"""
    op.execute(
        sa.text(
            """
            UPDATE messages
            SET status = 'failed',
                error_code = COALESCE(error_code, 'DOWNGRADED_UNKNOWN_STATUS')
            WHERE status = 'unknown'
            """
        )
    )
    op.drop_constraint("ck_messages_status", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_status",
        "messages",
        "status IN ('received', 'processing', 'sent', 'delivered', 'failed')",
    )
