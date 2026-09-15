"""知识服务独立数据所有权测试。"""

from app.knowledge_service.database import KnowledgeBase

EXPECTED_TABLES = {
    "kb_applications",
    "kb_application_space_grants",
    "kb_shop_space_grants",
    "kb_revoked_credentials",
    "kb_coverage_cells",
    "kb_sources",
    "kb_content_versions",
    "kb_content_approvals",
    "kb_index_generations",
    "kb_audit_events",
}


def test_knowledge_metadata_owns_only_independent_tables() -> None:
    """独立 metadata 不得包含 CRM 表或对 CRM 表建外键。"""
    assert set(KnowledgeBase.metadata.tables) == EXPECTED_TABLES

    referenced_tables = {
        foreign_key.target_fullname.split(".", maxsplit=1)[0]
        for table in KnowledgeBase.metadata.tables.values()
        for foreign_key in table.foreign_keys
    }
    assert referenced_tables <= EXPECTED_TABLES
    assert not referenced_tables.intersection({"stores", "users", "knowledge_documents", "knowledge_chunks"})


def test_space_and_content_state_constraints_are_authoritative() -> None:
    """空间、店铺范围和内容三态必须存在于权威模型。"""
    coverage_columns = set(KnowledgeBase.metadata.tables["kb_coverage_cells"].columns.keys())
    application_grant_columns = set(
        KnowledgeBase.metadata.tables["kb_application_space_grants"].columns.keys()
    )
    content_columns = set(KnowledgeBase.metadata.tables["kb_content_versions"].columns.keys())
    index_columns = set(KnowledgeBase.metadata.tables["kb_index_generations"].columns.keys())

    assert {
        "space_code",
        "shop_ref",
        "platform_code",
        "market_code",
        "language_tag",
        "audience_code",
    } <= coverage_columns
    assert {
        "space_code",
        "platform_code",
        "market_code",
        "language_tag",
        "audience_code",
    } <= application_grant_columns
    assert {
        "content_status",
        "approval_status",
        "effective_from",
        "effective_until",
        "content_sha256",
    } <= content_columns
    assert {"index_state", "embedding_model", "embedding_dimensions", "activated_at"} <= index_columns


def test_audit_table_cannot_persist_query_or_token_body() -> None:
    """审计表只保存低敏决策元数据，不预留正文字段。"""
    audit_columns = set(KnowledgeBase.metadata.tables["kb_audit_events"].columns.keys())

    assert {"request_id", "application_ref", "decision", "reason_code", "jti_hash", "created_at"} <= audit_columns
    assert not audit_columns.intersection({"query", "query_text", "token", "authorization", "content_text"})
