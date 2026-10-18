"""构建内部 FAQ Agent 和向量化服务，不暴露新的 HTTP 路由。"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chunking import FaqTokenChunker
from app.agent.embeddings import EmbeddingService, LocalBgeEmbeddingProvider, build_embedding_provider
from app.agent.generation import StructuredGenerationService
from app.agent.marketing_generation import MarketingCopyService
from app.agent.providers.deepseek_provider import DeepSeekProvider
from app.agent.providers.factory import build_provider_pair
from app.agent.rag import RagRetrievalService
from app.agent.reply_safety import ReplySafetyPolicy
from app.agent.repository import SqlAlchemyAgentRunRecorder
from app.agent.retrieval_models import LocalRetrievalModelClient, RerankingService
from app.agent.service import IntentClassificationService
from app.agent.tool_execution import AgentToolService
from app.agent.translation import TranslationService
from app.agent.vectorization import KnowledgeVectorizationService
from app.agent.workflow import AgentWorkflowService
from app.knowledge_base.vector_port import SqlAlchemyKnowledgeSearchPort, SqlAlchemyKnowledgeVectorPort
from app.shared.config.settings import Settings
from app.shared.database.session import session_factory
from app.tools.executor import SqlAlchemyToolExecutor


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
        settings.llm_enabled
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


def build_agent_workflow(
    session: AsyncSession, settings: Settings, runtime: SharedAgentRuntime | None = None
) -> AgentWorkflowService:
    """构建全栈内部服务可调用的 FAQ Agent，不执行平台发送。"""
    primary_provider, fallback_provider = (
        (runtime.primary_provider, None) if runtime is not None else build_provider_pair(settings)
    )
    recorder = SqlAlchemyAgentRunRecorder(session)
    classifier = IntentClassificationService(
        primary_provider,
        fallback_provider,
        recorder,
        max_attempts=settings.llm_max_attempts,
        max_output_tokens=settings.llm_max_output_tokens,
    )
    rag_service = RagRetrievalService(
        embedding_service=runtime.embedding_service if runtime is not None else build_embedding_service(settings),
        search_port=SqlAlchemyKnowledgeSearchPort(),
        reranking_service=runtime.reranking_service if runtime is not None else build_reranking_service(settings),
        dense_top_k=settings.rag_dense_top_k,
        lexical_top_k=settings.rag_lexical_top_k,
        candidate_top_k=settings.rag_candidate_top_k,
        final_top_k=settings.rag_top_k,
        rrf_k=settings.rag_rrf_k,
        min_dense_score=settings.rag_min_score,
        min_lexical_score=settings.rag_min_lexical_score,
        max_context_tokens=settings.rag_max_context_tokens,
        search_session_factory=session_factory,
    )
    generator = StructuredGenerationService(primary_provider, fallback_provider, max_attempts=2)
    return AgentWorkflowService(
        classifier=classifier,
        rag_service=rag_service,
        generator=generator,
        run_recorder=recorder,
        tool_service=AgentToolService(SqlAlchemyToolExecutor(session)),
        # 翻译会额外消耗一次模型调用，默认不进入 SSE 关键路径。
        # 只有显式启用后才返回与触发消息关联的双语结果。
        translation_service=TranslationService(generator) if settings.ai_translation_enabled else None,
        reply_safety_policy=ReplySafetyPolicy(),
        auto_reply_threshold=settings.agent_auto_reply_threshold,
        human_review_threshold=settings.agent_human_review_threshold,
        # G5 使用已有的分类与店铺 FAQ 检索并行路径；草稿仍经独立安全复核。
        combined_faq_enabled=False,
        # 当前版本的单条已审批政策 FAQ 使用原文草稿和独立并行复核。
        trusted_faq_enabled=True,
    )
