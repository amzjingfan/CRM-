"""只对原 G5 批次修复邮箱，拒绝错配或不完整的私有 manifest。"""

import hashlib
import sys
import uuid
from pathlib import Path
from typing import Self
from unittest.mock import AsyncMock

import pytest

from app.auth.security import create_access_token
from app.shared.config.settings import get_settings
from scripts import prepare_sse_staging_content as content
from scripts import prepare_sse_staging_fixture as fixture


def original_fixture_payload() -> dict[str, object]:
    run_id = uuid.uuid4()
    users = [uuid.uuid4() for _ in range(50)]
    sessions = [uuid.uuid4() for _ in range(50)]
    return {
        "manifest": {
            "run_id": str(run_id),
            "store_id": str(uuid.uuid4()),
            "role_id": str(uuid.uuid4()),
            "user_ids": [str(value) for value in users],
            "conversation_ids": [str(value) for value in sessions],
        },
        "clients": [
            {
                "access_token": create_access_token(user_id),
                "csrf_token": "synthetic-csrf",
                "session_id": str(session_id),
            }
            for user_id, session_id in zip(users, sessions, strict=True)
        ],
    }


@pytest.fixture(autouse=True)
def runtime_signing_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setenv("EXPECTED_RUNTIME_JWT_SHA256", hashlib.sha256(settings.jwt_secret_key.encode()).hexdigest())
    monkeypatch.setenv("EXPECTED_RUNTIME_JWT_ALGORITHM", settings.jwt_algorithm)


def test_reconcile_accepts_only_complete_original_fixture_mapping() -> None:
    payload = original_fixture_payload()

    manifest = fixture.validate_reconciliation_payload(payload)

    assert len(manifest.user_ids) == len(manifest.conversation_ids) == 50
    assert manifest.run_id == uuid.UUID(payload["manifest"]["run_id"])  # type: ignore[index]


def test_read_only_content_reconciliation_validates_renewed_pool_mapping() -> None:
    original = original_fixture_payload()
    manifest = fixture.validate_reconciliation_payload(original)
    renewed = fixture.build_renewed_credentials(original, manifest)

    content.validate_renewed_payload(renewed, manifest)
    renewed["clients"][0]["access_token"] = create_access_token(uuid.uuid4())
    with pytest.raises(ValueError, match="fixture"):
        content.validate_renewed_payload(renewed, manifest)


@pytest.mark.parametrize("damage", ["wrong_owner", "duplicate_session", "missing_user"])
def test_reconcile_rejects_tampered_private_fixture(damage: str) -> None:
    payload = original_fixture_payload()
    manifest = payload["manifest"]
    clients = payload["clients"]
    assert isinstance(manifest, dict) and isinstance(clients, list)
    if damage == "wrong_owner":
        clients[0]["access_token"] = create_access_token(uuid.uuid4())
    elif damage == "duplicate_session":
        clients[1]["session_id"] = clients[0]["session_id"]
    else:
        manifest["user_ids"] = manifest["user_ids"][:-1]

    with pytest.raises(ValueError, match="fixture"):
        fixture.validate_reconciliation_payload(payload)


@pytest.mark.asyncio
async def test_reconcile_check_reads_original_batch_without_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = original_fixture_payload()
    manifest = fixture.validate_reconciliation_payload(payload)
    source = tmp_path / "g5-38852775454-1.json"
    output = tmp_path / "g5-38852775454-2.json"
    source.write_text("private", encoding="utf-8")

    class FakeSession:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def begin(self) -> "FakeSession":
            return self

    inspect = AsyncMock(return_value=[object()] * 50)
    repair = AsyncMock()
    monkeypatch.setattr(fixture, "validate_reconciliation_target", lambda _env, _output, *, writable: None)
    monkeypatch.setattr(fixture, "validate_database_target", lambda _db, _sha: None)
    monkeypatch.setattr(fixture, "read_reconciliation_source", lambda _source, _output: manifest, raising=False)
    monkeypatch.setattr(fixture, "session_factory", lambda: FakeSession())
    monkeypatch.setattr(fixture, "inspect_existing_reconciliation", inspect)
    monkeypatch.setattr(fixture, "reconcile_fixture_emails", repair)

    result = await fixture.execute_reconciliation(source, output, "expected-db-sha", execute=False)

    assert result == {"mode": "reconcile_check", "ready": True, "matched_users": 50, "provider_calls": 0}
    assert not output.exists()
    assert inspect.await_count == 1 and inspect.await_args.kwargs == {"lock_users": False}
    repair.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_keeps_new_private_file_when_database_commit_is_uncertain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = original_fixture_payload()
    manifest = fixture.validate_reconciliation_payload(payload)
    source = tmp_path / "g5-38852775454-1.json"
    output = tmp_path / "g5-38852775454-2.json"
    source.write_text("original-private-material", encoding="utf-8")

    class FailingCommit:
        async def __aenter__(self) -> object:
            return self

        async def __aexit__(self, *_args: object) -> None:
            raise RuntimeError("commit result unavailable")

    class FakeSession:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def begin(self) -> FailingCommit:
            return FailingCommit()

    monkeypatch.setattr(fixture, "validate_reconciliation_target", lambda _env, _output, *, writable: None)
    monkeypatch.setattr(fixture, "validate_database_target", lambda _db, _sha: None)
    monkeypatch.setattr(fixture, "read_reconciliation_source", lambda _source, _output: manifest)
    monkeypatch.setattr(fixture, "session_factory", lambda: FakeSession())
    monkeypatch.setattr(fixture, "inspect_existing_reconciliation", AsyncMock(return_value=[object()] * 50))
    monkeypatch.setattr(fixture, "reconcile_fixture_emails", AsyncMock(return_value=payload))

    with pytest.raises(fixture.FixtureCommitUnknownError, match="fixture_commit_unknown"):
        await fixture.execute_reconciliation(source, output, "expected-db-sha", execute=True)

    assert output.exists()
    assert source.read_text(encoding="utf-8") == "original-private-material"


def test_reconcile_check_cli_reports_only_fixed_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    source = tmp_path / "g5-38852775454-1.json"
    output = tmp_path / "g5-38852775454-2.json"
    run = AsyncMock(return_value={"mode": "reconcile_check", "ready": True, "matched_users": 50, "provider_calls": 0})
    monkeypatch.setattr(fixture, "execute_reconciliation", run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fixture",
            "--reconcile-check",
            "--source-credentials-file",
            str(source),
            "--credentials-file",
            str(output),
            "--expected-database-sha256",
            "0" * 64,
        ],
    )

    fixture.main()

    assert capsys.readouterr().out.strip() == (
        '{"matched_users": 50, "mode": "reconcile_check", "provider_calls": 0, "ready": true}'
    )
    assert run.await_args.kwargs == {"execute": False}
