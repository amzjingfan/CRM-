"""仅接收已核验同步观察的物流更新深模块。"""

from .contracts import (
    AuthorizationSnapshot,
    BoundLogisticsEvent,
    DeliveryMode,
    DeliveryReceipt,
    LogisticsObservation,
    LogisticsRepository,
    LogisticsScope,
    LogisticsUpdateResult,
    NotificationArguments,
    NotificationDeliveryPort,
    PreparedLogisticsNotification,
    ReviewDecision,
    TrackingEvent,
)
from .memory import InMemoryLogisticsRepository
from .service import LogisticsUpdateService, build_notify_logistics_update_tool

__all__ = [
    "AuthorizationSnapshot",
    "BoundLogisticsEvent",
    "DeliveryMode",
    "DeliveryReceipt",
    "InMemoryLogisticsRepository",
    "LogisticsObservation",
    "LogisticsRepository",
    "LogisticsScope",
    "LogisticsUpdateResult",
    "LogisticsUpdateService",
    "NotificationArguments",
    "NotificationDeliveryPort",
    "PreparedLogisticsNotification",
    "ReviewDecision",
    "TrackingEvent",
    "build_notify_logistics_update_tool",
]
