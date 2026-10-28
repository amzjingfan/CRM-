"""把受控只读工具结果缩成模型所需的低敏事实。"""

from app.agents.safety.input import prepare_untrusted_text
from app.shared.exceptions.errors import AppError
from app.tools.contracts import ToolResult

MODEL_FIELDS: dict[str, frozenset[str]] = {
    "query_order": frozenset(
        {"status", "payment_status", "fulfillment_status", "currency", "total_amount", "ordered_at"}
    ),
    "query_logistics": frozenset(
        {"tracking_status", "latest_tracking_description", "latest_tracking_at", "shipped_at", "delivered_at"}
    ),
    "query_customer_profile": frozenset({"tags", "order_count", "total_spend"}),
}


def project_tool_result(tool_name: str, result: ToolResult) -> dict[str, object]:
    """资源 ID 留在可信服务端，模型只见核准字段及明确的脱敏状态。"""
    allowed = MODEL_FIELDS.get(tool_name)
    if allowed is None:
        raise ValueError("未知只读工具")
    projected: dict[str, object] = {
        "tool_call_id": str(result.tool_call_id),
        "status": result.status,
        "error_code": result.error_code,
    }
    if result.status != "succeeded" or result.data is None:
        return projected
    facts: dict[str, object] = {}
    redacted: list[str] = []
    for key, value in result.data.items():
        if key not in allowed or value is None:
            continue
        if isinstance(value, str):
            try:
                facts[key] = prepare_untrusted_text(value, source="tool_result").text
            except AppError:
                redacted.append(key)
        elif key == "tags" and isinstance(value, list):
            tags = []
            for tag in value:
                if not isinstance(tag, str):
                    continue
                try:
                    tags.append(prepare_untrusted_text(tag, source="tool_result").text)
                except AppError:
                    redacted.append(key)
            facts[key] = tags
        elif isinstance(value, int | float | bool):
            facts[key] = value
    projected["facts"] = facts
    if redacted:
        projected["redacted_fields"] = sorted(set(redacted))
    return projected
