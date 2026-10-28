"""Agent 运行阶段只有明确的前进边，不允许终态再次写入。"""

import pytest

from app.agents.runtime.state import RunPhase, RunStateMachine


def test_successful_multi_agent_state_sequence() -> None:
    state = RunStateMachine()
    for phase in (
        RunPhase.FROZEN,
        RunPhase.ROUTING,
        RunPhase.EXECUTING,
        RunPhase.AGGREGATING,
        RunPhase.REVIEW_READY,
    ):
        state.advance(phase)
    assert state.phase is RunPhase.REVIEW_READY
    with pytest.raises(ValueError, match="terminal"):
        state.advance(RunPhase.EXECUTING)


def test_timeout_can_close_any_active_stage_once() -> None:
    state = RunStateMachine()
    state.advance(RunPhase.FROZEN)
    state.advance(RunPhase.ROUTING)
    state.advance(RunPhase.TIMEOUT)
    with pytest.raises(ValueError, match="terminal"):
        state.advance(RunPhase.TIMEOUT)


def test_cannot_skip_route_or_aggregate() -> None:
    state = RunStateMachine()
    with pytest.raises(ValueError, match="transition"):
        state.advance(RunPhase.EXECUTING)
