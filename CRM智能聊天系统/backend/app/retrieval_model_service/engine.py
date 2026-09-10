"""离线加载 BGE-M3 与 BGE Reranker 的受控推理引擎。"""

import hashlib
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class EngineEmbeddingResult:
    """模型引擎生成的 Dense 向量及输入 Token 数。"""

    vectors: list[list[float]]
    input_tokens: int


@dataclass(frozen=True, slots=True)
class EngineRerankResult:
    """模型引擎按输入顺序返回的未归一化 Cross-Encoder 分数。"""

    scores: list[float]


class RetrievalEngine(Protocol):
    """HTTP 层可使用的最小同步推理契约。"""

    embedding_model: str
    embedding_revision: str
    reranker_model: str
    reranker_revision: str
    dimensions: int
    device: str

    def load(self) -> None:
        """离线加载并校验两套固定模型。"""
        ...

    def embed(self, texts: list[str]) -> EngineEmbeddingResult:
        """生成归一化 Dense 向量。"""
        ...

    def rerank(self, query: str, passages: list[str]) -> EngineRerankResult:
        """为查询与候选对生成原始相关性分数。"""
        ...


class RetrievalEngineError(RuntimeError):
    """不包含正文、向量、路径和底层堆栈的稳定推理错误。"""


class TransformersBgeEngine:
    """使用 Transformers 离线加载固定 BGE 权重的单实例引擎。

    BGE-M3 的 sentence-transformers 配置使用 CLS 池化和 L2 归一化，
    因此这里直接复现该推理规则。Reranker 使用序列分类头的单个 logit，
    原始 logit 只参与排序，不在此处执行 Sigmoid 或业务阈值判断。
    """

    embedding_model = "BAAI/bge-m3"
    embedding_revision = "5617a9f61b028005a4858fdac845db406aefb181"
    reranker_model = "BAAI/bge-reranker-large"
    reranker_revision = "55611d7bca2a7133960a6d3b71e083071bbfc312"
    dimensions = 1024
    _EXPECTED_ASSET_HASHES = {
        "bge-m3/config.json": "26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa",
        "bge-m3/pytorch_model.bin": "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38",
        "bge-m3/tokenizer.json": "21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08",
        "bge-reranker-large/config.json": ("25dda0319f57e9de243c32eb7ecefa0768271afac6b5d8a94ba7f779198ab102"),
        "bge-reranker-large/model.safetensors": ("c5ae4e262c60ed2fb507ec587358285377ec36ee0a2e6da029f0534272b06d36"),
        "bge-reranker-large/tokenizer.json": ("9eb652ac4e40cc093272bbbe0f55d521cf67570060227109b5cdc20945a4489e"),
    }

    def __init__(
        self,
        *,
        embedding_path: Path,
        reranker_path: Path,
        device: str,
        use_fp16: bool,
        embedding_batch_size: int,
        reranker_batch_size: int,
        embedding_max_length: int,
        reranker_max_length: int,
        verify_hashes: bool,
    ) -> None:
        """保存模型运行配置；真正导入 Torch 和加载权重延迟到 load。"""
        self.embedding_path = embedding_path.resolve()
        self.reranker_path = reranker_path.resolve()
        self.requested_device = device.strip().lower()
        self.use_fp16 = use_fp16
        self.embedding_batch_size = embedding_batch_size
        self.reranker_batch_size = reranker_batch_size
        self.embedding_max_length = embedding_max_length
        self.reranker_max_length = reranker_max_length
        self.verify_hashes = verify_hashes
        self.device = "unloaded"
        self._torch: Any = None
        self._embedding_tokenizer: Any = None
        self._embedding_model: Any = None
        self._reranker_tokenizer: Any = None
        self._reranker_model: Any = None
        # 单实例仍限制为一次推理，避免 8 GB 显存下两个大模型并发导致 OOM。
        self._inference_lock = threading.Lock()

    def load(self) -> None:
        """校验资产后以 local_files_only 模式加载，禁止运行时访问模型仓库。"""
        self._verify_assets()
        try:
            import torch
            from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as error:
            raise RetrievalEngineError("MODEL_RUNTIME_DEPENDENCY_MISSING") from error

        if self.requested_device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        elif self.requested_device in {"cpu", "cuda"}:
            self.device = self.requested_device
        else:
            raise RetrievalEngineError("MODEL_DEVICE_INVALID")
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RetrievalEngineError("MODEL_CUDA_UNAVAILABLE")

        dtype = torch.float16 if self.device == "cuda" and self.use_fp16 else torch.float32
        try:
            self._embedding_tokenizer = AutoTokenizer.from_pretrained(
                self.embedding_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            self._embedding_model = AutoModel.from_pretrained(
                self.embedding_path,
                local_files_only=True,
                trust_remote_code=False,
                dtype=dtype,
            ).to(self.device)
            self._embedding_model.eval()
            self._reranker_tokenizer = AutoTokenizer.from_pretrained(
                self.reranker_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            self._reranker_model = AutoModelForSequenceClassification.from_pretrained(
                self.reranker_path,
                local_files_only=True,
                trust_remote_code=False,
                dtype=dtype,
            ).to(self.device)
            self._reranker_model.eval()
            self._torch = torch
        except Exception as error:
            # 上层日志只记录 RetrievalEngineError 类型和稳定错误码，不记录本机路径。
            raise RetrievalEngineError("MODEL_LOAD_FAILED") from error

    def embed(self, texts: list[str]) -> EngineEmbeddingResult:
        """分批执行 CLS 池化与 L2 归一化，并返回 1024 维有限向量。"""
        self._require_loaded()
        vectors: list[list[float]] = []
        input_tokens = 0
        with self._inference_lock, self._torch.inference_mode():
            for offset in range(0, len(texts), self.embedding_batch_size):
                batch = texts[offset : offset + self.embedding_batch_size]
                encoded = self._embedding_tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.embedding_max_length,
                    return_tensors="pt",
                )
                input_tokens += int(encoded["attention_mask"].sum().item())
                encoded = {name: value.to(self.device) for name, value in encoded.items()}
                output = self._embedding_model(**encoded)
                dense = self._torch.nn.functional.normalize(output.last_hidden_state[:, 0], p=2, dim=1)
                vectors.extend(dense.float().cpu().tolist())
        if len(vectors) != len(texts) or any(len(vector) != self.dimensions for vector in vectors):
            raise RetrievalEngineError("EMBEDDING_DIMENSION_INVALID")
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise RetrievalEngineError("EMBEDDING_VALUE_INVALID")
        return EngineEmbeddingResult(vectors=vectors, input_tokens=input_tokens)

    def rerank(self, query: str, passages: list[str]) -> EngineRerankResult:
        """分批计算查询/候选对的原始 logit，输出顺序与候选输入一致。"""
        self._require_loaded()
        scores: list[float] = []
        with self._inference_lock, self._torch.inference_mode():
            for offset in range(0, len(passages), self.reranker_batch_size):
                batch = passages[offset : offset + self.reranker_batch_size]
                encoded = self._reranker_tokenizer(
                    [query] * len(batch),
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.reranker_max_length,
                    return_tensors="pt",
                )
                encoded = {name: value.to(self.device) for name, value in encoded.items()}
                logits = self._reranker_model(**encoded).logits.reshape(-1)
                scores.extend(float(value) for value in logits.float().cpu().tolist())
        if len(scores) != len(passages) or any(not math.isfinite(score) for score in scores):
            raise RetrievalEngineError("RERANK_OUTPUT_INVALID")
        return EngineRerankResult(scores=scores)

    def _require_loaded(self) -> None:
        """防止模型未就绪时以空对象执行推理。"""
        if self._torch is None or self._embedding_model is None or self._reranker_model is None:
            raise RetrievalEngineError("MODEL_NOT_LOADED")

    def _verify_assets(self) -> None:
        """验证固定六文件；启用完整哈希时任何配置、分词器或权重篡改均失败关闭。"""
        model_roots = {
            "bge-m3": self.embedding_path,
            "bge-reranker-large": self.reranker_path,
        }
        expected_hashes: dict[Path, str] = {}
        for relative_path, expected_hash in self._EXPECTED_ASSET_HASHES.items():
            model_name, filename = relative_path.split("/", maxsplit=1)
            expected_hashes[model_roots[model_name] / filename] = expected_hash
        if any(not path.is_file() for path in expected_hashes):
            raise RetrievalEngineError("MODEL_ASSET_MISSING")
        if not self.verify_hashes:
            return
        for path, expected_hash in expected_hashes.items():
            digest = hashlib.sha256()
            with path.open("rb") as file_handle:
                for block in iter(lambda: file_handle.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected_hash:
                raise RetrievalEngineError("MODEL_ASSET_HASH_MISMATCH")
