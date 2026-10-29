"""只有确定尚未进入平台写入时才能使用的发送异常。"""

from app.shared.exceptions.errors import AppError


class DeliveryNotStarted(AppError):
    """已知零外部写入；允许原交付计划明确重试，不伪造消息记录。"""
