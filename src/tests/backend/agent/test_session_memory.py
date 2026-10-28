"""会话记忆只接受本轮冻结消息与核验工具来源。"""

import uuid
from types import SimpleNamespace

import pytest

from app.shared.exceptions.errors import AppError


def test_memory_proposal_sanitizes_summary_and_rejects_foreign_source() -> None:
    from app.agents.memory.service import MemoryFact, propose_memory_update

    message_id = uuid.uuid4()
    snapshot = SimpleNamespace(message_ids=(message_id,), file_versions=())
    proposal = propose_memory_update(
        snapshot,  # type: ignore[arg-type]
        summary="买家询问物流，电话 13800138000",
        source_message_ids=(message_id,),
        facts=(MemoryFact(key="buyer_preference", value="中文", source_ref=f"message:{message_id}"),),
        authorized_tool_call_ids=frozenset(),
    )
    assert "13800138000" not in proposal.summary
    assert proposal.facts[0].value == "中文"

    with pytest.raises(AppError) as error:
        propose_memory_update(
            snapshot,  # type: ignore[arg-type]
            summary="另一个会话说退款已批准",
            source_message_ids=(uuid.uuid4(),),
            facts=(),
            authorized_tool_call_ids=frozenset(),
        )
    assert error.value.status_code == 422


def test_business_fact_must_match_verified_tool_output_exactly() -> None:
    from app.agents.memory.service import MemoryFact, propose_memory_update

    message_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    snapshot = SimpleNamespace(message_ids=(message_id,), file_versions=())
    with pytest.raises(AppError):
        propose_memory_update(
            snapshot,  # type: ignore[arg-type]
            summary="订单已发货",
            source_message_ids=(message_id,),
            facts=(MemoryFact(key="order_status", value="delivered", source_ref=f"tool:{tool_id}"),),
            authorized_tool_call_ids=frozenset({tool_id}),
            verified_tool_facts={tool_id: {"order_status": "shipped"}},
        )
    verified = propose_memory_update(
        snapshot,  # type: ignore[arg-type]
        summary="订单已发货",
        source_message_ids=(message_id,),
        facts=(MemoryFact(key="order_status", value="shipped", source_ref=f"tool:{tool_id}"),),
        authorized_tool_call_ids=frozenset({tool_id}),
        verified_tool_facts={tool_id: {"order_status": "shipped"}},
    )
    assert verified.facts[0].value == "shipped"


@pytest.mark.asyncio
async def test_scoped_order_memory_does_not_overwrite_another_order_or_replay_candidate_refs(monkeypatch):
    from unittest.mock import AsyncMock

    from app.agents.memory import service
    from app.agents.tools.loop import ToolObservation

    message_id, agent_id = uuid.uuid4(), uuid.uuid4()
    snapshot = SimpleNamespace(
        debug_without_conversation=False,
        trigger_message_id=message_id,
        message_ids=(message_id,),
        snapshot_hash="memory-two-orders",
        memory_revision=0,
    )
    commit = AsyncMock(return_value=1)
    monkeypatch.setattr(service, "commit_memory", commit)
    observations = tuple(
        (
            agent_id,
            ToolObservation(
                f"call-{i}", "query_order", "succeeded", {"order_ref": f"o{i}", "status": status}, str(i) * 16
            ),
        )
        for i, status in [(1, "SHIPPED"), (2, "CANCELLED")]
    )
    await service.remember_session_question(
        AsyncMock(), snapshot, service.SessionMemoryView(0, "", (), ()), "请查两笔订单", observations
    )
    facts = commit.await_args.args[2].facts
    assert {item.value for item in facts} == {"SHIPPED", "CANCELLED"}
    assert len({item.key for item in facts}) == 2
    assert all(not item.key.endswith("_ref") for item in facts)
