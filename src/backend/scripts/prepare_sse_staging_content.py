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
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgeEntryCreate,
    KnowledgePublicationApproval,
    KnowledgeStatementType,
)
from app.knowledge_base.service import create_entry, set_entry_status
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.database.session import session_factory
from app.stores.models import Store
from scripts.prepare_sse_staging_fixture import (
    G5_ORIGINAL_QUESTION,
    G5_SYNTHETIC_ANSWER,
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
RENEWED_NAME = "g5-38852775454-3.json"
FAQ_SOURCE = "g5-synthetic-only"


@dataclass(frozen=True)
class ContentSnapshot:
    state: str
    approver: User
    messages: list[Message]
    document: KnowledgeDocument | None


def validate_content_paths(app_env: str, source: Path, output: Path, *, writable: bool) -> None:
    """源码只读、私有目录按模式挂载，且绝不覆盖原始或更新后的凭证。"""
    if app_env != "staging":
        raise ValueError("G5 content preparation requires staging")
    if source.name != SOURCE_NAME or output.name != RENEWED_NAME or source.parent != output.parent:
        raise ValueError("G5 content batch mismatch")
    if output.exists():
        raise ValueError("G5 renewed credentials file already exists")
    if os.name != "posix" or not source.is_absolute() or not source.is_file() or source.is_symlink():
        raise ValueError("G5 content source requires private POSIX staging")
    if not private_source_metadata_is_safe(source.parent.stat(), source.stat()) or not current_container_paths_are_safe(
        output, writable=writable
    ):
        raise ValueError("G5 content private source is unsafe")


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


async def inspect_content_fixture(session: AsyncSession, manifest: ReconciliationManifest) -> ContentSnapshot:
    """只读核对原批次、权限、审计、全部消息和知识的唯一安全状态。"""
    store = await session.get(Store, manifest.store_id)
    role = await session.get(Role, manifest.role_id)
    if role is None or role.code != f"g5-{manifest.run_id.hex}":
        raise ValueError("G5 fixture role mismatch")
    users = (await session.scalars(select(User).where(User.id.in_(manifest.user_ids)))).all()
    conversations = (
        await session.scalars(select(Conversation).where(Conversation.id.in_(manifest.conversation_ids)))
    ).all()
    messages = (await session.scalars(select(Message).where(Message.store_id == manifest.store_id))).all()
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
                    ["g5.fixture.provision", "g5.fixture.reconcile_email", "g5.fixture.content_prepare"]
                ),
            )
        )
    ).all()
    audit_actions = [row.action for row in audits]
    if (
        audit_actions.count("g5.fixture.provision") != 1
        or audit_actions.count("g5.fixture.reconcile_email") != 1
        or audit_actions.count("g5.fixture.content_prepare") != (1 if state == "prepared" else 0)
        or len(audits) != (3 if state == "prepared" else 2)
    ):
        raise ValueError("G5 fixture audit mismatch")
    documents = (
        await session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.store_id == manifest.store_id))
    ).all()
    document = documents[0] if len(documents) == 1 else None
    if state == "original" and documents:
        raise ValueError("G5 fixture knowledge already exists")
    if state == "prepared":
        if (
            document is None
            or document.deleted_at is not None
            or document.source != FAQ_SOURCE
            or document.question != G5_SYNTHETIC_QUESTION
            or document.answer != G5_SYNTHETIC_ANSWER
            or document.status != "published"
            or document.statement_type != KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION
            or document.customer_scope != KnowledgeCustomerScope.GENERIC
            or document.publication_approval != KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW
            or document.approved_by != manifest.user_ids[0]
            or document.approved_at is None
            or document.document_version != 1
            or document.vectorization_status not in {"pending", "processing", "ready"}
        ):
            raise ValueError("G5 fixture knowledge mismatch")
        if document.vectorization_status == "ready":
            chunk_count = len(
                (
                    await session.scalars(
                        select(KnowledgeChunk.id).where(
                            KnowledgeChunk.store_id == manifest.store_id,
                            KnowledgeChunk.document_id == document.id,
                            KnowledgeChunk.document_version == document.document_version,
                        )
                    )
                ).all()
            )
            if chunk_count < 1:
                raise ValueError("G5 fixture ready knowledge has no chunks")
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
            question=G5_SYNTHETIC_QUESTION,
            answer=G5_SYNTHETIC_ANSWER,
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
        message.content = G5_SYNTHETIC_QUESTION
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
    validate_content_paths(settings.app_env, source, output, writable=writable)
    validate_database_target(settings.database_url, expected_database_sha256)
    payload, manifest = read_private_source(source)
    async with session_factory() as session:
        if mode == "prepare_content":
            async with session.begin():
                snapshot = await inspect_content_fixture(session, manifest)
                await prepare_synthetic_content(session, manifest, snapshot)
            return {"mode": mode, "updated_sessions": 50, "synthetic_faq": 1, "provider_calls": 0}
        snapshot = await inspect_content_fixture(session, manifest)
        knowledge_ready = (
            snapshot.state == "prepared"
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
            "matched_sessions": 50,
            "provider_calls": 0,
            "database_writes": 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact G5 synthetic content and token renewal")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--prepare-content", action="store_true")
    mode.add_argument("--renew-credentials", action="store_true")
    parser.add_argument("--source-credentials-file", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--expected-database-sha256", required=True)
    args = parser.parse_args()
    if args.prepare_content:
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
