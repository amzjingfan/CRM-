"""断线审计只允许收敛本次授权范围内仍在运行的 Agent 记录。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.chat import service


class _ScalarResult:
    def __init__(self, values: list[uuid.UUID]) -> None:
        self.values = values

    def all(self) -> list[uuid.UUID]:
        return self.values

    def one_or_none(self) -> uuid.UUID | None:
        return self.values[0] if self.values else None


class _AuditSession:
    def __init__(self, results: list[list[uuid.UUID]]) -> None:
        self.results = [_ScalarResult(values) for values in results]
        self.statements: list[object] = []
        self.commit = AsyncMock()

    async def __aenter__(self) -> "_AuditSession":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def scalars(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_cancel_reconciliation_is_scoped_and_compare_and_swap(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    store_id = uuid.uuid4()
    trace_id = str(uuid.uuid4())
    audit_session = _AuditSession([[run_id], [run_id]])
    monkeypatch.setattr(service, "session_factory", lambda: audit_session)
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={store_id}))

    assert await service.reconcile_cancelled_sse_agent_run(
        SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
        conversation_id,
        trace_id,
        datetime.now(UTC),
    )

    assert len(audit_session.statements) == 2
    candidate, update = audit_session.statements
    candidate_sql = str(candidate)
    candidate_values = list(candidate.compile().params.values())
    assert all(
        column in candidate_sql for column in ("trace_id", "conversation_id", "store_id", "created_at", "status")
    )
    assert all(value in candidate_values for value in (trace_id, conversation_id, "running"))
    assert store_id in next(value for value in candidate_values if isinstance(value, list))
    update_sql = str(update)
    update_values = list(update.compile().params.values())
    assert "agent_runs.status" in update_sql and "agent_runs.id" in update_sql
    assert all(value in update_values for value in (run_id, "running", "failed", "AGENT_CANCELLED"))
    audit_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_reconciliation_does_not_write_without_authorized_store(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_session = _AuditSession([])
    monkeypatch.setattr(service, "session_factory", lambda: audit_session)
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value=set()))

    assert not await service.reconcile_cancelled_sse_agent_run(
        SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
        uuid.uuid4(),
        str(uuid.uuid4()),
        datetime.now(UTC),
    )
    assert audit_session.statements == []
    audit_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_reconciliation_preserves_already_terminal_run(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_session = _AuditSession([[]])
    monkeypatch.setattr(service, "session_factory", lambda: audit_session)
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={uuid.uuid4()}))

    assert not await service.reconcile_cancelled_sse_agent_run(
        SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
        uuid.uuid4(),
        str(uuid.uuid4()),
        datetime.now(UTC),
    )
    assert len(audit_session.statements) == 1
    audit_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_reconciliation_rejects_ambiguous_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_session = _AuditSession([[uuid.uuid4(), uuid.uuid4()]])
    monkeypatch.setattr(service, "session_factory", lambda: audit_session)
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={uuid.uuid4()}))

    with pytest.raises(RuntimeError, match="匹配多个运行记录"):
        await service.reconcile_cancelled_sse_agent_run(
            SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
            uuid.uuid4(),
            str(uuid.uuid4()),
            datetime.now(UTC),
        )
    assert len(audit_session.statements) == 1
    audit_session.commit.assert_not_awaited()
