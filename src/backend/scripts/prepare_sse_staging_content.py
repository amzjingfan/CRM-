"""只处理 R05 已核对的 G5 隔离店铺合成内容与短期凭证。"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import stat
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chunking import FaqTokenChunker
from app.agent.factory import build_embedding_service
from app.agent.vectorization import KnowledgeVectorizationService
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgeEntryCreate,
    KnowledgePublicationApproval,
    KnowledgeStatementType,
)
from app.knowledge_base.service import content_hash, create_entry, set_entry_status
from app.knowledge_base.vector_port import SqlAlchemyKnowledgeVectorPort
from app.shared.config.settings import Settings, get_settings
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.database.session import session_factory
from app.stores.models import Store
from scripts.prepare_sse_staging_fixture import (
    G5_LEGACY_ANSWER,
    G5_LEGACY_QUESTION,
    G5_ORIGINAL_QUESTION,
    G5_SYNTHETIC_ANSWER,
    G5_SYNTHETIC_ANSWER_V2,
    G5_SYNTHETIC_QUESTION,
    ReconciliationManifest,
    build_renewed_credentials,
    current_container_paths_are_safe,
    validate_database_target,
    validate_reconciliation_payload,
    verify_g5_content_snapshot,
    write_secure_pool,
)

SOURCE_NAME = "g5-38852775454-2.json"
CREDENTIAL_PREFIX = "g5-38852775454-"
FAQ_SOURCE = "g5-synthetic-only"


@dataclass(frozen=True)
class ContentSnapshot:
    state: str
    approver: User
    messages: list[Message]
    document: KnowledgeDocument | None


def assert_single_vector_target(
    manifest: ReconciliationManifest, snapshot: ContentSnapshot
) -> tuple[uuid.UUID, uuid.UUID, int]:
    """只允许原隔离店铺中刚发布、尚未向量化的唯一合成 FAQ。"""
    document = snapshot.document
    if (
        (snapshot.state, document.document_version if document is not None else None)
        not in {("legacy_prepared", 1), ("prepared", 2), ("prepared_v3", 3)}
        or document is None
        or document.store_id != manifest.store_id
        or document.source != FAQ_SOURCE
        or document.status != "published"
        or document.vectorization_status != "pending"
        or document.deleted_at is not None
    ):
        raise ValueError("G5 vector target mismatch")
    return document.id, manifest.store_id, document.document_version


def assert_replacement_target(manifest: ReconciliationManifest, snapshot: ContentSnapshot) -> None:
    """一次性替换只接受已向量化的原隔离 FAQ 和完整的旧 50 条提问。"""
    document = snapshot.document
    if (
        snapshot.state != "legacy_prepared"
        or len(snapshot.messages) != 50
        or document is None
        or document.store_id != manifest.store_id
        or document.source != FAQ_SOURCE
        or document.source_type != "faq"
        or document.tags != ["g5-synthetic"]
        or document.question != G5_LEGACY_QUESTION
        or document.answer != G5_LEGACY_ANSWER
        or document.status != "published"
        or document.vectorization_status != "ready"
        or document.document_version != 1
        or document.statement_type != KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION
        or document.customer_scope != KnowledgeCustomerScope.GENERIC
        or document.publication_approval != KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW
        or document.approved_by != snapshot.approver.id
        or document.approved_at is None
        or document.deleted_at is not None
        or any(message.content != G5_LEGACY_QUESTION for message in snapshot.messages)
    ):
        raise ValueError("G5 replacement target mismatch")


async def replace_synthetic_content(
    session: AsyncSession, manifest: ReconciliationManifest, snapshot: ContentSnapshot
) -> None:
    """在一个事务内更新原 50 条问题与唯一 FAQ；版本门禁立即使旧向量失效。"""
    assert_replacement_target(manifest, snapshot)
    document = snapshot.document
    assert document is not None
    document.question = G5_SYNTHETIC_QUESTION
    document.answer = G5_SYNTHETIC_ANSWER_V2
    document.title = G5_SYNTHETIC_QUESTION[:500]
    document.content_hash = content_hash(G5_SYNTHETIC_QUESTION, G5_SYNTHETIC_ANSWER_V2)
    document.statement_type = KnowledgeStatementType.POLICY
    document.document_version = 2
    document.vectorization_status = "pending"
    document.approved_at = datetime.now(UTC)
    document.published_at = document.approved_at
    for message in snapshot.messages:
        message.content = G5_SYNTHETIC_QUESTION
    session.add(
        AuditLog(
            store_id=manifest.store_id,
            actor_type="system",
            actor_id=None,
            action="g5.fixture.content_replace",
            resource_type="knowledge_document",
            resource_id=document.id,
            request_id=str(manifest.run_id),
            after_data={"sessions": 50, "synthetic_faq": 1, "version": 2, "knowledge_ready": False},
            result="success",
        )
    )
    await session.flush()


def assert_third_faq_target(manifest: ReconciliationManifest, snapshot: ContentSnapshot) -> None:
    """只认领原隔离店铺已就绪的版本 2 FAQ；50 条提问不得变化。"""
    document = snapshot.document
    if (
        snapshot.state != "prepared"
        or len(snapshot.messages) != 50
        or document is None
        or document.store_id != manifest.store_id
        or document.source != FAQ_SOURCE
        or document.source_type != "faq"
        or document.tags != ["g5-synthetic"]
        or document.question != G5_SYNTHETIC_QUESTION
        or document.answer != G5_SYNTHETIC_ANSWER_V2
        or document.status != "published"
        or document.vectorization_status != "ready"
        or document.document_version != 2
        or document.statement_type != KnowledgeStatementType.POLICY
        or document.customer_scope != KnowledgeCustomerScope.GENERIC
        or document.publication_approval != KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW
        or document.approved_by != snapshot.approver.id
        or document.approved_at is None
        or document.deleted_at is not None
        or any(message.content != G5_SYNTHETIC_QUESTION for message in snapshot.messages)
    ):
        raise ValueError("G5 third FAQ target mismatch")


async def replace_third_faq_answer(
    session: AsyncSession, manifest: ReconciliationManifest, snapshot: ContentSnapshot
) -> None:
    """单事务替换唯一 FAQ 的答案，旧版本向量立即失效。"""
    assert_third_faq_target(manifest, snapshot)
    document = snapshot.document
    assert document is not None
    document.answer = G5_SYNTHETIC_ANSWER
    document.content_hash = content_hash(G5_SYNTHETIC_QUESTION, G5_SYNTHETIC_ANSWER)
    document.document_version = 3
    document.vectorization_status = "pending"
    document.approved_at = datetime.now(UTC)
    document.published_at = document.approved_at
    session.add(
        AuditLog(
            store_id=manifest.store_id,
            actor_type="system",
            actor_id=None,
            action="g5.fixture.faq_v3_replace",
            resource_type="knowledge_document",
            resource_id=document.id,
            request_id=str(manifest.run_id),
            after_data={"sessions": 50, "synthetic_faq": 1, "version": 3, "knowledge_ready": False},
            result="success",
        )
    )
    await session.flush()


class ScopedG5VectorPort(SqlAlchemyKnowledgeVectorPort):
    """复用现有向量替换逻辑，但认领只允许指定隔离店铺的一条 FAQ。"""

    def __init__(self, store_id: uuid.UUID, document_id: uuid.UUID, version: int) -> None:
        self.store_id = store_id
        self.document_id = document_id
        self.version = version

    async def claim_pending_documents(self, session: AsyncSession, limit: int) -> list[KnowledgeDocument]:
        if limit != 1:
            raise ValueError("G5 vector claim must be one")
        documents = list(
            (
                await session.scalars(
                    select(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.store_id == self.store_id,
                        KnowledgeDocument.id == self.document_id,
                        KnowledgeDocument.document_version == self.version,
                        KnowledgeDocument.status == "published",
                        KnowledgeDocument.vectorization_status == "pending",
                        KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
                        KnowledgeDocument.publication_approval
                        == KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                        KnowledgeDocument.deleted_at.is_(None),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if documents:
            documents[0].vectorization_status = "processing"
            await session.commit()
        return documents


def assert_vector_runtime(settings: Settings) -> None:
    """一次性嵌入只使用 staging 本地 BGE，不借用通用模型或平台写入能力。"""
    if (
        settings.app_env != "staging"
        or not settings.embedding_enabled
        or settings.embedding_provider != "local_bge"
        or settings.embedding_model != "BAAI/bge-m3"
        or settings.embedding_dimensions != 1024
        or settings.retrieval_model_service_url != "http://retrieval-model-service:8010"
        or settings.llm_enabled
        or settings.real_tiktok_message_write_enabled
    ):
        raise ValueError("G5 vector runtime mismatch")


def credential_name(generation: int) -> str:
    return f"{CREDENTIAL_PREFIX}{generation}.json"


def validate_credential_inventory(
    source: Path, output: Path, names: set[str], *, writable: bool, allow_renewed: bool
) -> int:
    """只接受原批次的连续编号；写入目标必须是下一个未占用的编号。"""
    suffix = output.name.removeprefix(CREDENTIAL_PREFIX).removesuffix(".json")
    if (
        source.name != SOURCE_NAME
        or source.parent != output.parent
        or not output.name.startswith(CREDENTIAL_PREFIX)
        or not output.name.endswith(".json")
        or not suffix.isascii()
        or not suffix.isdecimal()
    ):
        raise ValueError("G5 content batch mismatch")
    try:
        generation = int(suffix)
    except ValueError as exc:
        raise ValueError("G5 content batch mismatch") from exc
    if (
        generation < 3
        or suffix != str(generation)
        or len(names) < 2
        or names != {credential_name(index) for index in range(1, len(names) + 1)}
    ):
        raise ValueError("G5 content batch mismatch")
    expected = len(names) + 1 if writable else max(3, len(names)) if allow_renewed else 3
    if generation != expected or (not writable and not allow_renewed and len(names) != 2):
        raise ValueError("G5 content batch mismatch")
    return generation


def validate_content_paths(
    app_env: str, source: Path, output: Path, *, writable: bool, allow_renewed: bool = False
) -> int:
    """源码只读、私有目录按模式挂载，且绝不覆盖原始或更新后的凭证。"""
    if app_env != "staging":
        raise ValueError("G5 content preparation requires staging")
    if output.is_symlink() or (output.exists() and not allow_renewed):
        raise ValueError("G5 renewed credentials file already exists")
    generation = validate_credential_inventory(
        source, output, {path.name for path in source.parent.iterdir()}, writable=writable, allow_renewed=allow_renewed
    )
    if os.name != "posix" or not source.is_absolute() or not source.is_file() or source.is_symlink():
        raise ValueError("G5 content source requires private POSIX staging")
    if not private_source_metadata_is_safe(source.parent.stat(), source.stat()) or not current_container_paths_are_safe(
        output, writable=writable
    ):
        raise ValueError("G5 content private source is unsafe")
    if output.exists() and (
        not output.is_file() or not private_source_metadata_is_safe(output.parent.stat(), output.stat())
    ):
        raise ValueError("G5 renewed credentials file is unsafe")
    last_existing = generation if output.exists() else generation - 1
    for index in range(1, last_existing + 1):
        prior = source.parent / credential_name(index)
        if (
            prior.is_symlink()
            or not prior.is_file()
            or not private_source_metadata_is_safe(prior.parent.stat(), prior.stat())
        ):
            raise ValueError("G5 private credential history is unsafe")
    return generation


def assert_content_mode_inventory(
    mode: str, generation: int, output_exists: bool, document_version: int | None
) -> None:
    """写入模式将私有凭证批次与唯一 FAQ 版本精确绑定。"""
    if mode == "replace_content":
        allowed = generation == 4 and output_exists
    elif mode == "replace_answer_v3":
        allowed = generation == 5 and output_exists and document_version == 2
    elif mode == "vectorize_one":
        allowed = (
            (document_version == 1 and generation == 3 and not output_exists)
            or (document_version == 2 and generation == 4 and output_exists)
            or (document_version == 3 and generation == 5 and output_exists)
        )
    else:
        raise ValueError("G5 content mode is invalid")
    if not allowed:
        raise ValueError("G5 content batch does not match document version")


def validate_renewed_payload(payload: object, manifest: ReconciliationManifest) -> None:
    """只读验签续期文件的全部 50 个用户和会话映射，不输出令牌。"""
    if validate_reconciliation_payload(payload) != manifest:
        raise ValueError("fixture renewed batch mismatch")


def validate_credentials_history(source: Path, output: Path, manifest: ReconciliationManifest) -> None:
    """逐份验签原批次与所有续期批次；旧令牌过期不影响只读对账。"""
    generation = int(output.name.removeprefix(CREDENTIAL_PREFIX).removesuffix(".json"))
    last_existing = generation if output.exists() else generation - 1
    for index in range(1, last_existing + 1):
        prior = source.parent / credential_name(index)
        if prior == source:
            continue
        try:
            renewed_payload: Any = json.loads(prior.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("G5 renewed credentials unreadable") from exc
        validate_renewed_payload(renewed_payload, manifest)


def private_source_metadata_is_safe(parent: os.stat_result, source: os.stat_result) -> bool:
    """Rootless 映射可改变容器内 UID，目录和文件仍必须同属私有 Runner。"""
    return bool(
        stat.S_ISDIR(parent.st_mode)
        and stat.S_ISREG(source.st_mode)
        and parent.st_uid == source.st_uid
        and parent.st_mode & 0o077 == 0
        and source.st_mode & 0o077 == 0
        and 1 <= source.st_size <= 200_000
    )


def read_private_source(source: Path) -> tuple[dict[str, Any], ReconciliationManifest]:
    """过期令牌仍须验签和逐一匹配原 50 个会话；内容永不进入报告。"""
    try:
        payload: Any = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("G5 private source unreadable") from exc
    manifest = validate_reconciliation_payload(payload)
    settings = get_settings()
    expected_key_sha = os.environ.get("EXPECTED_RUNTIME_JWT_SHA256", "")
    if (
        len(expected_key_sha) != 64
        or not hmac.compare_digest(hashlib.sha256(settings.jwt_secret_key.encode()).hexdigest(), expected_key_sha)
        or settings.jwt_algorithm != os.environ.get("EXPECTED_RUNTIME_JWT_ALGORITHM", "")
    ):
        raise ValueError("G5 runtime signing configuration mismatch")
    return payload, manifest


async def inspect_content_fixture(
    session: AsyncSession, manifest: ReconciliationManifest, *, lock: bool = False
) -> ContentSnapshot:
    """只读核对原批次、权限、审计、全部消息和知识的唯一安全状态。"""
    store = await session.get(Store, manifest.store_id, with_for_update=lock)
    role = await session.get(Role, manifest.role_id)
    if role is None or role.code != f"g5-{manifest.run_id.hex}":
        raise ValueError("G5 fixture role mismatch")
    users = (await session.scalars(select(User).where(User.id.in_(manifest.user_ids)))).all()
    conversations = (
        await session.scalars(select(Conversation).where(Conversation.id.in_(manifest.conversation_ids)))
    ).all()
    message_query = select(Message).where(Message.store_id == manifest.store_id)
    messages = (await session.scalars(message_query.with_for_update() if lock else message_query)).all()
    state = verify_g5_content_snapshot(manifest, store, users, conversations, messages)
    permission_id = await session.scalar(select(Permission.id).where(Permission.code == "workspace.view"))
    role_permission_ids = (
        await session.scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == role.id))
    ).all()
    assignments = (await session.execute(select(user_roles).where(user_roles.c.user_id.in_(manifest.user_ids)))).all()
    if (
        permission_id is None
        or role_permission_ids != [permission_id]
        or len(assignments) != 50
        or {(row.user_id, row.role_id, row.store_id) for row in assignments}
        != {(user_id, manifest.role_id, manifest.store_id) for user_id in manifest.user_ids}
    ):
        raise ValueError("G5 fixture permissions mismatch")
    audits = (
        await session.scalars(
            select(AuditLog).where(
                AuditLog.store_id == manifest.store_id,
                AuditLog.action.in_(
                    [
                        "g5.fixture.provision",
                        "g5.fixture.reconcile_email",
                        "g5.fixture.content_prepare",
                        "g5.fixture.content_replace",
                        "g5.fixture.faq_v3_replace",
                    ]
                ),
            )
        )
    ).all()
    audit_actions = [row.action for row in audits]
    if state == "prepared" and audit_actions.count("g5.fixture.faq_v3_replace") == 1:
        state = "prepared_v3"
    if (
        audit_actions.count("g5.fixture.provision") != 1
        or audit_actions.count("g5.fixture.reconcile_email") != 1
        or audit_actions.count("g5.fixture.content_prepare") != (1 if state != "original" else 0)
        or audit_actions.count("g5.fixture.content_replace") != (1 if state in {"prepared", "prepared_v3"} else 0)
        or audit_actions.count("g5.fixture.faq_v3_replace") != (1 if state == "prepared_v3" else 0)
        or len(audits)
        != (5 if state == "prepared_v3" else 4 if state == "prepared" else 3 if state == "legacy_prepared" else 2)
    ):
        raise ValueError("G5 fixture audit mismatch")
    document_query = select(KnowledgeDocument).where(KnowledgeDocument.store_id == manifest.store_id)
    documents = (await session.scalars(document_query.with_for_update() if lock else document_query)).all()
    document = documents[0] if len(documents) == 1 else None
    if state == "original" and documents:
        raise ValueError("G5 fixture knowledge already exists")
    if state in {"legacy_prepared", "prepared", "prepared_v3"}:
        legacy = state == "legacy_prepared"
        third = state == "prepared_v3"
        if (
            document is None
            or document.deleted_at is not None
            or document.source != FAQ_SOURCE
            or document.source_type != "faq"
            or document.tags != ["g5-synthetic"]
            or document.question != (G5_LEGACY_QUESTION if legacy else G5_SYNTHETIC_QUESTION)
            or document.answer
            != (G5_LEGACY_ANSWER if legacy else G5_SYNTHETIC_ANSWER if third else G5_SYNTHETIC_ANSWER_V2)
            or document.content_hash != content_hash(document.question, document.answer)
            or document.status != "published"
            or document.statement_type
            != (KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION if legacy else KnowledgeStatementType.POLICY)
            or document.customer_scope != KnowledgeCustomerScope.GENERIC
            or document.publication_approval != KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW
            or document.approved_by != manifest.user_ids[0]
            or document.approved_at is None
            or document.document_version != (1 if legacy else 3 if third else 2)
            or document.vectorization_status not in {"pending", "processing", "ready"}
        ):
            raise ValueError("G5 fixture knowledge mismatch")
        all_chunks = (
            await session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.store_id == manifest.store_id))
        ).all()
        expected_version = (
            document.document_version
            if document.vectorization_status == "ready"
            else max(1, document.document_version - 1)
        )
        expected_count = 0 if legacy and document.vectorization_status != "ready" else 1
        if len(all_chunks) != expected_count or any(
            chunk.document_id != document.id or chunk.document_version != expected_version for chunk in all_chunks
        ):
            raise ValueError("G5 fixture chunks mismatch")
    users_by_id = {user.id: user for user in users}
    return ContentSnapshot(state, users_by_id[manifest.user_ids[0]], list(messages), document)


async def prepare_synthetic_content(
    session: AsyncSession, manifest: ReconciliationManifest, snapshot: ContentSnapshot
) -> None:
    """在单一事务内借用隔离知识权限、走现有知识服务并撤销临时授权。"""
    if snapshot.state != "original" or snapshot.document is not None:
        raise ValueError("G5 fixture content already changed")
    permission_id = await session.scalar(select(Permission.id).where(Permission.code == "knowledge.manage"))
    if permission_id is None:
        raise ValueError("G5 fixture knowledge permission missing")
    temporary_role_id = uuid.uuid4()
    await session.execute(
        insert(Role).values(
            id=temporary_role_id,
            code=f"g5-{manifest.run_id.hex}-approver",
            name="G5 synthetic knowledge approver",
        )
    )
    await session.execute(role_permissions.insert().values(role_id=temporary_role_id, permission_id=permission_id))
    await session.execute(
        user_roles.insert().values(user_id=manifest.user_ids[0], role_id=temporary_role_id, store_id=manifest.store_id)
    )
    document = await create_entry(
        session,
        snapshot.approver,
        KnowledgeEntryCreate(
            store_id=manifest.store_id,
            question=G5_LEGACY_QUESTION,
            answer=G5_LEGACY_ANSWER,
            source=FAQ_SOURCE,
            tags=["g5-synthetic"],
            statement_type=KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            customer_scope=KnowledgeCustomerScope.GENERIC,
        ),
        commit=False,
    )
    await set_entry_status(session, snapshot.approver, document.id, "published", commit=False)
    for message in snapshot.messages:
        if message.content != G5_ORIGINAL_QUESTION:
            raise ValueError("G5 fixture message changed during preparation")
        message.content = G5_LEGACY_QUESTION
    session.add(
        AuditLog(
            store_id=manifest.store_id,
            actor_type="system",
            actor_id=None,
            action="g5.fixture.content_prepare",
            resource_type="store",
            resource_id=manifest.store_id,
            request_id=str(manifest.run_id),
            after_data={"sessions": 50, "synthetic_faq": 1, "approval": "internal_review"},
            result="success",
        )
    )
    await session.flush()
    await session.execute(
        user_roles.delete().where(
            user_roles.c.user_id == manifest.user_ids[0], user_roles.c.role_id == temporary_role_id
        )
    )
    await session.execute(role_permissions.delete().where(role_permissions.c.role_id == temporary_role_id))
    await session.execute(delete(Role).where(Role.id == temporary_role_id))


async def run_content_mode(mode: str, source: Path, output: Path, expected_database_sha256: str) -> dict[str, Any]:
    """读检查、一次性内容写入与零数据库写入续期分开执行。"""
    writable = mode == "renew_credentials"
    settings = get_settings()
    generation = validate_content_paths(
        settings.app_env,
        source,
        output,
        writable=writable,
        allow_renewed=mode in {"check_only", "replace_content", "replace_answer_v3", "vectorize_one"},
    )
    if mode == "replace_content":
        assert_content_mode_inventory(mode, generation, output.exists(), None)
    if mode == "replace_answer_v3":
        assert_content_mode_inventory(mode, generation, output.exists(), 2)
    validate_database_target(settings.database_url, expected_database_sha256)
    payload, manifest = read_private_source(source)
    if mode == "vectorize_one":
        assert_vector_runtime(settings)
    validate_credentials_history(source, output, manifest)
    async with session_factory() as session:
        if mode == "vectorize_one":
            snapshot = await inspect_content_fixture(session, manifest)
            document_id, store_id, version = assert_single_vector_target(manifest, snapshot)
            assert_content_mode_inventory(mode, generation, output.exists(), version)
            existing_chunks = (
                await session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.store_id == store_id))
            ).all()
            if (version == 1 and existing_chunks) or (
                version in {2, 3}
                and (
                    len(existing_chunks) != 1
                    or existing_chunks[0].document_id != document_id
                    or existing_chunks[0].document_version != version - 1
                )
            ):
                raise ValueError("G5 vector target has unexpected chunks")
            service = KnowledgeVectorizationService(
                vector_port=ScopedG5VectorPort(store_id, document_id, version),
                embedding_service=build_embedding_service(settings),
                chunker=FaqTokenChunker(model_name=settings.embedding_model, max_tokens=800, overlap_tokens=80),
                claim_limit=1,
            )
            result = await service.process_cycle(session)
            if (result.claimed, result.succeeded, result.failed, result.stale) != (1, 1, 0, 0):
                raise ValueError("G5 vector outcome requires read-only reconciliation")
            verified = await inspect_content_fixture(session, manifest)
            if verified.document is None or verified.document.vectorization_status != "ready":
                raise ValueError("G5 vector outcome is not ready")
            return {
                "mode": mode,
                "matched_sessions": 50,
                "synthetic_faq": 1,
                "local_embedding_documents": 1,
                "deepseek_calls": 0,
                "knowledge_ready": True,
            }
        if mode == "prepare_content":
            async with session.begin():
                snapshot = await inspect_content_fixture(session, manifest)
                await prepare_synthetic_content(session, manifest, snapshot)
            return {"mode": mode, "updated_sessions": 50, "synthetic_faq": 1, "provider_calls": 0}
        if mode == "replace_content":
            async with session.begin():
                snapshot = await inspect_content_fixture(session, manifest, lock=True)
                await replace_synthetic_content(session, manifest, snapshot)
            return {
                "mode": mode,
                "updated_sessions": 50,
                "synthetic_faq": 1,
                "document_version": 2,
                "knowledge_ready": False,
                "provider_calls": 0,
            }
        if mode == "replace_answer_v3":
            async with session.begin():
                snapshot = await inspect_content_fixture(session, manifest, lock=True)
                assert_content_mode_inventory(
                    mode, generation, output.exists(), snapshot.document.document_version if snapshot.document else None
                )
                await replace_third_faq_answer(session, manifest, snapshot)
            return {
                "mode": mode,
                "matched_sessions": 50,
                "synthetic_faq": 1,
                "document_version": 3,
                "knowledge_ready": False,
                "provider_calls": 0,
            }
        snapshot = await inspect_content_fixture(session, manifest)
        knowledge_ready = (
            snapshot.state in {"legacy_prepared", "prepared", "prepared_v3"}
            and snapshot.document is not None
            and snapshot.document.vectorization_status == "ready"
        )
        if mode == "renew_credentials":
            if not knowledge_ready:
                raise ValueError("G5 synthetic knowledge is not ready")
            write_secure_pool(output, build_renewed_credentials(payload, manifest))
            return {"mode": mode, "rotated_tokens": 50, "provider_calls": 0, "database_writes": 0}
        return {
            "mode": mode,
            "fixture_state": snapshot.state,
            "knowledge_ready": knowledge_ready,
            "credentials_state": "renewed" if output.exists() else "original",
            "matched_sessions": 50,
            "provider_calls": 0,
            "database_writes": 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact G5 synthetic content and token renewal")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--prepare-content", action="store_true")
    mode.add_argument("--replace-content", action="store_true")
    mode.add_argument("--replace-answer-v3", action="store_true")
    mode.add_argument("--renew-credentials", action="store_true")
    mode.add_argument("--vectorize-one", action="store_true")
    parser.add_argument("--source-credentials-file", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--expected-database-sha256", required=True)
    args = parser.parse_args()
    if args.vectorize_one:
        selected = "vectorize_one"
    elif args.replace_answer_v3:
        selected = "replace_answer_v3"
    elif args.replace_content:
        selected = "replace_content"
    elif args.prepare_content:
        selected = "prepare_content"
    elif args.renew_credentials:
        selected = "renew_credentials"
    else:
        selected = "check_only"
    try:
        result = asyncio.run(
            run_content_mode(
                selected, args.source_credentials_file, args.credentials_file, args.expected_database_sha256
            )
        )
    except (ValueError, FileExistsError, OSError) as exc:
        raise SystemExit(type(exc).__name__) from None
    except Exception:
        raise SystemExit("g5_content_outcome_unknown; run read-only reconciliation") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
