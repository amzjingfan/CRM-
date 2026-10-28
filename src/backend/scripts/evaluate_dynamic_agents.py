"""动态 Agent 确定性边界评测；不代表真实模型的语义选择准确率。"""

import argparse
import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.agents.management.repository import PublishedAgent
from app.agents.orchestration.router import RouteDecisionError, route_agents
from app.agents.providers.tool_calling import FunctionCall, ToolTurn
from app.agents.safety.input import UntrustedSource, prepare_untrusted_text
from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool
from app.shared.exceptions.errors import AppError
from app.tools.contracts import ToolInvocation, ToolResult


class DynamicCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    kind: Literal["input", "route", "tool"]
    text: str = "订单物流在哪里"
    source: UntrustedSource = "user_message"
    expected: str
    candidates: int = 1
    selections: list[int] = Field(default_factory=list)
    tool_name: str = "query_order"
    permissions: list[str] = Field(default_factory=list)
    arguments: dict[str, object] = Field(default_factory=dict)


class EvaluationExecutor:
    """仅用合成结果验证执行边界，绝不访问业务或外部平台。"""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls += 1
        return ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"status": "shipped"})


async def evaluate_case(case: DynamicCase) -> bool:
    if case.kind == "input":
        try:
            result = prepare_untrusted_text(case.text, source=case.source)
        except AppError:
            return case.expected == "blocked"
        actual = "redacted" if result.redacted else "labeled"
        return actual == case.expected and result.as_user_message()["role"] == "user"
    if case.kind == "tool":
        executor = EvaluationExecutor()
        context = AgentToolContext(
            uuid.uuid4(), uuid.uuid4(), "synthetic-order", uuid.uuid4(), frozenset(case.permissions), "eval"
        )
        tools = build_agent_tools((case.tool_name,), context=context, executor=executor)
        try:
            tool_result = await invoke_selected_tool(tools[0], case.arguments)
        except ValueError:
            return case.expected == "invalid_arguments" and executor.calls == 0
        tool_status = tool_result.get("status") if isinstance(tool_result, dict) else None
        return tool_status == case.expected and (tool_status == "succeeded" or executor.calls == 0)
    store = uuid.uuid4()
    agents = tuple(
        PublishedAgent(
            uuid.uuid5(store, str(index)),
            store,
            1,
            f"Agent {index}",
            f"a{index}",
            "合成测试职责",
            "service",
            "deepseek",
            "synthetic-model",
            MappingProxyType({}),
            "hash",
            (),
            (),
            True,
        )
        for index in range(case.candidates)
    )

    class ScriptedRouter:
        async def complete(
            self, *, messages: tuple[dict[str, object], ...], tools: tuple[BaseTool, ...], max_output_tokens: int
        ) -> ToolTurn:
            call = FunctionCall(
                "eval-route",
                "route_agents",
                {
                    "selections": [
                        {"agent_id": str(uuid.uuid5(store, str(index))), "subquestion": case.text}
                        for index in case.selections
                    ]
                },
            )
            return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 1, 1)

    try:
        plan = await route_agents(
            question=case.text,
            agents=agents,
            provider=ScriptedRouter(),
            deadline=time.monotonic() + 5,
            max_catalog_tokens=4096,
        )
    except RouteDecisionError as error:
        return error.reason_code == case.expected
    return case.expected == "accepted" and len(plan.selections) == len(case.selections)


async def evaluate_dataset(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    cases = [DynamicCase.model_validate_json(line) for line in raw.decode("utf-8").splitlines() if line]
    if not cases or len({item.case_id for item in cases}) != len(cases):
        raise ValueError("评测样本为空或 ID 重复")
    failed = [case.case_id for case in cases if not await evaluate_case(case)]
    return {
        "gate": "dynamic_agent_contract_v1",
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "sample_count": len(cases),
        "failed_case_ids": failed,
        "passed": not failed,
        "live_model_evaluation": False,
        "semantic_routing_accuracy_measured": False,
        "platform_send_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(evaluate_dataset(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
