"""结构化日志和请求追踪配置。"""

import hashlib
import json
import logging
import re
import uuid
from datetime import UTC, datetime

SENSITIVE_FIELD_NAME = (
    r"(?:[a-z0-9_-]+[_-])?"
    r"(?:"
    r"api[_-]?key|access[_-]?key|secret(?:[_-]?key)?|password"
    r"|credential(?:[_-]?encryption)?[_-]?key|credential"
    r"|authorization|auth[_-]?code|oauth[_-]?(?:code|state)|access[_-]?token|refresh[_-]?token"
    r"|raw[_-]?body|content|message|address|street"
    r")"
)
QUOTED_SENSITIVE_VALUE = r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
JSON_SENSITIVE_VALUE = rf"({QUOTED_SENSITIVE_VALUE}|[^,}}\s;]+)"
# 未加引号的 key=value 日志没有可靠的空格边界。为避免多词消息或地址只脱敏
# 第一个单词，宁可把值连同后续空格文本隐藏到明确的逗号、分号、换行或行尾。
KEY_VALUE_SENSITIVE_VALUE = rf"({QUOTED_SENSITIVE_VALUE}|[^,;\r\n]+)"
SENSITIVE_JSON_PATTERN = re.compile(rf"(?i)([\"']{SENSITIVE_FIELD_NAME}[\"']\s*:\s*){JSON_SENSITIVE_VALUE}")
SENSITIVE_KEY_VALUE_PATTERN = re.compile(rf"(?i)\b({SENSITIVE_FIELD_NAME})(\s*[:=]\s*){KEY_VALUE_SENSITIVE_VALUE}")
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
OAUTH_QUERY_PATTERN = re.compile(r"(?i)([?&](?:code|state)=)[^&#\s\"']+")
URL_CREDENTIAL_PATTERN = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^/\s:@]+:)[^@\s/]+(@)")
SAFE_EVENT_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
SAFE_LOG_METADATA_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/,-]{0,99}$")
INVALID_LOG_METADATA = "[INVALID_LOG_METADATA]"

# 只有这些不含客户正文和凭证的运行元数据可以进入生产 JSON 日志。
# 严禁加入 content、message、prompt、reasoning_content 或地址类字段。
LOW_SENSITIVITY_LOG_FIELDS = (
    "provider",
    "model",
    "prompt_version",
    "provider_request_id",
    "agent_run_id",
    "attempt",
    "finish_reason",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "first_output_latency_ms",
    "total_latency_ms",
    "content_length",
    "reasoning_length",
    "error_code",
    "retriable",
    "status_code",
    "prompt_safety_state",
    "prompt_safety_reason_code",
    "prompt_safety_policy_version",
)


def redact_log_text(value: object) -> str:
    """脱敏可能误入日志的凭证和客户正文。

    正式业务代码仍禁止主动记录请求正文。本函数是日志出口的纵深防御，
    防止第三方异常或临时诊断把常见 Token、密钥、地址和消息字段写入日志。
    """
    text = str(value)
    text = BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    text = OAUTH_QUERY_PATTERN.sub(r"\1[REDACTED]", text)
    text = URL_CREDENTIAL_PATTERN.sub(r"\1[REDACTED]\2", text)
    text = SENSITIVE_JSON_PATTERN.sub(r'\1"[REDACTED]"', text)
    text = SENSITIVE_KEY_VALUE_PATTERN.sub(r"\1\2[REDACTED]", text)
    return JWT_PATTERN.sub("[REDACTED_JWT]", text)


def sanitize_log_metadata(value: object) -> str:
    """只允许有限 ASCII 标识进入结构化日志。

    白名单字段名不能证明字段值可信。供应商响应头、请求 Header 和未来适配器
    都可能把正文塞入标识字段；不符合字符集或长度契约的值统一替换，不尝试
    依靠敏感词正则推断其是否安全。
    """
    text = str(value)
    if text == "-" or SAFE_LOG_METADATA_PATTERN.fullmatch(text):
        return text
    return INVALID_LOG_METADATA


def sanitize_log_uuid(value: object) -> str:
    """只允许标准 UUID 或框架缺省标记进入追踪字段。"""
    text = str(value)
    if text == "-":
        return text
    try:
        normalized = str(uuid.UUID(text))
    except (ValueError, AttributeError):
        return INVALID_LOG_METADATA
    return normalized if text == normalized else INVALID_LOG_METADATA


def fingerprint_log_identifier(value: object) -> str:
    """将外部供应商标识转换为稳定不可逆摘要。"""
    text = str(value)
    if text == "-":
        return text
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


class TraceIdFilter(logging.Filter):
    """为没有显式 trace_id 的框架日志提供安全默认值。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return True


class JsonFormatter(logging.Formatter):
    """将框架与业务日志统一为低敏、单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        raw_event = getattr(record, "event", None)
        event_candidate = raw_event if isinstance(raw_event, str) else ""
        # 任意自由文本日志都可能包含没有字段名的 Prompt、客户正文或凭证，无法靠
        # 正则可靠识别。生产出口只接受稳定事件名，诊断信息必须走下方低敏白名单。
        event = event_candidate if SAFE_EVENT_PATTERN.fullmatch(event_candidate) else "unstructured_log_redacted"
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "event": event,
            "trace_id": sanitize_log_uuid(getattr(record, "trace_id", "-")),
            "message": event,
        }
        for field_name in LOW_SENSITIVITY_LOG_FIELDS:
            value = getattr(record, field_name, None)
            if isinstance(value, str):
                if field_name == "provider_request_id":
                    payload[field_name] = fingerprint_log_identifier(value)
                elif field_name == "agent_run_id":
                    payload[field_name] = sanitize_log_uuid(value)
                else:
                    payload[field_name] = sanitize_log_metadata(value)
            elif isinstance(value, (int, float, bool)):
                payload[field_name] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """输出单行 JSON，日志字段只包含低敏运行信息。"""
    handler = logging.StreamHandler()
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Uvicorn 默认安装独立文本 Handler；统一向根 Logger 传播，避免同一容器混出两种格式。
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        framework_logger = logging.getLogger(logger_name)
        framework_logger.handlers.clear()
        framework_logger.propagate = True
