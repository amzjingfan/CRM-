"""CRM 内部会话状态规则。"""

from datetime import datetime
from typing import Protocol


class ClosableConversation(Protocol):
    status: str
    closed_at: datetime | None


def reopen_on_new_buyer_message(conversation: ClosableConversation, created_at: datetime) -> bool:
    """仅晚于人工关闭时间的新买家消息恢复会话；历史回填不恢复。"""
    if conversation.status != "closed" or conversation.closed_at is None or created_at <= conversation.closed_at:
        return False
    conversation.status = "active"
    conversation.closed_at = None
    return True
