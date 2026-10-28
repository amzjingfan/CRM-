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
