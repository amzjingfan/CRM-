"""为 G5 准备隔离的 staging 合成身份；只在显式执行时写入。"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_management.models import AgentConfig
from app.audit.models import AuditLog
from app.auth.security import create_access_token, hash_password
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, Role, User, user_roles
from app.shared.database.session import session_factory
from app.stores.models import Store
from scripts.load_test_sse import prepare_paths_are_safe


class FixtureCommitUnknownError(RuntimeError):
    """凭证文件已写入，数据库提交结果须按 manifest 人工核对。"""


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


def container_paths_are_safe(output: Path, source_file: Path, mountinfo: str) -> bool:
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
    return "ro" in mounts.get(source_root.as_posix(), set()) and "rw" in mounts.get(credential_root.as_posix(), set())


def current_container_paths_are_safe(output: Path) -> bool:
    try:
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    except OSError:
        return False
    return container_paths_are_safe(output, Path(__file__).resolve(), mountinfo)


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
            email=f"g5-{run_id.hex}-{index:02d}@example.invalid",
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
    parser.add_argument("--execute", action="store_true", help="explicitly create staging fixture")
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--expected-database-sha256", required=True)
    args = parser.parse_args()
    if not args.execute:
        parser.error("--execute is required")
    try:
        result = asyncio.run(execute_fixture(args.credentials_file, args.expected_database_sha256))
    except FixtureCommitUnknownError:
        raise SystemExit("fixture_commit_unknown; retain the private manifest and reconcile the store") from None
    except (ValueError, FileExistsError, OSError) as exc:
        raise SystemExit(type(exc).__name__) from None
    except Exception:
        raise SystemExit("fixture_failed") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
