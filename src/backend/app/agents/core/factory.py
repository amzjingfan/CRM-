"""构建可复用的模型、向量化和营销服务；动态 Agent 在各子模块组合。"""

from dataclasses import dataclass

from app.agents.core.generation import StructuredGenerationService
from app.agents.core.marketing_generation import MarketingCopyService
from app.agents.core.providers.deepseek_provider import DeepSeekProvider
from app.agents.core.providers.factory import build_provider_pair
from app.agents.core.reply_safety import ReplySafetyPolicy
from app.agents.rag.chunking import FaqTokenChunker
from app.agents.rag.embeddings import EmbeddingService, LocalBgeEmbeddingProvider, build_embedding_provider
from app.agents.rag.retrieval_models import LocalRetrievalModelClient, RerankingService
from app.agents.rag.vectorization import KnowledgeVectorizationService
from app.knowledge_base.vector_port import SqlAlchemyKnowledgeVectorPort
from app.shared.config.settings import Settings


@dataclass(slots=True)
class SharedAgentRuntime:
    """仅复用单进程 HTTP 客户端；数据库会话和店铺查询仍逐请求创建。"""

    primary_provider: DeepSeekProvider
    embedding_service: EmbeddingService
    reranking_service: RerankingService
    retrieval_client: LocalRetrievalModelClient

    async def aclose(self) -> None:
        """应用退出时释放两个连接池。"""
        try:
            await self.primary_provider.aclose()
        finally:
            await self.retrieval_client.aclose()


def build_shared_agent_runtime(settings: Settings) -> SharedAgentRuntime | None:
    """只在 G5 的 DeepSeek + 本地 BGE 配置下构建进程级连接池。"""
    if not (
        (settings.llm_enabled or settings.agent_debug_enabled)
        and settings.embedding_enabled
        and settings.llm_primary_provider == "deepseek"
        and settings.embedding_provider == "local_bge"
        and not (settings.llm_fallback_provider and settings.llm_fallback_model)
    ):
        return None
    if settings.deepseek_api_key is None or settings.retrieval_model_service_token is None:
        raise ValueError("G5 模型客户端配置不完整")
    provider = DeepSeekProvider(
        api_key=settings.deepseek_api_key.get_secret_value(),
        model_name=settings.llm_primary_model or "",
        base_url=settings.deepseek_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        thinking_enabled=settings.deepseek_thinking_enabled,
    )
    retrieval_client = LocalRetrievalModelClient(
        base_url=settings.retrieval_model_service_url,
        token=settings.retrieval_model_service_token.get_secret_value(),
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    return SharedAgentRuntime(
        primary_provider=provider,
        embedding_service=EmbeddingService(
            LocalBgeEmbeddingProvider(
                client=retrieval_client,
                model_name=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
            ),
            max_attempts=settings.embedding_max_attempts,
            batch_size=settings.embedding_batch_size,
        ),
        reranking_service=RerankingService(retrieval_client, max_attempts=settings.reranker_max_attempts),
        retrieval_client=retrieval_client,
    )


def build_embedding_service(settings: Settings) -> EmbeddingService:
    """从类型化配置构建共享 Embedding 服务。"""
    return EmbeddingService(
        build_embedding_provider(settings),
        max_attempts=settings.embedding_max_attempts,
        batch_size=settings.embedding_batch_size,
    )


def build_reranking_service(settings: Settings) -> RerankingService:
    """构建与 Embedding 共用单实例服务地址的 Cross-Encoder 客户端。"""
    if settings.retrieval_model_service_token is None:
        raise ValueError("未配置内部检索模型服务令牌")
    client = LocalRetrievalModelClient(
        base_url=settings.retrieval_model_service_url,
        token=settings.retrieval_model_service_token.get_secret_value(),
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    return RerankingService(client, max_attempts=settings.reranker_max_attempts)


def build_knowledge_vectorization_service(settings: Settings) -> KnowledgeVectorizationService:
    """构建 jobs Worker 使用的 FAQ 向量化服务。"""
    return KnowledgeVectorizationService(
        vector_port=SqlAlchemyKnowledgeVectorPort(),
        embedding_service=build_embedding_service(settings),
        chunker=FaqTokenChunker(
            model_name=settings.embedding_model,
            max_tokens=800,
            overlap_tokens=80,
        ),
        claim_limit=10,
    )


def build_marketing_copy_service(settings: Settings) -> MarketingCopyService:
    """构建 Jobs Worker 使用的营销文案服务；该服务没有发送权限。"""
    primary_provider, fallback_provider = build_provider_pair(settings)
    return MarketingCopyService(
        StructuredGenerationService(primary_provider, fallback_provider, max_attempts=2),
        ReplySafetyPolicy(),
    )
