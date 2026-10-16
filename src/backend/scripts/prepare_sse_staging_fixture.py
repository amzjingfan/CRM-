"""为 G5 准备隔离的 staging 合成身份；只在显式执行时写入。"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_management.models import AgentConfig
from app.audit.models import AuditLog
from app.auth.security import create_access_token, hash_password
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.database.session import session_factory
from app.stores.models import Store
from scripts.load_test_sse import prepare_paths_are_safe


class FixtureCommitUnknownError(RuntimeError):
    """凭证文件已写入，数据库提交结果须按 manifest 人工核对。"""


@dataclass(frozen=True)
class ReconciliationManifest:
    run_id: uuid.UUID
    store_id: uuid.UUID
    role_id: uuid.UUID
    user_ids: tuple[uuid.UUID, ...]
    conversation_ids: tuple[uuid.UUID, ...]


def validate_reconciliation_payload(payload: object) -> ReconciliationManifest:
    """核对旧凭证与原批次的 50 个用户、会话映射；过期 Token 仍验签。"""
    try:
        if not isinstance(payload, dict) or set(payload) != {"manifest", "clients"}:
            raise ValueError
        raw_manifest, clients = payload["manifest"], payload["clients"]
        if (
            not isinstance(raw_manifest, dict)
            or set(raw_manifest) != {"run_id", "store_id", "role_id", "user_ids", "conversation_ids"}
            or not isinstance(clients, list)
            or len(clients) != 50
        ):
            raise ValueError
        raw_users, raw_sessions = raw_manifest["user_ids"], raw_manifest["conversation_ids"]
        if not isinstance(raw_users, list) or not isinstance(raw_sessions, list):
            raise ValueError
        if len(raw_users) != 50 or len(raw_sessions) != 50:
            raise ValueError
        manifest = ReconciliationManifest(
            run_id=uuid.UUID(raw_manifest["run_id"]),
            store_id=uuid.UUID(raw_manifest["store_id"]),
            role_id=uuid.UUID(raw_manifest["role_id"]),
            user_ids=tuple(uuid.UUID(value) for value in raw_users),
            conversation_ids=tuple(uuid.UUID(value) for value in raw_sessions),
        )
        if len(set(manifest.user_ids)) != 50 or len(set(manifest.conversation_ids)) != 50:
            raise ValueError
        settings = get_settings()
        for index, client in enumerate(clients):
            if not isinstance(client, dict) or set(client) != {"access_token", "csrf_token", "session_id"}:
                raise ValueError
            if not isinstance(client["csrf_token"], str) or not client["csrf_token"]:
                raise ValueError
            if uuid.UUID(client["session_id"]) != manifest.conversation_ids[index]:
                raise ValueError
            claims = jwt.decode(
                client["access_token"],
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False},
            )
            if claims.get("type") != "access" or claims.get("sub") != str(manifest.user_ids[index]):
                raise ValueError
    except (KeyError, TypeError, ValueError, jwt.InvalidTokenError) as exc:
        raise ValueError("fixture manifest or token mapping invalid") from exc
    return manifest


async def inspect_existing_reconciliation(
    session: AsyncSession, manifest: ReconciliationManifest, *, lock_users: bool = False
) -> list[User]:
    """旧批次、隔离权限、用户和会话必须逐一匹配，才允许触碰邮箱。"""
    run_code = f"g5-{manifest.run_id.hex}"
    store = await session.get(Store, manifest.store_id)
    role = await session.get(Role, manifest.role_id)
    if (
        store is None
        or store.code != run_code
        or store.status != "active"
        or store.deleted_at is not None
        or store.metadata_json != {"purpose": "g5-staging", "run_id": str(manifest.run_id)}
        or role is None
        or role.code != run_code
    ):
        raise ValueError("fixture batch mismatch")

    audit_rows = (
        await session.scalars(
            select(AuditLog).where(
                AuditLog.store_id == manifest.store_id,
                AuditLog.action.in_(["g5.fixture.provision", "g5.fixture.reconcile_email"]),
            )
        )
    ).all()
    if (
        len(audit_rows) != 1
        or audit_rows[0].action != "g5.fixture.provision"
        or (
            audit_rows[0].request_id != str(manifest.run_id)
            or audit_rows[0].resource_id != manifest.store_id
            or audit_rows[0].result != "success"
            or audit_rows[0].after_data != {"users": 50, "sessions": 50, "permission": "workspace.view"}
        )
    ):
        raise ValueError("fixture audit mismatch")

    workspace_permission = await session.scalar(select(Permission.id).where(Permission.code == "workspace.view"))
    permission_ids = (
        await session.scalars(
            select(role_permissions.c.permission_id).where(role_permissions.c.role_id == manifest.role_id)
        )
    ).all()
    if workspace_permission is None or permission_ids != [workspace_permission]:
        raise ValueError("fixture permission mismatch")

    assignments = (await session.execute(select(user_roles).where(user_roles.c.user_id.in_(manifest.user_ids)))).all()
    if len(assignments) != 50 or {(row.user_id, row.role_id, row.store_id) for row in assignments} != {
        (user_id, manifest.role_id, manifest.store_id) for user_id in manifest.user_ids
    }:
        raise ValueError("fixture role mapping mismatch")

    statement = select(User).where(User.id.in_(manifest.user_ids))
    if lock_users:
        statement = statement.with_for_update()
    users = (await session.scalars(statement)).all()
    users_by_id = {user.id: user for user in users}
    if len(users_by_id) != 50:
        raise ValueError("fixture user count mismatch")
    for index, user_id in enumerate(manifest.user_ids):
        user = users_by_id[user_id]
        if user.email != f"{run_code}-{index:02d}@example.invalid" or user.status != "active":
            raise ValueError("fixture user mismatch")

    conversations = (
        await session.scalars(select(Conversation).where(Conversation.id.in_(manifest.conversation_ids)))
    ).all()
    sessions_by_id = {conversation.id: conversation for conversation in conversations}
    if len(sessions_by_id) != 50:
        raise ValueError("fixture session count mismatch")
    for index, conversation_id in enumerate(manifest.conversation_ids):
        conversation = sessions_by_id[conversation_id]
        if (
            conversation.store_id != manifest.store_id
            or conversation.platform != "synthetic"
            or conversation.status != "active"
            or conversation.external_conversation_id != f"{run_code}-{index:02d}"
        ):
            raise ValueError("fixture session mismatch")

    repaired_emails = [f"{run_code}-{index:02d}@example.com" for index in range(50)]
    existing_email = await session.scalar(select(User.id).where(User.email.in_(repaired_emails)).limit(1))
    if existing_email is not None:
        raise ValueError("fixture target email conflict")
    return [users_by_id[user_id] for user_id in manifest.user_ids]


async def reconcile_fixture_emails(
    session: AsyncSession, manifest: ReconciliationManifest, users: list[User]
) -> dict[str, Any]:
    """只修复已核对的 50 个邮箱并签发新的隔离凭证。"""
    if len(users) != 50 or tuple(user.id for user in users) != manifest.user_ids:
        raise ValueError("fixture user order mismatch")
    run_code = f"g5-{manifest.run_id.hex}"
    for index, user in enumerate(users):
        user.email = f"{run_code}-{index:02d}@example.com"
    session.add(
        AuditLog(
            store_id=manifest.store_id,
            actor_type="system",
            actor_id=None,
            action="g5.fixture.reconcile_email",
            resource_type="store",
            resource_id=manifest.store_id,
            request_id=str(manifest.run_id),
            before_data={"users": 50, "email_domain": "example.invalid"},
            after_data={"users": 50, "email_domain": "example.com", "tokens_rotated": 50},
            result="success",
        )
    )
    await session.flush()
    return {
        "manifest": {
            "run_id": str(manifest.run_id),
            "store_id": str(manifest.store_id),
            "role_id": str(manifest.role_id),
            "user_ids": [str(value) for value in manifest.user_ids],
            "conversation_ids": [str(value) for value in manifest.conversation_ids],
        },
        "clients": [
            {
                "access_token": create_access_token(user_id),
                "csrf_token": secrets.token_urlsafe(32),
                "session_id": str(conversation_id),
            }
            for user_id, conversation_id in zip(manifest.user_ids, manifest.conversation_ids, strict=True)
        ],
    }


def read_reconciliation_source(source: Path, output: Path) -> ReconciliationManifest:
    """只接受原创建作业的私有文件，并保留其内容供事后对账。"""
    if os.name != "posix":
        raise ValueError("fixture source requires POSIX staging")
    if (
        source.name != "g5-38852775454-1.json"
        or output.name != "g5-38852775454-2.json"
        or source.parent != output.parent
        or source.is_symlink()
        or not source.is_file()
    ):
        raise ValueError("fixture source path invalid")
    file_stat = source.stat()
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != output.parent.stat().st_uid
        or file_stat.st_mode & 0o077
        or not 1 <= file_stat.st_size <= 200_000
    ):
        raise ValueError("fixture source permissions invalid")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("fixture source unreadable") from exc
    return validate_reconciliation_payload(payload)


async def execute_reconciliation(
    source: Path, output: Path, expected_database_sha256: str, *, execute: bool
) -> dict[str, int | str | bool]:
    """先全量核对；仅显式执行时更新原用户并独占创建第二份私有凭证。"""
    settings = get_settings()
    validate_reconciliation_target(settings.app_env, output, writable=execute)
    validate_database_target(settings.database_url, expected_database_sha256)
    runtime_key_sha = os.environ.get("EXPECTED_RUNTIME_JWT_SHA256", "")
    runtime_algorithm = os.environ.get("EXPECTED_RUNTIME_JWT_ALGORITHM", "")
    if (
        len(runtime_key_sha) != 64
        or not hmac.compare_digest(hashlib.sha256(settings.jwt_secret_key.encode()).hexdigest(), runtime_key_sha)
        or runtime_algorithm != settings.jwt_algorithm
    ):
        raise ValueError("fixture runtime signing configuration mismatch")
    manifest = read_reconciliation_source(source, output)
    file_created = False
    try:
        async with session_factory() as session:
            async with session.begin():
                users = await inspect_existing_reconciliation(session, manifest, lock_users=execute)
                if execute:
                    payload = await reconcile_fixture_emails(session, manifest, users)
                    write_secure_pool(output, payload)
                    file_created = True
    except Exception as exc:
        if file_created:
            raise FixtureCommitUnknownError("fixture_commit_unknown") from exc
        raise
    if not execute:
        return {"mode": "reconcile_check", "ready": True, "matched_users": 50, "provider_calls": 0}
    return {"mode": "reconcile_email", "updated_users": 50, "rotated_tokens": 50, "provider_calls": 0}


def validate_target(app_env: str, output: Path) -> None:
    """拒绝非 staging、仓库内、已有文件及共享目录。"""
    if app_env != "staging":
        raise ValueError("fixture provisioning requires staging")
    if (
        not output.is_absolute()
        or not output.parent.is_dir()
        or output.exists()
        or not (prepare_paths_are_safe(output, output) or current_container_paths_are_safe(output))
    ):
        raise ValueError("fixture output must be a new file outside the repository")
    if sys.platform == "win32" or os.name != "posix":
        raise ValueError("fixture provisioning requires a POSIX staging runner")
    parent = output.parent.stat()
    if parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
        raise ValueError("fixture output parent must be owned by the runner and private")


def validate_reconciliation_target(app_env: str, output: Path, *, writable: bool) -> None:
    """检查和修复分别接受私有只读、可写挂载，均拒绝仓库与现有输出。"""
    if (
        app_env != "staging"
        or sys.platform == "win32"
        or os.name != "posix"
        or not output.is_absolute()
        or output.exists()
        or not output.parent.is_dir()
        or not current_container_paths_are_safe(output, writable=writable)
    ):
        raise ValueError("fixture reconciliation target invalid")
    parent = output.parent.stat()
    if parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
        raise ValueError("fixture reconciliation parent unsafe")


def container_paths_are_safe(output: Path, source_file: Path, mountinfo: str, *, writable: bool = True) -> bool:
    """镜像不含 Git；仅接受独立只读源码挂载与私有可写凭证挂载。"""
    source_root = Path("/opt/crm-g5-source")
    credential_root = Path("/opt/crm-g5-credentials")
    if output.parent != credential_root or not source_file.is_relative_to(source_root):
        return False
    mounts: dict[str, set[str]] = {}
    for line in mountinfo.splitlines():
        fields = line.split(" - ", 1)[0].split()
        if len(fields) >= 6 and fields[4] in (source_root.as_posix(), credential_root.as_posix()):
            mounts[fields[4]] = set(fields[5].split(","))
    required_mode = "rw" if writable else "ro"
    return "ro" in mounts.get(source_root.as_posix(), set()) and required_mode in mounts.get(
        credential_root.as_posix(), set()
    )


def current_container_paths_are_safe(output: Path, *, writable: bool = True) -> bool:
    try:
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    except OSError:
        return False
    return container_paths_are_safe(output, Path(__file__).resolve(), mountinfo, writable=writable)


def validate_database_target(database_url: str, expected_sha256: str) -> None:
    """要求与独立核对的 staging DSN 指纹完全一致，不输出连接串。"""
    actual = hashlib.sha256(database_url.encode("utf-8")).hexdigest()
    if len(expected_sha256) != 64 or not hmac.compare_digest(actual, expected_sha256.lower()):
        raise ValueError("staging database fingerprint mismatch")


async def provision_fixture(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any]:
    """在调用方事务中准备 50 个只拥有工作台查看权的合成身份。"""
    view_permission = await session.scalar(select(Permission).where(Permission.code == "workspace.view"))
    if view_permission is None:
        raise ValueError("workspace.view permission missing")

    run_code = f"g5-{run_id.hex}"
    store = Store(
        id=uuid.uuid4(),
        name="G5 staging synthetic fixture",
        code=run_code,
        status="active",
        metadata_json={"purpose": "g5-staging", "run_id": str(run_id)},
    )
    role = Role(id=uuid.uuid4(), code=run_code, name="G5 synthetic viewer", permissions=[view_permission])
    config = AgentConfig(
        id=uuid.uuid4(),
        store_id=store.id,
        name="G5 synthetic assistant",
        code="g5-synthetic",
        status="enabled",
        enabled_tools=[],
    )
    users: list[User] = []
    customers: list[Customer] = []
    conversations: list[Conversation] = []
    messages: list[Message] = []
    role_assignments: list[dict[str, uuid.UUID]] = []
    clients: list[dict[str, str]] = []
    user_ids: list[str] = []
    conversation_ids: list[str] = []
    for index in range(50):
        user_id, customer_id, conversation_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        user = User(
            id=user_id,
            email=f"g5-{run_id.hex}-{index:02d}@example.com",
            name=f"G5 synthetic {index:02d}",
            status="active",
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        customer = Customer(
            id=customer_id,
            store_id=store.id,
            platform="synthetic",
            external_customer_id=f"{run_code}-{index:02d}",
            name="Synthetic customer",
        )
        conversation = Conversation(
            id=conversation_id,
            store_id=store.id,
            customer_id=customer_id,
            platform="synthetic",
            external_conversation_id=f"{run_code}-{index:02d}",
            status="active",
        )
        message = Message(
            id=uuid.uuid4(),
            store_id=store.id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            platform="synthetic",
            external_message_id=f"{run_code}-{index:02d}",
            role="user",
            direction="inbound",
            message_type="text",
            content="What is the status of my test order?",
            status="received",
        )
        users.append(user)
        customers.append(customer)
        conversations.append(conversation)
        messages.append(message)
        role_assignments.append({"user_id": user_id, "role_id": role.id, "store_id": store.id})
        clients.append(
            {
                "access_token": create_access_token(user_id),
                "csrf_token": secrets.token_urlsafe(32),
                "session_id": str(conversation_id),
            }
        )
        user_ids.append(str(user_id))
        conversation_ids.append(str(conversation_id))

    # 仅传入外键 UUID 时 ORM 不推断跨表插入顺序；逐层 flush 防止真实 PG 外键失败。
    session.add_all([store, role])
    await session.flush()
    session.add_all([config, *users])
    await session.flush()
    session.add_all(customers)
    await session.flush()
    session.add_all(conversations)
    await session.flush()
    session.add_all(messages)
    await session.flush()
    await session.execute(user_roles.insert(), role_assignments)
    session.add(
        AuditLog(
            store_id=store.id,
            actor_type="system",
            actor_id=None,
            action="g5.fixture.provision",
            resource_type="store",
            resource_id=store.id,
            request_id=str(run_id),
            after_data={"users": 50, "sessions": 50, "permission": "workspace.view"},
            result="success",
        )
    )
    await session.flush()
    return {
        "clients": clients,
        "manifest": {
            "run_id": str(run_id),
            "store_id": str(store.id),
            "role_id": str(role.id),
            "user_ids": user_ids,
            "conversation_ids": conversation_ids,
        },
    }


def write_secure_pool(output: Path, payload: dict[str, Any]) -> None:
    """仅新建凭证文件，禁止覆盖或向 stdout 打印敏感字段。"""
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    except BaseException:
        output.unlink(missing_ok=True)
        raise


async def execute_fixture(output: Path, expected_database_sha256: str) -> dict[str, int | str]:
    """仅在锁定数据库目标后建立；提交不确定时保留唯一恢复 manifest。"""
    settings = get_settings()
    validate_target(settings.app_env, output)
    validate_database_target(settings.database_url, expected_database_sha256)
    run_id = uuid.uuid4()
    file_created = False
    try:
        async with session_factory() as session:
            async with session.begin():
                payload = await provision_fixture(session, run_id)
                write_secure_pool(output, payload)
                file_created = True
    except Exception as exc:
        if file_created:
            raise FixtureCommitUnknownError("fixture_commit_unknown") from exc
        raise
    return {"mode": "provision", "created_users": 50, "created_sessions": 50, "provider_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description="G5 staging-only synthetic account fixture")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true", help="explicitly create staging fixture")
    mode.add_argument("--reconcile-check", action="store_true", help="inspect one existing fixture without writes")
    mode.add_argument("--reconcile-email", action="store_true", help="repair one exact existing fixture")
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--source-credentials-file", type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    args = parser.parse_args()
    if args.execute and args.source_credentials_file is not None:
        parser.error("--source-credentials-file is only valid for reconciliation")
    if not args.execute and args.source_credentials_file is None:
        parser.error("--source-credentials-file is required for reconciliation")
    try:
        if args.execute:
            result = asyncio.run(execute_fixture(args.credentials_file, args.expected_database_sha256))
        else:
            result = asyncio.run(
                execute_reconciliation(
                    args.source_credentials_file,
                    args.credentials_file,
                    args.expected_database_sha256,
                    execute=args.reconcile_email,
                )
            )
    except FixtureCommitUnknownError:
        raise SystemExit("fixture_commit_unknown; retain the private manifest and reconcile the store") from None
    except (ValueError, FileExistsError, OSError) as exc:
        raise SystemExit(type(exc).__name__) from None
    except Exception:
        raise SystemExit("fixture_failed") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
