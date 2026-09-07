"""使用只读本地资产验证 Transformers/BGE 加载、向量化和重排序。"""

import argparse
import json
from pathlib import Path

from app.retrieval_model_service.engine import TransformersBgeEngine


def parse_args() -> argparse.Namespace:
    """解析模型目录和设备，不接受客户输入或远程模型地址。"""
    parser = argparse.ArgumentParser(description="Verify local BGE runtime")
    parser.add_argument("--embedding-path", type=Path, required=True)
    parser.add_argument("--reranker-path", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    return parser.parse_args()


def main() -> None:
    """执行单样本低敏探针，并只输出版本、维度和有限分数。"""
    args = parse_args()
    engine = TransformersBgeEngine(
        embedding_path=args.embedding_path,
        reranker_path=args.reranker_path,
        device=args.device,
        use_fp16=args.device != "cpu",
        embedding_batch_size=1,
        reranker_batch_size=1,
        embedding_max_length=64,
        reranker_max_length=64,
        verify_hashes=False,
    )
    engine.load()
    embedding = engine.embed(["退货政策"])
    reranked = engine.rerank("退货", ["支持按规则申请退货。"])

    import torch
    import transformers

    print(
        json.dumps(
            {
                "transformers": transformers.__version__,
                "torch": torch.__version__,
                "device": engine.device,
                "embedding_count": len(embedding.vectors),
                "embedding_dimensions": len(embedding.vectors[0]),
                "input_tokens": embedding.input_tokens,
                "rerank_count": len(reranked.scores),
                "rerank_score_is_finite": bool(reranked.scores),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
