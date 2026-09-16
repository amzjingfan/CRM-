"""补齐 Phase 4 AI 首输出、质量、工具、Token 与成本聚合字段。"""

import sqlalchemy as sa
from alembic import op

revision = "018_ai_observability"
down_revision = "017_phase4_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加低敏可重建指标；意图准确率字段只接收有标签数据。"""
    op.add_column("agent_runs", sa.Column("first_output_latency_ms", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_agent_runs_first_output_latency",
        "agent_runs",
        "first_output_latency_ms IS NULL OR first_output_latency_ms >= 0",
    )
    columns = (
        sa.Column("rag_run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rag_hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tool_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tool_success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_output_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("p95_first_output_latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("intent_labeled_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("intent_correct_count", sa.Integer(), server_default="0", nullable=False),
    )
    for column in columns:
        op.add_column("metric_daily", column)
    op.create_check_constraint(
        "ck_metric_daily_ai_counts",
        "metric_daily",
        "rag_run_count >= 0 AND rag_hit_count >= 0 AND rag_hit_count <= rag_run_count "
        "AND tool_call_count >= 0 AND tool_success_count >= 0 AND tool_success_count <= tool_call_count "
        "AND first_output_count >= 0 AND input_tokens >= 0 AND output_tokens >= 0 "
        "AND estimated_cost_usd >= 0 AND intent_labeled_count >= 0 "
        "AND intent_correct_count >= 0 AND intent_correct_count <= intent_labeled_count",
    )
    op.create_check_constraint(
        "ck_metric_daily_first_output_latency",
        "metric_daily",
        "p95_first_output_latency_ms IS NULL OR p95_first_output_latency_ms >= 0",
    )


def downgrade() -> None:
    """移除派生可观测字段，不删除已有 Agent、消息或营销事实。"""
    op.drop_constraint("ck_metric_daily_first_output_latency", "metric_daily", type_="check")
    op.drop_constraint("ck_metric_daily_ai_counts", "metric_daily", type_="check")
    for column_name in (
        "intent_correct_count",
        "intent_labeled_count",
        "estimated_cost_usd",
        "output_tokens",
        "input_tokens",
        "p95_first_output_latency_ms",
        "first_output_count",
        "tool_success_count",
        "tool_call_count",
        "rag_hit_count",
        "rag_run_count",
    ):
        op.drop_column("metric_daily", column_name)
    op.drop_constraint("ck_agent_runs_first_output_latency", "agent_runs", type_="check")
    op.drop_column("agent_runs", "first_output_latency_ms")
