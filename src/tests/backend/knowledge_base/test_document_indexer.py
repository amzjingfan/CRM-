"""向量输入和批次必须在整个版本中使用同一模型与可完整编码的文本。"""

from types import SimpleNamespace

import pytest

from app.knowledge_base import document_indexer


class CharacterTokenizer:
    def encode(self, value: str) -> list[int]:
        return [ord(char) for char in value]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


@pytest.mark.asyncio
async def test_embedding_revision_change_between_batches_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        document_indexer,
        "get_settings",
        lambda: SimpleNamespace(embedding_batch_size=2, embedding_max_length=8192),
    )

    class ChangingEmbedder:
        def __init__(self) -> None:
            self.calls = 0

        async def embed(self, texts: list[str]) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(
                model="BAAI/bge-m3",
                revision=f"revision-{self.calls}",
                dimensions=1024,
                vectors=[[0.1] * 1024 for _ in texts],
            )

    with pytest.raises(document_indexer.DocumentIndexError, match="EMBEDDING_REVISION_MISMATCH"):
        await document_indexer._embed_texts(ChangingEmbedder(), ["一", "二", "三"])


def test_embedding_input_longer_than_model_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        document_indexer,
        "get_settings",
        lambda: SimpleNamespace(embedding_batch_size=2, embedding_max_length=8),
    )
    with pytest.raises(document_indexer.DocumentIndexError, match="EMBEDDING_INPUT_TOO_LONG"):
        document_indexer._check_embedding_lengths(["1234567"], CharacterTokenizer())
    document_indexer._check_embedding_lengths(["123456"], CharacterTokenizer())
