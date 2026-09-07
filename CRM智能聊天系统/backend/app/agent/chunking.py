"""把 FAQ 问答对切分为保留问题语义的 Token 片段。"""

from dataclasses import dataclass
from typing import Protocol

import tiktoken


class TokenEncoding(Protocol):
    """隔离具体 tokenizer，便于确定性测试和模型升级。"""

    def encode(self, text: str) -> list[int]:
        """把文本编码为 Token ID。"""
        ...

    def decode(self, tokens: list[int]) -> str:
        """把 Token ID 还原为文本。"""
        ...


@dataclass(frozen=True, slots=True)
class FaqTextChunk:
    """尚未生成向量的 FAQ 文本片段。"""

    chunk_index: int
    content: str
    token_count: int


class FaqTokenChunker:
    """按 Token 上限切分答案，并为每片重复问题前缀。"""

    def __init__(
        self,
        *,
        model_name: str,
        max_tokens: int = 800,
        overlap_tokens: int = 80,
        encoding: TokenEncoding | None = None,
    ) -> None:
        """创建切分器并验证窗口不会产生零步长或无限循环。"""
        if max_tokens < 32:
            raise ValueError("FAQ 片段 Token 上限不能小于 32")
        if overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("FAQ 重叠 Token 必须小于片段 Token 上限")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.encoding = encoding or self._load_encoding(model_name)

    def split(self, question: str, answer: str) -> list[FaqTextChunk]:
        """切分 FAQ；每个片段都带问题，避免单独召回时语义残缺。"""
        normalized_question = question.strip()
        normalized_answer = answer.strip()
        if not normalized_question or not normalized_answer:
            raise ValueError("问题和答案不能为空")

        prefix = f"问题：{normalized_question}\n答案："
        prefix_tokens = self.encoding.encode(prefix)
        if len(prefix_tokens) >= self.max_tokens:
            raise ValueError("FAQ 问题过长，无法在片段预算内保留问题前缀")
        answer_tokens = self.encoding.encode(normalized_answer)
        answer_budget = self.max_tokens - len(prefix_tokens)
        # 重叠只作用于答案部分；问题前缀已天然在所有片段重复。
        effective_overlap = min(self.overlap_tokens, max(0, answer_budget - 1))
        step = answer_budget - effective_overlap
        chunks: list[FaqTextChunk] = []
        offset = 0
        while offset < len(answer_tokens):
            answer_slice = answer_tokens[offset : offset + answer_budget]
            content = f"{prefix}{self.encoding.decode(answer_slice)}"
            token_count = len(self.encoding.encode(content))
            chunks.append(FaqTextChunk(chunk_index=len(chunks), content=content, token_count=token_count))
            if offset + answer_budget >= len(answer_tokens):
                break
            offset += step
        return chunks

    @staticmethod
    def _load_encoding(model_name: str) -> TokenEncoding:
        """优先使用模型编码，未知模型回退到稳定的 cl100k_base。"""
        try:
            return tiktoken.encoding_for_model(model_name)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")
