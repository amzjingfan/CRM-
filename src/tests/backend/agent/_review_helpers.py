"""确定性模型端口中，显式返回独立复核 function call。"""

import json

from app.agents.providers.tool_calling import FunctionCall, ToolTurn


def accepted_review_turn(messages) -> ToolTurn:
    payload = json.loads(messages[-1]["content"])
    call = FunctionCall(
        "review-ok",
        "review_answer_evidence",
        {
            "supported": True,
            "evidence_ids": list(payload["evidence"]),
            "reason_code": "supported",
            "privacy_reviewed": True,
            "output_rewrite_required": False,
            "redactions": [],
        },
    )
    return ToolTurn(None, (call,), {"role": "assistant", "content": None}, 2, 2)
