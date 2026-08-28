from __future__ import annotations

import hashlib
import math
from array import array
from collections.abc import Iterable
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from app.core.config import get_settings


class EmbeddingProvider(Protocol):
    name: str
    model: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _normalise(vector: Iterable[float]) -> list[float]:
    values = [float(item) for item in vector]
    norm = math.sqrt(sum(item * item for item in values))
    if norm == 0:
        return values
    return [item / norm for item in values]


class FastEmbedProvider:
    name = "fastembed"

    def __init__(self, model: str, cache_dir: str) -> None:
        module = import_module("fastembed")
        text_embedding = cast(Any, module).TextEmbedding
        self.model = model
        local_model_dir = Path(cache_dir) / f"fast-{model.split('/')[-1]}"
        kwargs = {"specific_model_path": str(local_model_dir)} if local_model_dir.is_dir() else {}
        self._client = text_embedding(model_name=model, cache_dir=cache_dir, **kwargs)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_normalise(vector) for vector in self._client.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vectors = list(self._client.query_embed(text))
        if not vectors:
            raise RuntimeError("本地嵌入模型未返回查询向量")
        return _normalise(vectors[0])


class HashEmbeddingProvider:
    """测试与离线降级使用；正式导入默认使用本地 FastEmbed。"""

    name = "hash"

    def __init__(self, dimensions: int = 128) -> None:
        self.model = f"deterministic-hash-{dimensions}"
        self._dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        compact = "".join(text.lower().split())
        tokens = [compact[index : index + 2] for index in range(max(len(compact) - 1, 1))]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            slot = int.from_bytes(digest[:4], "little") % self._dimensions
            vector[slot] += 1.0 if digest[4] % 2 == 0 else -1.0
        return _normalise(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.rag_embedding_provider == "hash":
        return HashEmbeddingProvider()
    if settings.rag_embedding_provider == "fastembed":
        settings.rag_embedding_cache_dir.mkdir(parents=True, exist_ok=True)
        return FastEmbedProvider(
            settings.rag_embedding_model,
            str(settings.rag_embedding_cache_dir),
        )
    raise ValueError(f"不支持的本地嵌入提供商：{settings.rag_embedding_provider}")


def vector_to_blob(vector: list[float]) -> bytes:
    values = array("f", vector)
    return values.tobytes()


def blob_to_vector(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return list(values)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    return sum(a * b for a, b in zip(left, right, strict=True))
