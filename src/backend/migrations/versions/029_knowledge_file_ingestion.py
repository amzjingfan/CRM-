"""为通用 RAG 文件建立与 FAQ 隔离的版本和向量表。"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "029_knowledge_file_ingestion"
down_revision = "028_basic_reception_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_categories.id", ondelete="SET NULL"),
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("filename_key", sa.String(255), nullable=False),
        sa.Column("active_version_number", sa.Integer()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_files_store_id", "knowledge_files", ["store_id"])
    op.create_index(
        "uq_knowledge_files_store_filename_active",
        "knowledge_files",
        ["store_id", "filename_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_file_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_object_key", sa.String(500), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("parser_version", sa.String(50)),
        sa.Column("cleaning_version", sa.String(30), nullable=False),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("file_id", "version_number", name="uq_knowledge_file_version_number"),
        sa.CheckConstraint(
            "status IN ('queued', 'parsing', 'review_required', 'indexing', 'ready', "
            "'failed_retryable', 'failed_final')",
            name="ck_knowledge_file_version_status",
        ),
    )
    op.create_index("ix_knowledge_file_versions_store_id", "knowledge_file_versions", ["store_id"])
    op.create_index(
        "ix_knowledge_file_version_claim", "knowledge_file_versions", ["status", "lease_until", "created_at"]
    )

    op.create_table(
        "knowledge_file_import_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_file_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "store_id", "created_by", "idempotency_key_hash", name="uq_knowledge_file_import_receipt_key"
        ),
    )

    op.create_table(
        "knowledge_file_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_file_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("unit_kind", sa.String(30), nullable=False),
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
        sa.Column("blocks_json", postgresql.JSONB(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("cleaned_text", sa.Text(), nullable=False),
        sa.Column("issue_codes", postgresql.JSONB(), nullable=False),
        sa.Column("parse_mode", sa.String(30), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version_id", "unit_index", name="uq_knowledge_file_unit_index"),
    )
    op.create_index("ix_knowledge_file_units_store_id", "knowledge_file_units", ["store_id"])
    op.create_index("ix_knowledge_file_units_version_id", "knowledge_file_units", ["version_id"])

    op.create_table(
        "knowledge_file_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_file_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("strategy", sa.String(40), nullable=False),
        sa.Column("heading_path", postgresql.JSONB(), nullable=False),
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
        sa.Column("parser_version", sa.String(50), nullable=False),
        sa.Column("cleaning_version", sa.String(30), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("embedding_revision", sa.String(100), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version_id", "chunk_index", name="uq_knowledge_file_chunk_index"),
    )
    op.create_index("ix_knowledge_file_chunks_store_id", "knowledge_file_chunks", ["store_id"])
    op.create_index("ix_knowledge_file_chunks_version_id", "knowledge_file_chunks", ["version_id"])

    op.create_table(
        "knowledge_file_settings",
        sa.Column(
            "store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("strategy", sa.String(40), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("overlap", sa.Integer(), nullable=False),
        sa.Column("parser_mode", sa.String(20), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column(
            "updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "chunk_size > 0 AND overlap >= 0 AND overlap < chunk_size", name="ck_knowledge_file_settings_chunk"
        ),
    )


def downgrade() -> None:
    op.drop_table("knowledge_file_settings")
    op.drop_index("ix_knowledge_file_chunks_version_id", table_name="knowledge_file_chunks")
    op.drop_index("ix_knowledge_file_chunks_store_id", table_name="knowledge_file_chunks")
    op.drop_table("knowledge_file_chunks")
    op.drop_index("ix_knowledge_file_units_version_id", table_name="knowledge_file_units")
    op.drop_index("ix_knowledge_file_units_store_id", table_name="knowledge_file_units")
    op.drop_table("knowledge_file_units")
    op.drop_index("ix_knowledge_file_version_claim", table_name="knowledge_file_versions")
    op.drop_index("ix_knowledge_file_versions_store_id", table_name="knowledge_file_versions")
    op.drop_table("knowledge_file_import_receipts")
    op.drop_table("knowledge_file_versions")
    op.drop_index("uq_knowledge_files_store_filename_active", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_store_id", table_name="knowledge_files")
    op.drop_table("knowledge_files")
