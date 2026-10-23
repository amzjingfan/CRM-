"""集中导入全部 ORM 模型，确保 Alembic 能发现完整 metadata。"""

from app.agent.models import AgentRun
from app.agent_management.models import AgentConfig, AgentTask
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.dashboard.models import MetricDaily
from app.integrations.models import TikTokOAuthJob, WebhookEvent
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
from app.shared.database.base import Permission, Role, User
from app.stores.models import ChannelAccount, Store
from app.tools.models import CouponIssuance, ToolCall
from app.users.models import Department

__all__ = [
    "AuditLog",
    "AgentRun",
    "AgentConfig",
    "AgentTask",
    "ChannelAccount",
    "Conversation",
    "Customer",
    "CustomerReview",
    "Department",
    "CouponIssuance",
    "KnowledgeCategory",
    "KnowledgeChunk",
    "KnowledgeDocument",
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
    "Role",
    "Store",
    "ToolCall",
    "TikTokOAuthJob",
    "User",
    "WebhookEvent",
]
