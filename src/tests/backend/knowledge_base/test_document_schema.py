"""通用文档与 FAQ 分表、整版本切换的结构契约。"""

from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.knowledge_base.document_models import (
    KnowledgeFile,
    KnowledgeFileChunk,
    KnowledgeFileImportReceipt,
    KnowledgeFileSettings,
    KnowledgeFileUnit,
    KnowledgeFileVersion,
)
from app.knowledge_base.models import KnowledgeChunk


def test_independently_deployed_reception_and_document_migrations_join_one_head() -> None:
    """两条 029 已分别在环境落地，合流必须保留两个历史 revision。"""
    migration_path = Path(__file__).resolve().parents[3] / "backend" / "migrations"
    scripts = ScriptDirectory(str(migration_path))
    assert scripts.get_heads() == ["044_reception_assignment"]
    assert scripts.get_revision("044_reception_assignment").down_revision == "043_logistics_updates"
    assert scripts.get_revision("043_logistics_updates").down_revision == "042_agent_reply_delivery"
    assert scripts.get_revision("042_agent_reply_delivery").down_revision == "041_merge_agent_multishop_collab"
    assert set(scripts.get_revision("041_merge_agent_multishop_collab").down_revision) == {
        "040_agent_collaboration",
        "035_tiktok_seller_multishop",
    }
    assert scripts.get_revision("040_agent_collaboration").down_revision == "039_agent_run_hierarchy"
    assert scripts.get_revision("035_tiktok_seller_multishop").down_revision == "034_agent_debug_runs"
    assert scripts.get_revision("034_agent_debug_runs").down_revision == "033_file_version_approval"
    assert scripts.get_revision("032_knowledge_file_archive").down_revision == "031_reception_policy_schedule"
    assert scripts.get_revision("031_reception_policy_schedule").down_revision == "030_merge_rag_reception"
    assert set(scripts.get_revision("030_merge_rag_reception").down_revision) == {
        "029_knowledge_file_ingestion",
        "029_reception_group_enabled",
    }


def test_file_vectors_are_separate_and_fixed_to_bge_dimension() -> None:
    """新文档在检索未接入前不得混入 FAQ 现有检索表。"""
    assert KnowledgeFileChunk.__tablename__ == "knowledge_file_chunks"
    assert KnowledgeFileChunk.__table__ is not KnowledgeChunk.__table__
    assert KnowledgeFileChunk.__table__.c.embedding.type.dim == 1024
    assert {
        "store_id",
        "file_id",
        "version_id",
        "unit_index",
        "content_hash",
        "source_locator",
    } <= set(KnowledgeFileChunk.__table__.c.keys())


def test_version_status_and_active_pointer_support_whole_version_review() -> None:
    """待复核状态与有效版本指针必须同时存在，不能用页状态替代版本状态。"""
    assert KnowledgeFile.__table__.c.active_version_number.nullable
    assert KnowledgeFile.__table__.c.archived_at.nullable
    assert "review_required" in " ".join(
        str(constraint.sqltext)
        for constraint in KnowledgeFileVersion.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert any(
        {"file_id", "version_number"} == {column.name for column in constraint.columns}
        for constraint in KnowledgeFileVersion.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert {"unit_index", "issue_codes", "reviewed_by", "reviewed_at"} <= set(KnowledgeFileUnit.__table__.c.keys())
    assert KnowledgeFileSettings.__table__.c.store_id.primary_key


def test_import_identity_is_persisted_for_casefolded_names_and_idempotency() -> None:
    assert "filename_key" in KnowledgeFile.__table__.c
    assert {"idempotency_key_hash", "request_fingerprint", "version_id"} <= set(
        KnowledgeFileImportReceipt.__table__.c.keys()
    )
