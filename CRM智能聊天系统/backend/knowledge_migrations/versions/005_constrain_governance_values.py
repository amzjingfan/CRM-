"""约束覆盖、权利、空间和风险治理值域。

Revision ID: 005_kb_governance_constraints
Revises: 004_kb_security
Create Date: 2026-09-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005_kb_governance_constraints"
down_revision: str | None = "004_kb_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """先将无法证明的历史值降级为安全状态，再由数据库锁定值域。"""
    op.execute(
        "UPDATE kb_coverage_cells SET coverage_status = '待审批' "
        "WHERE coverage_status NOT IN ('资料待获取', '待审批', '已生效', '已过期', '不适用')"
    )
    op.execute(
        "UPDATE kb_sources SET rights_review_status = '未审' "
        "WHERE rights_review_status NOT IN ('未审', '允许受限使用', '拒绝', '已撤销')"
    )
    op.execute(
        "UPDATE kb_sources SET allowed_app_refs = '[]'::json "
        "WHERE json_typeof(allowed_app_refs) <> 'array'"
    )
    op.execute(
        "UPDATE kb_sources SET allowed_space_codes = '[]'::json "
        "WHERE json_typeof(allowed_space_codes) <> 'array' OR NOT "
        "(allowed_space_codes::jsonb <@ '[\"company_shared\", \"shop_private\"]'::jsonb)"
    )
    op.execute(
        "UPDATE kb_content_versions SET risk_level = '高' "
        "WHERE risk_level NOT IN ('低', '中', '高')"
    )

    constraints = (
        (
            "kb_coverage_cells",
            "ck_kb_coverage_status",
            "coverage_status IN ('资料待获取', '待审批', '已生效', '已过期', '不适用')",
        ),
        (
            "kb_sources",
            "ck_kb_source_rights_status",
            "rights_review_status IN ('未审', '允许受限使用', '拒绝', '已撤销')",
        ),
        (
            "kb_sources",
            "ck_kb_source_allowed_apps_array",
            "json_typeof(allowed_app_refs) = 'array'",
        ),
        (
            "kb_sources",
            "ck_kb_source_allowed_spaces",
            "json_typeof(allowed_space_codes) = 'array' AND "
            "allowed_space_codes::jsonb <@ '[\"company_shared\", \"shop_private\"]'::jsonb",
        ),
        (
            "kb_content_versions",
            "ck_kb_content_risk_level",
            "risk_level IN ('低', '中', '高')",
        ),
    )
    for table, name, condition in constraints:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    """只解除值域门禁，不伪造被降级前的无效历史值。"""
    constraints = (
        ("kb_content_versions", "ck_kb_content_risk_level"),
        ("kb_sources", "ck_kb_source_allowed_spaces"),
        ("kb_sources", "ck_kb_source_allowed_apps_array"),
        ("kb_sources", "ck_kb_source_rights_status"),
        ("kb_coverage_cells", "ck_kb_coverage_status"),
    )
    for table, name in constraints:
        op.drop_constraint(name, table, type_="check")
