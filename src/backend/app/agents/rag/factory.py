"""复用现有文件向量检索端口，始终由调用方传入非空绑定文件范围。"""

from app.agents.core.factory import (
    SharedAgentRuntime,
    build_embedding_service,
    build_reranking_service,
)
from app.agents.rag.search import RagRetrievalService
from app.knowledge_base.vector_port import SqlAlchemyKnowledgeSearchPort
from app.shared.config.settings import Settings
from app.shared.database.session import session_factory


def build_bound_file_rag(settings: Settings, runtime: SharedAgentRuntime | None) -> RagRetrievalService:
    return RagRetrievalService(
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
