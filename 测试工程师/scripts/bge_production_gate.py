"""执行本地 BGE 检索质量、阈值和单实例容量生产门禁。

该脚本是测试工程师产物，只通过内部 HTTP 契约访问模型服务，不读取
项目 ``.env``，也不输出 Bearer Token、查询正文、FAQ 正文或完整向量。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class EvalCase:
    """一条不含真实客户数据的版本化 FAQ 评测样本。"""

    case_id: str
    query: str
    expected_document_key: str | None
    question: str | None
    answer: str | None


def load_cases(path: Path) -> list[EvalCase]:
    """严格加载 JSONL，坏样本直接终止评测，防止静默漏测。"""
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            EvalCase(
                case_id=str(payload["case_id"]),
                query=str(payload["query"]),
                expected_document_key=payload.get("expected_document_key"),
                question=payload.get("question"),
                answer=payload.get("answer"),
            )
        )
    return cases


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算与 PostgreSQL pgvector cosine distance 一致的相似度。"""
    dot = sum(first * second for first, second in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


async def post_json(
    client: httpx.AsyncClient,
    token: str,
    path: str,
    payload: dict[str, object],
) -> dict[str, Any]:
    """调用内部模型端点；异常仅包含状态码，不回显响应正文。"""
    response = await client.post(path, json=payload, headers={"Authorization": f"Bearer {token}"})
    if not response.is_success:
        raise RuntimeError(f"模型服务返回 HTTP {response.status_code}")
    return dict(response.json())


async def evaluate_quality(
    client: httpx.AsyncClient,
    token: str,
    dataset: Path,
    configured_threshold: float,
) -> dict[str, object]:
    """一次真实推理完成召回、重排和阈值网格评测。"""
    cases = load_cases(dataset)
    documents: dict[str, str] = {}
    for case in cases:
        if case.expected_document_key is None:
            continue
        if not case.question or not case.answer:
            raise ValueError(f"{case.case_id} 缺少目标 FAQ")
        content = f"问题：{case.question}\n答案：{case.answer}"
        previous = documents.setdefault(case.expected_document_key, content)
        if previous != content:
            raise ValueError(f"文档键 {case.expected_document_key} 对应多个正文")

    document_keys = sorted(documents)
    document_response = await post_json(
        client,
        token,
        "/internal/v1/embeddings",
        {"texts": [documents[key] for key in document_keys]},
    )
    query_response = await post_json(
        client,
        token,
        "/internal/v1/embeddings",
        {"texts": [case.query for case in cases]},
    )
    document_vectors = document_response["vectors"]
    query_vectors = query_response["vectors"]
    if any(len(vector) != 1024 for vector in [*document_vectors, *query_vectors]):
        raise RuntimeError("真实评测收到非 1024 维向量")

    observations: list[dict[str, object]] = []
    reciprocal_rank_total = 0.0
    ndcg_total = 0.0
    dense_correct = 0
    citation_legal = 0
    citation_total = 0
    reranker_latency_ms = 0
    for case, query_vector in zip(cases, query_vectors, strict=True):
        dense_ranked = sorted(
            (
                (key, cosine_similarity(query_vector, document_vector))
                for key, document_vector in zip(document_keys, document_vectors, strict=True)
            ),
            key=lambda item: (-item[1], item[0]),
        )[:20]
        dense_keys = [key for key, _score in dense_ranked]
        top_dense_score = dense_ranked[0][1] if dense_ranked else 0.0
        rerank_response = await post_json(
            client,
            token,
            "/internal/v1/rerank",
            {
                "query": case.query,
                "candidates": [{"candidate_id": key, "text": documents[key]} for key, _score in dense_ranked],
            },
        )
        reranker_latency_ms += int(rerank_response["latency_ms"])
        reranked = sorted(
            rerank_response["scores"],
            key=lambda item: (-float(item["score"]), dense_keys.index(str(item["candidate_id"]))),
        )
        reranked_keys = [str(item["candidate_id"]) for item in reranked[:5]]
        citation_total += len(reranked_keys)
        citation_legal += sum(key in documents for key in reranked_keys)
        expected_key = case.expected_document_key
        if expected_key is not None:
            dense_correct += int(expected_key in dense_keys)
            if expected_key in reranked_keys:
                rank = reranked_keys.index(expected_key) + 1
                reciprocal_rank_total += 1 / rank
                ndcg_total += 1 / math.log2(rank + 1)
        observations.append(
            {
                "case_id": case.case_id,
                "expected_document_key": expected_key,
                "top_dense_score": top_dense_score,
                "reranked_keys": reranked_keys,
            }
        )

    grounded = [item for item in observations if item["expected_document_key"] is not None]
    rejected = [item for item in observations if item["expected_document_key"] is None]
    threshold_rows: list[dict[str, object]] = []
    for index in range(30, 91):
        threshold = index / 100
        grounded_correct = sum(
            float(item["top_dense_score"]) >= threshold and item["expected_document_key"] in item["reranked_keys"]
            for item in grounded
        )
        rejection_correct = sum(float(item["top_dense_score"]) < threshold for item in rejected)
        grounded_recall = grounded_correct / len(grounded)
        rejection_rate = rejection_correct / len(rejected)
        threshold_rows.append(
            {
                "threshold": threshold,
                "rerank_recall_at_5": round(grounded_recall, 4),
                "rejection_rate": round(rejection_rate, 4),
                "balanced_score": round((grounded_recall + rejection_rate) / 2, 4),
            }
        )
    eligible = [
        row
        for row in threshold_rows
        if float(row["rerank_recall_at_5"]) >= 0.90 and float(row["rejection_rate"]) >= 0.90
    ]
    recommended = (
        max(
            eligible,
            key=lambda row: (
                float(row["balanced_score"]),
                float(row["rejection_rate"]),
                float(row["rerank_recall_at_5"]),
                -float(row["threshold"]),
            ),
        )
        if eligible
        else None
    )
    configured = min(threshold_rows, key=lambda row: abs(float(row["threshold"]) - configured_threshold))
    recommended_threshold = float(recommended["threshold"]) if recommended else configured_threshold
    failed_grounded = [
        item["case_id"]
        for item in grounded
        if float(item["top_dense_score"]) < recommended_threshold
        or item["expected_document_key"] not in item["reranked_keys"]
    ]
    failed_rejection = [item["case_id"] for item in rejected if float(item["top_dense_score"]) >= recommended_threshold]
    return {
        "dataset": dataset.name,
        "provider": document_response["provider"],
        "embedding_model": document_response["model"],
        "embedding_revision": document_response["revision"],
        "reranker_model": "BAAI/bge-reranker-large",
        "grounded_cases": len(grounded),
        "rejection_cases": len(rejected),
        "dense_recall_at_20": round(dense_correct / len(grounded), 4),
        "rerank_recall_at_5_without_gate": round(
            sum(item["expected_document_key"] in item["reranked_keys"] for item in grounded) / len(grounded),
            4,
        ),
        "mrr": round(reciprocal_rank_total / len(grounded), 4),
        "ndcg_at_5": round(ndcg_total / len(grounded), 4),
        "citation_legality": round(citation_legal / citation_total if citation_total else 1.0, 4),
        "configured_threshold": configured,
        "recommended_threshold": recommended,
        "failed_grounded_case_ids": failed_grounded,
        "failed_rejection_case_ids": failed_rejection,
        "threshold_grid": threshold_rows,
        "embedding_latency_ms": int(document_response["latency_ms"]) + int(query_response["latency_ms"]),
        "reranker_latency_ms": reranker_latency_ms,
        "passed": bool(
            recommended
            and dense_correct / len(grounded) >= 0.90
            and sum(item["expected_document_key"] in item["reranked_keys"] for item in grounded) / len(grounded) >= 0.90
            and citation_legal == citation_total
        ),
    }


def percentile(values: list[float], percent: float) -> float:
    """使用 nearest-rank 计算请求延迟百分位。"""
    ordered = sorted(values)
    index = max(0, math.ceil(percent * len(ordered)) - 1)
    return ordered[index]


def sample_gpu_memory_mb() -> int | None:
    """读取容器可见 GPU 总显存占用，兼容 WDDM 无进程显存明细场景。"""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    values = [int(line.strip()) for line in completed.stdout.splitlines() if line.strip().isdigit()]
    return sum(values) if values else 0


async def run_load_case(
    client: httpx.AsyncClient,
    token: str,
    kind: str,
    concurrency: int,
    sample_gpu: bool,
) -> dict[str, object]:
    """同时发起指定数量请求；显存采样可关闭以避免干扰延迟。"""
    candidates = [
        {"candidate_id": f"candidate-{index}", "text": f"退货政策测试候选 {index}，签收后七天内可申请。"}
        for index in range(20)
    ]

    async def request_once(index: int) -> tuple[bool, float, str | None]:
        started_at = time.perf_counter()
        try:
            if kind == "embedding":
                response = await post_json(
                    client,
                    token,
                    "/internal/v1/embeddings",
                    {"texts": [f"第 {index} 条退货政策并发测试"]},
                )
                valid = len(response["vectors"][0]) == 1024
            else:
                response = await post_json(
                    client,
                    token,
                    "/internal/v1/rerank",
                    {"query": f"第 {index} 条退货政策查询", "candidates": candidates},
                )
                valid = len(response["scores"]) == 20
            return valid, (time.perf_counter() - started_at) * 1000, None if valid else "OUTPUT_INVALID"
        except Exception as error:  # 测试汇总只保留异常类型，不记录服务正文。
            return False, (time.perf_counter() - started_at) * 1000, type(error).__name__

    stop_sampling = asyncio.Event()
    memory_samples: list[int] = []

    async def sample_memory() -> None:
        while not stop_sampling.is_set():
            value = await asyncio.to_thread(sample_gpu_memory_mb)
            if value is not None:
                memory_samples.append(value)
            try:
                await asyncio.wait_for(stop_sampling.wait(), timeout=0.2)
            except TimeoutError:
                continue

    sampler = asyncio.create_task(sample_memory()) if sample_gpu else None
    started_at = time.perf_counter()
    results = await asyncio.gather(*(request_once(index) for index in range(concurrency)))
    elapsed_seconds = time.perf_counter() - started_at
    stop_sampling.set()
    if sampler is not None:
        await sampler
    latencies = [latency for _success, latency, _error in results]
    failures = [error for success, _latency, error in results if not success]
    return {
        "kind": kind,
        "concurrency": concurrency,
        "success_count": concurrency - len(failures),
        "failure_count": len(failures),
        "failure_types": sorted(set(item for item in failures if item)),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "throughput_rps": round(concurrency / elapsed_seconds, 4),
        "latency_average_ms": round(statistics.mean(latencies), 2),
        "latency_p50_ms": round(percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(percentile(latencies, 0.95), 2),
        "latency_p99_ms": round(percentile(latencies, 0.99), 2),
        "latency_max_ms": round(max(latencies), 2),
        "gpu_memory_peak_mb": max(memory_samples) if memory_samples else None,
        "passed": len(failures) == 0 and percentile(latencies, 0.95) < 5000,
    }


async def evaluate_capacity(client: httpx.AsyncClient, token: str, sample_gpu: bool) -> dict[str, object]:
    """执行批量 OOM 门禁和两类 50 并发负载。"""
    await post_json(client, token, "/internal/v1/embeddings", {"texts": ["预热测试"]})
    await post_json(
        client,
        token,
        "/internal/v1/rerank",
        {
            "query": "预热退货政策",
            "candidates": [{"candidate_id": "warmup", "text": "签收后七天内支持退货。"}],
        },
    )
    batch_embedding = await post_json(
        client,
        token,
        "/internal/v1/embeddings",
        {"texts": [f"批量向量化测试 {index}" for index in range(32)]},
    )
    batch_rerank = await post_json(
        client,
        token,
        "/internal/v1/rerank",
        {
            "query": "退货政策",
            "candidates": [{"candidate_id": f"batch-{index}", "text": f"第 {index} 条退货候选"} for index in range(20)],
        },
    )
    embedding_load = await run_load_case(client, token, "embedding", 50, sample_gpu)
    reranker_load = await run_load_case(client, token, "rerank", 50, sample_gpu)
    return {
        "embedding_batch_32": {
            "vectors": len(batch_embedding["vectors"]),
            "dimensions_valid": all(len(vector) == 1024 for vector in batch_embedding["vectors"]),
        },
        "reranker_batch_20": {
            "scores": len(batch_rerank["scores"]),
            "finite": all(math.isfinite(float(item["score"])) for item in batch_rerank["scores"]),
        },
        "embedding_concurrency_50": embedding_load,
        "reranker_concurrency_50": reranker_load,
        "oom_detected": bool(embedding_load["failure_count"] or reranker_load["failure_count"]),
        "passed": bool(
            len(batch_embedding["vectors"]) == 32
            and len(batch_rerank["scores"]) == 20
            and embedding_load["passed"]
            and reranker_load["passed"]
        ),
    }


async def main_async(args: argparse.Namespace) -> None:
    """执行选定门禁并写入不含正文的 JSON 证据。"""
    token = os.environ.get("RETRIEVAL_MODEL_SERVICE_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("测试要求至少 32 字符的临时内部 Token")
    limits = httpx.Limits(max_connections=64, max_keepalive_connections=64)
    timeout = httpx.Timeout(180.0)
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), limits=limits, timeout=timeout) as client:
        report: dict[str, object] = {}
        if args.mode in {"quality", "all"}:
            report["quality"] = await evaluate_quality(
                client,
                token,
                args.dataset,
                args.configured_threshold,
            )
        if args.mode in {"capacity", "all"}:
            report["capacity"] = await evaluate_capacity(client, token, args.sample_gpu)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    """解析测试参数。"""
    parser = argparse.ArgumentParser(description="BGE 真实质量、阈值和容量生产门禁")
    parser.add_argument("--mode", choices=("quality", "capacity", "all"), default="all")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--configured-threshold", type=float, default=0.52)
    parser.add_argument(
        "--sample-gpu",
        action="store_true",
        help="在容器内采集显存；生产门禁建议关闭并由宿主机独立采样，避免干扰延迟。",
    )
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
