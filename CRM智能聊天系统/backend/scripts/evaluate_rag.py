"""使用真实本地 BGE 对版本化 FAQ 执行 Dense 召回和重排序评测。"""

import argparse
import asyncio
import json
import math
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.agent.embeddings import EmbeddingService, build_embedding_provider
from app.agent.factory import build_reranking_service
from app.agent.retrieval_models import RerankCandidate
from app.shared.config.settings import get_settings


class RagEvalCase(BaseModel):
    """单条检索评测样本；无答案样本不携带知识正文。"""

    case_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=4000)
    expected_document_key: str | None = Field(default=None, max_length=100)
    question: str | None = Field(default=None, max_length=4000)
    answer: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def validate_document_pair(self) -> "RagEvalCase":
        """有答案样本必须提供完整 FAQ，无答案样本不得伪造文档。"""
        has_document = self.question is not None or self.answer is not None
        if self.expected_document_key and (not self.question or not self.answer):
            raise ValueError("有目标文档的样本必须提供问题和答案")
        if not self.expected_document_key and has_document:
            raise ValueError("无答案样本不能携带 FAQ 文档")
        return self


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算与 pgvector cosine distance 对应的相似度。"""
    dot = sum(first * second for first, second in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def load_cases(path: Path) -> list[RagEvalCase]:
    """逐行解析 JSONL，任何坏样本都使评测失败关闭。"""
    return [RagEvalCase.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


async def evaluate(dataset: Path, output: Path) -> None:
    """执行真实 Embedding 评测并生成不含查询正文的聚合报告。"""
    settings = get_settings()
    if not settings.llm_live_eval or not settings.embedding_enabled:
        raise RuntimeError("真实 RAG 评测要求 LLM_LIVE_EVAL=true 且 EMBEDDING_ENABLED=true")
    cases = load_cases(dataset)
    documents: dict[str, str] = {}
    for case in cases:
        if case.expected_document_key:
            content = f"问题：{case.question}\n答案：{case.answer}"
            previous = documents.setdefault(case.expected_document_key, content)
            if previous != content:
                raise ValueError(f"文档键 {case.expected_document_key} 对应了不同正文")

    embedding_service = EmbeddingService(
        build_embedding_provider(settings),
        max_attempts=settings.embedding_max_attempts,
        batch_size=settings.embedding_batch_size,
    )
    document_keys = sorted(documents)
    document_result = await embedding_service.embed([documents[key] for key in document_keys])
    query_result = await embedding_service.embed([case.query for case in cases])
    reranking_service = build_reranking_service(settings)
    grounded_total = dense_correct = rerank_correct = 0
    rejection_total = rejection_correct = 0
    citation_legal = citation_total = 0
    reciprocal_rank_total = ndcg_total = 0.0
    reranker_latency_ms = 0
    failures: list[dict[str, object]] = []
    for case, query_vector in zip(cases, query_result.vectors, strict=True):
        dense_ranked = sorted(
            (
                (key, cosine_similarity(query_vector, vector))
                for key, vector in zip(document_keys, document_result.vectors, strict=True)
            ),
            key=lambda item: (-item[1], item[0]),
        )[: settings.rag_dense_top_k]
        reranked_keys: list[str] = []
        if dense_ranked:
            rerank_result = await reranking_service.rerank(
                case.query,
                [RerankCandidate(candidate_id=key, text=documents[key]) for key, _score in dense_ranked],
            )
            reranker_latency_ms += rerank_result.latency_ms
            reranked_keys = [item.candidate_id for item in rerank_result.scores[: settings.rag_top_k]]
        top_dense_score = dense_ranked[0][1] if dense_ranked else 0.0
        accepted = reranked_keys if top_dense_score >= settings.rag_min_score else []
        citation_total += len(accepted)
        citation_legal += sum(key in documents for key in accepted)
        if case.expected_document_key:
            grounded_total += 1
            dense_passed = case.expected_document_key in {key for key, _score in dense_ranked}
            rerank_passed = case.expected_document_key in accepted
            dense_correct += int(dense_passed)
            rerank_correct += int(rerank_passed)
            if case.expected_document_key in reranked_keys:
                rank = reranked_keys.index(case.expected_document_key) + 1
                reciprocal_rank_total += 1 / rank
                ndcg_total += 1 / math.log2(rank + 1)
            passed = dense_passed and rerank_passed
        else:
            rejection_total += 1
            passed = not accepted
            rejection_correct += int(passed)
        if not passed:
            failures.append(
                {
                    "case_id": case.case_id,
                    "expected_document_key": case.expected_document_key,
                    "dense_keys": [key for key, _score in dense_ranked],
                    "reranked_keys": accepted,
                }
            )

    dense_recall_at_20 = dense_correct / grounded_total if grounded_total else 0.0
    rerank_recall_at_5 = rerank_correct / grounded_total if grounded_total else 0.0
    mean_reciprocal_rank = reciprocal_rank_total / grounded_total if grounded_total else 0.0
    ndcg_at_5 = ndcg_total / grounded_total if grounded_total else 0.0
    rejection_rate = rejection_correct / rejection_total if rejection_total else 0.0
    citation_legality = citation_legal / citation_total if citation_total else 1.0
    passed = (
        dense_recall_at_20 >= 0.90
        and rerank_recall_at_5 >= 0.90
        and rejection_rate >= 0.90
        and citation_legality == 1.0
    )
    report = {
        "dataset": dataset.name,
        "provider": document_result.provider,
        "model": document_result.model,
        "grounded_cases": grounded_total,
        "rejection_cases": rejection_total,
        "dense_recall_at_20": round(dense_recall_at_20, 4),
        "rerank_recall_at_5": round(rerank_recall_at_5, 4),
        "mrr": round(mean_reciprocal_rank, 4),
        "ndcg_at_5": round(ndcg_at_5, 4),
        "rejection_rate": round(rejection_rate, 4),
        "citation_legality": round(citation_legality, 4),
        "input_tokens": document_result.input_tokens + query_result.input_tokens,
        "embedding_latency_ms": document_result.latency_ms + query_result.latency_ms,
        "reranker_latency_ms": reranker_latency_ms,
        "failed_case_ids": failures,
        "passed": passed,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not passed:
        raise SystemExit(1)


def main() -> None:
    """解析命令行并运行异步评测。"""
    parser = argparse.ArgumentParser(description="评测 FAQ Dense Recall@20、Rerank Recall@5 和无答案拒判率")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(evaluate(args.dataset, args.output))


if __name__ == "__main__":
    main()
