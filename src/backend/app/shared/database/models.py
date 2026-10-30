"""集中导入全部 ORM 模型，确保 Alembic 能发现完整 metadata。"""

from app.agents.delivery.models import ReplyBatch
from app.agents.management.config_models import AgentConfig, AgentTask
from app.agents.management.models import AgentConfigVersion
from app.agents.management.templates.models import (
    AgentTemplate,
    AgentTemplateBatch,
    AgentTemplateBatchItem,
    AgentTemplateVersion,
)
from app.agents.memory.models import AgentSessionMemory
from app.agents.runtime.models import AgentRun
from app.agents.tools.logistics_updates.models import (
    LogisticsNotification,
    LogisticsNotificationPolicy,
    LogisticsObservationRow,
    LogisticsOrderScan,
)
from app.agents.tools.models import AgentCollaborationEntry
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.dashboard.models import MetricDaily
from app.integrations.models import TikTokOAuthJob, WebhookEvent
from app.knowledge_base.document_models import (
    KnowledgeFile,
    KnowledgeFileChunk,
    KnowledgeFileImportReceipt,
    KnowledgeFileSettings,
    KnowledgeFileUnit,
    KnowledgeFileVersion,
)
from app.knowledge_base.models import KnowledgeCategory, KnowledgeChunk, KnowledgeDocument, KnowledgeImportJob
from app.marketing.models import CustomerReview, MarketingCampaign, MarketingEvent
from app.orders.models import Order, OrderItem
from app.reception.models import (
    ReceptionGroup,
    ReceptionMutation,
    ReceptionPolicy,
    ReceptionPolicyStore,
    ReceptionReply,
)
from app.reception_assignment.models import (
    ReceptionAgentConfig,
    ReceptionDepartmentAgent,
    ReceptionDepartmentConfig,
    ReceptionStoreConfig,
)
from app.shared.database.base import Permission, Role, User, UserLoginSession
from app.stores.models import ChannelAccount, Store
from app.tools.models import CouponIssuance, ToolCall
from app.users.models import Department

__all__ = [
    "ReplyBatch",
    "AgentCollaborationEntry",
    "LogisticsNotification",
    "LogisticsNotificationPolicy",
    "LogisticsObservationRow",
    "LogisticsOrderScan",
    "AuditLog",
    "AgentRun",
    "AgentConfig",
    "AgentConfigVersion",
    "AgentSessionMemory",
    "AgentTask",
    "AgentTemplate",
    "AgentTemplateBatch",
    "AgentTemplateBatchItem",
    "AgentTemplateVersion",
    "ChannelAccount",
    "Conversation",
    "Customer",
    "CustomerReview",
    "Department",
    "CouponIssuance",
    "KnowledgeCategory",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeFile",
    "KnowledgeFileChunk",
    "KnowledgeFileImportReceipt",
    "KnowledgeFileSettings",
    "KnowledgeFileUnit",
    "KnowledgeFileVersion",
    "KnowledgeImportJob",
    "MarketingCampaign",
    "MarketingEvent",
    "MetricDaily",
    "Message",
    "Order",
    "OrderItem",
    "Permission",
    "ReceptionGroup",
    "ReceptionMutation",
    "ReceptionPolicy",
    "ReceptionPolicyStore",
    "ReceptionReply",
    "ReceptionAgentConfig",
    "ReceptionDepartmentAgent",
    "ReceptionDepartmentConfig",
    "ReceptionStoreConfig",
    "Role",
    "Store",
    "ToolCall",
    "TikTokOAuthJob",
    "User",
    "UserLoginSession",
    "WebhookEvent",
]
