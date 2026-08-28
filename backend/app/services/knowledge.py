from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import blob_to_vector, cosine_similarity, get_embedding_provider


@dataclass(frozen=True)
class KnowledgeHit:
    document: KnowledgeDocument
    chunk: KnowledgeChunk | None
    score: float
    retrieval_method: str
    keyword_rank: int | None = None
    vector_rank: int | None = None

    @property
    def content(self) -> str:
        return self.chunk.content if self.chunk is not None else self.document.content

    @property
    def heading(self) -> str | None:
        return self.chunk.heading if self.chunk is not None else None


@lru_cache(maxsize=20_000)
def _tokenize_cached(text: str) -> tuple[str, ...]:
    jieba = cast(Any, import_module("jieba"))
    words = [
        token.strip().lower()
        for token in jieba.cut_for_search(text)
        if len(token.strip()) >= 2
    ]
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    bigrams = [chinese[index : index + 2] for index in range(max(len(chinese) - 1, 0))]
    latin = re.findall(r"[a-zA-Z0-9_]{2,32}", text.lower())
    return tuple(words + bigrams + latin)


def _tokenize(text: str) -> list[str]:
    return list(_tokenize_cached(text))


def _bm25_scores(query: str, chunks: list[KnowledgeChunk]) -> dict[str, float]:
    query_terms = list(dict.fromkeys(_tokenize(query)))
    if not query_terms or not chunks:
        return {}
    tokenised = [_tokenize(f"{chunk.heading or ''} {chunk.content}") for chunk in chunks]
    frequencies = [Counter(tokens) for tokens in tokenised]
    document_frequency = Counter(
        term for terms in tokenised for term in set(terms) if term in query_terms
    )
    average_length = sum(len(tokens) for tokens in tokenised) / max(len(tokenised), 1)
    k1 = 1.5
    b = 0.75
    scores: dict[str, float] = {}
    for chunk, terms, frequency in zip(chunks, tokenised, frequencies, strict=True):
        score = 0.0
        length_ratio = len(terms) / max(average_length, 1.0)
        for term in query_terms:
            count = frequency.get(term, 0)
            if count == 0:
                continue
            df = document_frequency.get(term, 0)
            inverse_frequency = math.log(1 + (len(chunks) - df + 0.5) / (df + 0.5))
            score += inverse_frequency * (
                count * (k1 + 1) / (count + k1 * (1 - b + b * length_ratio))
            )
        if score > 0:
            scores[chunk.id] = score
    return scores


def _rank_dense(query: str, chunks: list[KnowledgeChunk]) -> list[tuple[str, float]]:
    settings = get_settings()
    if not settings.rag_embedding_enabled:
        return []
    provider = get_embedding_provider()
    query_vector = provider.embed_query(query)
    scored = []
    for chunk in chunks:
        if (
            chunk.embedding_blob is None
            or chunk.embedding_model != provider.model
            or chunk.embedding_dim != len(query_vector)
        ):
            continue
        score = cosine_similarity(query_vector, blob_to_vector(chunk.embedding_blob))
        scored.append((chunk.id, score))
    return sorted(scored, key=lambda item: item[1], reverse=True)[
        : settings.rag_vector_candidates
    ]


def _legacy_retrieval(
    documents: list[KnowledgeDocument], query: str, limit: int
) -> list[KnowledgeHit]:
    terms = _tokenize(query)
    ranked = []
    for document in documents:
        haystack = f"{document.title} {document.content}".lower()
        score = float(sum(1 for term in set(terms) if term in haystack))
        if score > 0:
            ranked.append(KnowledgeHit(document, None, score, "legacy_keyword"))
    return sorted(ranked, key=lambda hit: hit.score, reverse=True)[:limit]


def retrieve_knowledge(
    db: Session, persona_id: str, query: str, limit: int | None = None
) -> list[KnowledgeHit]:
    settings = get_settings()
    final_limit = limit or settings.rag_final_limit
    chunks = list(
        db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.persona_id == persona_id,
                KnowledgeChunk.enabled.is_(True),
            )
        )
    )
    documents = {
        document.id: document
        for document in db.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.persona_id == persona_id,
                KnowledgeDocument.enabled.is_(True),
            )
        )
    }
    if not chunks:
        return _legacy_retrieval(list(documents.values()), query, final_limit)

    keyword_scores = _bm25_scores(query, chunks)
    keyword_ranked = sorted(
        keyword_scores.items(), key=lambda item: item[1], reverse=True
    )[: settings.rag_keyword_candidates]
    try:
        vector_ranked = _rank_dense(query, chunks)
    except Exception:
        # 本地模型缺失或损坏时保留 BM25，可见的检索模式会变为 keyword。
        vector_ranked = []

    fused: dict[str, float] = {}
    keyword_ranks: dict[str, int] = {}
    vector_ranks: dict[str, int] = {}
    rrf_k = 60
    for rank, (chunk_id, _score) in enumerate(keyword_ranked, start=1):
        keyword_ranks[chunk_id] = rank
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, (chunk_id, _score) in enumerate(vector_ranked, start=1):
        vector_ranks[chunk_id] = rank
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.2 / (rrf_k + rank)

    by_id = {chunk.id: chunk for chunk in chunks}
    ranked_ids = sorted(fused, key=fused.__getitem__, reverse=True)
    hits: list[KnowledgeHit] = []
    per_document: Counter[str] = Counter()
    for chunk_id in ranked_ids:
        chunk = by_id[chunk_id]
        document = documents.get(chunk.document_id)
        if document is None or per_document[document.id] >= 2:
            continue
        keyword_rank = keyword_ranks.get(chunk_id)
        vector_rank = vector_ranks.get(chunk_id)
        method = (
            "hybrid_rrf"
            if keyword_rank is not None and vector_rank is not None
            else "bm25"
            if keyword_rank is not None
            else "vector"
        )
        hits.append(
            KnowledgeHit(
                document=document,
                chunk=chunk,
                score=fused[chunk_id],
                retrieval_method=method,
                keyword_rank=keyword_rank,
                vector_rank=vector_rank,
            )
        )
        per_document[document.id] += 1
        if len(hits) >= final_limit:
            break
    return hits
