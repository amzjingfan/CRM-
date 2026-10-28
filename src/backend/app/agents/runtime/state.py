"""动态 Agent 运行阶段状态机，外部状态仍映射现有 AgentRun.status。"""

from enum import StrEnum


class RunPhase(StrEnum):
    CREATED = "created"
    FROZEN = "frozen"
    ROUTING = "routing"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    REVIEW_READY = "review_ready"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


_NEXT: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.CREATED: frozenset({RunPhase.FROZEN, RunPhase.FAILED, RunPhase.TIMEOUT, RunPhase.CANCELLED}),
    RunPhase.FROZEN: frozenset({RunPhase.ROUTING, RunPhase.FAILED, RunPhase.TIMEOUT, RunPhase.CANCELLED}),
    RunPhase.ROUTING: frozenset(
        {RunPhase.EXECUTING, RunPhase.REVIEW_REQUIRED, RunPhase.FAILED, RunPhase.TIMEOUT, RunPhase.CANCELLED}
    ),
    RunPhase.EXECUTING: frozenset(
        {RunPhase.AGGREGATING, RunPhase.REVIEW_REQUIRED, RunPhase.FAILED, RunPhase.TIMEOUT, RunPhase.CANCELLED}
    ),
    RunPhase.AGGREGATING: frozenset(
        {RunPhase.REVIEW_READY, RunPhase.REVIEW_REQUIRED, RunPhase.FAILED, RunPhase.TIMEOUT, RunPhase.CANCELLED}
    ),
}
_TERMINAL = frozenset(
    {RunPhase.REVIEW_READY, RunPhase.REVIEW_REQUIRED, RunPhase.FAILED, RunPhase.TIMEOUT, RunPhase.CANCELLED}
)


class RunStateMachine:
    def __init__(self, phase: RunPhase = RunPhase.CREATED) -> None:
        self.phase = phase

    def advance(self, target: RunPhase) -> RunPhase:
        if self.phase in _TERMINAL:
            raise ValueError("terminal Agent run cannot advance")
        if target not in _NEXT[self.phase]:
            raise ValueError("invalid Agent phase transition")
        self.phase = target
        return target
