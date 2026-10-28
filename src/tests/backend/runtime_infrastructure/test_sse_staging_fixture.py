"""G5 staging 合成账号准备工具的失败关闭测试。"""

import hashlib
import importlib
import json
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.agents.management.config_models import AgentConfig
from app.audit.models import AuditLog
from app.auth.service import build_user_view
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.database.base import Permission, Role, User
from app.stores.models import Store


def fixture_tool():  # type: ignore[no-untyped-def]
    return importlib.import_module("scripts.prepare_sse_staging_fixture")


def test_fixture_tool_refuses_non_staging_environment(tmp_path: Path) -> None:
    tool = fixture_tool()

    with pytest.raises(ValueError, match="staging"):
        tool.validate_target("production", tmp_path / "clients.json")


def test_fixture_tool_refuses_repository_and_existing_output(tmp_path: Path) -> None:
    tool = fixture_tool()
    with pytest.raises(ValueError, match="outside the repository"):
        tool.validate_target("staging", Path(__file__))
    existing = tmp_path / "clients.json"
    existing.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="new file"):
        tool.validate_target("staging", existing)
    assert existing.read_text(encoding="utf-8") == "keep"


def test_fixture_requires_private_posix_runner_and_independent_database_digest(tmp_path: Path) -> None:
    tool = fixture_tool()
    output = tmp_path / "new-clients.json"
    if os.name != "posix":
        with pytest.raises(ValueError, match="POSIX"):
            tool.validate_target("staging", output)
    else:
        tool.validate_target("staging", output)
    database_url = "postgresql+asyncpg://synthetic@staging-db/crm"
    expected = hashlib.sha256(database_url.encode("utf-8")).hexdigest()
    tool.validate_database_target(database_url, expected)
    with pytest.raises(ValueError, match="database fingerprint"):
        tool.validate_database_target("postgresql+asyncpg://synthetic@other-db/crm", expected)
    with pytest.raises(ValueError, match="database fingerprint"):
        tool.validate_database_target(database_url, "")


def test_container_fixture_path_requires_separate_readonly_source_and_private_mount() -> None:
    tool = fixture_tool()
    output = Path("/opt/crm-g5-credentials/g5-test.json")
    source = Path("/opt/crm-g5-source/scripts/prepare_sse_staging_fixture.py")
    mountinfo = (
        "1 0 0:1 / /opt/crm-g5-source ro - ext4 /dev/test ro\n"
        "2 0 0:1 / /opt/crm-g5-credentials rw - ext4 /dev/test rw\n"
    )
    assert tool.container_paths_are_safe(output, source, mountinfo)
    assert not tool.container_paths_are_safe(output, source, mountinfo.replace("source ro", "source rw"))
    assert not tool.container_paths_are_safe(output, source, mountinfo.replace("credentials rw", "credentials ro"))
    assert tool.container_paths_are_safe(
        output, source, mountinfo.replace("credentials rw", "credentials ro"), writable=False
    )
    assert not tool.container_paths_are_safe(output, source, mountinfo, writable=False)
    assert not tool.container_paths_are_safe(output, source, mountinfo.splitlines()[0])
    assert not tool.container_paths_are_safe(Path("/opt/crm-g5-source/g5.json"), source, mountinfo)


@pytest.mark.asyncio
async def test_fixture_creates_fifty_scoped_viewers_and_distinct_synthetic_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = fixture_tool()
    permission = Permission(
        id=uuid.uuid4(), code="workspace.view", name="查看工作台", resource="workspace", action="view"
    )
    session = type("FakeSession", (), {})()
    session.scalar = AsyncMock(return_value=permission)
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    added: list[object] = []
    session.add_all = lambda rows: added.extend(rows)
    session.add = lambda row: added.append(row)
    monkeypatch.setattr(tool, "hash_password", lambda _password: "hashed-only")
    monkeypatch.setattr(tool, "create_access_token", lambda user_id: f"access-{user_id}")

    payload = await tool.provision_fixture(session, uuid.uuid4())

    stores = [row for row in added if isinstance(row, Store)]
    roles = [row for row in added if isinstance(row, Role)]
    configs = [row for row in added if isinstance(row, AgentConfig)]
    users = [row for row in added if isinstance(row, User)]
    customers = [row for row in added if isinstance(row, Customer)]
    conversations = [row for row in added if isinstance(row, Conversation)]
    messages = [row for row in added if isinstance(row, Message)]
    audits = [row for row in added if isinstance(row, AuditLog)]
    assert tuple(map(len, (stores, roles, configs, users, customers, conversations, messages))) == (
        1,
        1,
        1,
        50,
        50,
        50,
        50,
    )
    assert roles[0].permissions == [permission]
    assert configs[0].store_id == stores[0].id and configs[0].status == "enabled"
    assert len({user.id for user in users}) == 50
    assert all(build_user_view(user).email == user.email for user in users)
    assert all(conversation.store_id == stores[0].id for conversation in conversations)
    assert len({conversation.id for conversation in conversations}) == 50
    assert len({message.conversation_id for message in messages}) == 50
    assert len(audits) == 1 and audits[0].action == "g5.fixture.provision"
    assert len(payload["clients"]) == 50
    assert {row["session_id"] for row in payload["clients"]} == {str(row.id) for row in conversations}
    assert all(row["access_token"].startswith("access-") and row["csrf_token"] for row in payload["clients"])
    assert session.execute.await_count == 1
    role_assignments = session.execute.await_args.args[1]
    assert len(role_assignments) == 50
    assert all(row["store_id"] == stores[0].id and row["role_id"] == roles[0].id for row in role_assignments)


@pytest.mark.asyncio
async def test_fixture_missing_view_permission_writes_nothing() -> None:
    tool = fixture_tool()
    session = type("FakeSession", (), {})()
    session.scalar = AsyncMock(return_value=None)
    session.add_all = lambda _rows: pytest.fail("must stop before adding data")

    with pytest.raises(ValueError, match="workspace.view"):
        await tool.provision_fixture(session, uuid.uuid4())


def test_secure_pool_file_is_exclusive_and_contains_no_password(tmp_path: Path) -> None:
    tool = fixture_tool()
    output = tmp_path / "clients.json"
    payload = {"clients": [{"access_token": "private-token", "csrf_token": "private-csrf", "session_id": "id"}]}

    tool.write_secure_pool(output, payload)

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert "password" not in output.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        tool.write_secure_pool(output, payload)
    assert json.loads(output.read_text(encoding="utf-8")) == payload


@pytest.mark.asyncio
async def test_fixture_retains_manifest_when_database_commit_outcome_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool = fixture_tool()
    output = tmp_path / "clients.json"

    class FailingCommit:
        async def __aenter__(self) -> object:
            return self

        async def __aexit__(self, *_args: object) -> None:
            raise RuntimeError("commit failed")

        def begin(self) -> "FailingCommit":
            return self

    monkeypatch.setattr(tool, "validate_target", lambda _env, _path: None)
    database_url = "postgresql+asyncpg://synthetic@staging-db/crm"
    expected = hashlib.sha256(database_url.encode("utf-8")).hexdigest()
    monkeypatch.setattr(
        tool, "get_settings", lambda: type("Settings", (), {"app_env": "staging", "database_url": database_url})()
    )
    monkeypatch.setattr(tool, "session_factory", lambda: FailingCommit())
    monkeypatch.setattr(tool, "provision_fixture", AsyncMock(return_value={"clients": []}))

    with pytest.raises(tool.FixtureCommitUnknownError):
        await tool.execute_fixture(output, expected)
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == {"clients": []}
