"""G5 Runner 预检只允许读取配置与隔离夹具存在性。"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from scripts import check_sse_staging_fixture
from scripts.check_sse_staging_fixture import ReadinessError, check_readiness, run_check, safe_report


class ReadOnlySession:
    def __init__(self, results: list[object], *, fail: bool = False) -> None:
        self.results = iter(results)
        self.fail = fail
        self.statements: list[str] = []

    async def scalar(self, statement: object) -> object:
        self.statements.append(str(statement))
        if self.fail:
            raise RuntimeError("postgresql://sensitive-password@private-host")
        return next(self.results)


def test_readiness_only_selects_existing_permission_and_fixture() -> None:
    session = ReadOnlySession([uuid.uuid4(), None])
    report = asyncio.run(check_readiness(session, "staging"))
    assert report == {"mode": "check_only", "ready": True, "provider_calls": 0}
    assert len(session.statements) == 2
    assert all(statement.lstrip().startswith("SELECT ") for statement in session.statements)


@pytest.mark.parametrize(
    ("app_env", "results", "expected_stage"),
    [
        ("production", [], "config"),
        ("staging", [None], "permission_missing"),
        ("staging", [uuid.uuid4(), uuid.uuid4()], "existing_fixture"),
    ],
)
def test_readiness_fails_closed(app_env: str, results: list[object], expected_stage: str) -> None:
    session = ReadOnlySession(results)
    with pytest.raises(ReadinessError) as exc:
        asyncio.run(check_readiness(session, app_env))
    assert exc.value.stage == expected_stage
    if app_env == "production":
        assert session.statements == []


def test_database_error_reports_only_fixed_category() -> None:
    session = ReadOnlySession([], fail=True)
    with pytest.raises(ReadinessError) as exc:
        asyncio.run(check_readiness(session, "staging"))
    assert safe_report(exc.value) == {
        "mode": "check_only",
        "ready": False,
        "failure_stage": "database_read",
        "provider_calls": 0,
    }
    assert "sensitive-password" not in str(safe_report(exc.value))


def test_mismatched_independent_database_fingerprint_never_opens_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        check_sse_staging_fixture,
        "get_settings",
        lambda: SimpleNamespace(app_env="staging", database_url="postgresql://secret@private-host/db"),
    )

    def forbidden_session() -> None:
        raise AssertionError("database session must not open before fingerprint match")

    monkeypatch.setattr(check_sse_staging_fixture, "session_factory", forbidden_session)
    with pytest.raises(ReadinessError) as exc:
        asyncio.run(run_check("0" * 64))
    assert safe_report(exc.value)["failure_stage"] == "config"
