from __future__ import annotations

import json
import math
import re
from collections import Counter, OrderedDict, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from threading import RLock
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import get_embedding_provider


@dataclass(frozen=True)
class KnowledgeHit:
    document: KnowledgeDocument | _IndexedDocument
    chunk: KnowledgeChunk | _IndexedChunk | None
    score: float
    retrieval_method: str
    keyword_rank: int | None = None
    vector_rank: int | None = None
    vector_score: float | None = None

    @property
    def content(self) -> str:
        return self.chunk.content if self.chunk is not None else self.document.content

    @property
    def heading(self) -> str | None:
        return self.chunk.heading if self.chunk is not None else None


@dataclass(frozen=True)
class _KnowledgeIndex:
    fingerprint: tuple[Any, ...]
    chunks: tuple[_IndexedChunk, ...]
    documents: dict[str, _IndexedDocument]
    term_postings: dict[str, tuple[tuple[int, int], ...]]
    token_lengths: tuple[int, ...]
    average_length: float
    chunks_by_id: dict[str, _IndexedChunk]
    embedding_chunk_ids: tuple[str, ...]
    embedding_matrix: Any | None


@dataclass(frozen=True, slots=True)
class _IndexedDocument:
    id: str
    title: str
    source_url: str | None
    citation_label: str
    license_note: str
    content: str


@dataclass(frozen=True, slots=True)
class _IndexedChunk:
    id: str
    document_id: str
    heading: str | None
    content: str
    metadata_json: str


_INDEX_CACHE: OrderedDict[tuple[str, str, str], _KnowledgeIndex] = OrderedDict()
_INDEX_CACHE_LOCK = RLock()


def _tokenize(text: str) -> tuple[str, ...]:
    chinese_sequences = re.findall(r"[\u4e00-\u9fff]+", text)
    bigrams = [
        sequence[index : index + 2]
        for sequence in chinese_sequences
        for index in range(max(len(sequence) - 1, 0))
    ]
    short_phrases = [sequence for sequence in chinese_sequences if 2 <= len(sequence) <= 8]
    latin = re.findall(r"[a-zA-Z0-9_]{2,32}", text.lower())
    return tuple(short_phrases + bigrams + latin)


def _version_filter(column: Any, version_id: str | None) -> Any:
    return True if version_id is None else or_(column == version_id, column.is_(None))


def _index_fingerprint(db: Session, persona_id: str, version_id: str | None) -> tuple[Any, ...]:
    chunk_count, chunk_updated = db.execute(
        select(func.count(), func.max(KnowledgeChunk.updated_at)).where(
            KnowledgeChunk.persona_id == persona_id,
            _version_filter(KnowledgeChunk.persona_version_id, version_id),
            KnowledgeChunk.enabled.is_(True),
        )
    ).one()
    document_count, document_updated = db.execute(
        select(func.count(), func.max(KnowledgeDocument.updated_at)).where(
            KnowledgeDocument.persona_id == persona_id,
            _version_filter(KnowledgeDocument.persona_version_id, version_id),
            KnowledgeDocument.enabled.is_(True),
        )
    ).one()
    return chunk_count, chunk_updated, document_count, document_updated


def _build_index(
    db: Session,
    persona_id: str,
    version_id: str | None,
    fingerprint: tuple[Any, ...],
) -> _KnowledgeIndex:
    chunk_rows = db.execute(
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.document_id,
            KnowledgeChunk.heading,
            KnowledgeChunk.content,
            KnowledgeChunk.metadata_json,
            KnowledgeChunk.embedding_model,
            KnowledgeChunk.embedding_dim,
            KnowledgeChunk.embedding_blob,
        ).where(
            KnowledgeChunk.persona_id == persona_id,
            _version_filter(KnowledgeChunk.persona_version_id, version_id),
            KnowledgeChunk.enabled.is_(True),
        )
    ).all()
    chunks = tuple(
        _IndexedChunk(
            id=row.id,
            document_id=row.document_id,
            heading=row.heading,
            content=row.content,
            metadata_json=row.metadata_json,
        )
        for row in chunk_rows
    )
    documents = {
        row.id: _IndexedDocument(
            id=row.id,
            title=row.title,
            source_url=row.source_url,
            citation_label=row.citation_label,
            license_note=row.license_note,
            content=row.content,
        )
        for row in db.execute(
            select(
                KnowledgeDocument.id,
                KnowledgeDocument.title,
                KnowledgeDocument.source_url,
                KnowledgeDocument.citation_label,
                KnowledgeDocument.license_note,
                KnowledgeDocument.content,
            ).where(
                KnowledgeDocument.persona_id == persona_id,
                _version_filter(KnowledgeDocument.persona_version_id, version_id),
                KnowledgeDocument.enabled.is_(True),
            )
        )
    }
    postings: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)
    token_lengths: list[int] = []
    for chunk_index, chunk in enumerate(chunks):
        frequencies = Counter(_tokenize(f"{chunk.heading or ''} {chunk.content}"))
        token_lengths.append(sum(frequencies.values()))
        for term, count in frequencies.items():
            postings[term].append((chunk_index, count))
    average_length = sum(token_lengths) / len(token_lengths) if token_lengths else 0.0

    embedding_chunk_ids: list[str] = []
    embedding_rows: list[Any] = []
    settings = get_settings()
    if settings.rag_embedding_enabled:
        try:
            import numpy as np

            provider = get_embedding_provider()
            for chunk, row in zip(chunks, chunk_rows, strict=True):
                if (
                    row.embedding_blob is None
                    or row.embedding_model != provider.model
                    or not row.embedding_dim
                ):
                    continue
                vector = np.frombuffer(row.embedding_blob, dtype=np.float32)
                if vector.size != row.embedding_dim:
                    continue
                embedding_chunk_ids.append(chunk.id)
                embedding_rows.append(vector)
        except Exception:
            embedding_chunk_ids = []
            embedding_rows = []

    embedding_matrix = (
        np.ascontiguousarray(np.vstack(embedding_rows), dtype=np.float32)
        if embedding_rows
        else None
    )
    return _KnowledgeIndex(
        fingerprint=fingerprint,
        chunks=chunks,
        documents=documents,
        term_postings={term: tuple(rows) for term, rows in postings.items()},
        token_lengths=tuple(token_lengths),
        average_length=average_length,
        chunks_by_id={chunk.id: chunk for chunk in chunks},
        embedding_chunk_ids=tuple(embedding_chunk_ids),
        embedding_matrix=embedding_matrix,
    )


def _get_index(db: Session, persona_id: str, version_id: str | None = None) -> _KnowledgeIndex:
    cache_key = (str(db.get_bind().engine.url), persona_id, version_id or "current")
    fingerprint = _index_fingerprint(db, persona_id, version_id)
    with _INDEX_CACHE_LOCK:
        cached = _INDEX_CACHE.get(cache_key)
        if cached is not None and cached.fingerprint == fingerprint:
            _INDEX_CACHE.move_to_end(cache_key)
            return cached
        # Evict before constructing another dense matrix.  On a 512 MB instance,
        # temporarily holding the old cache plus the new index can be enough to OOM.
        _INDEX_CACHE.pop(cache_key, None)
        max_personas = max(get_settings().rag_index_cache_personas, 1)
        while len(_INDEX_CACHE) >= max_personas:
            _INDEX_CACHE.popitem(last=False)
    index = _build_index(db, persona_id, version_id, fingerprint)
    with _INDEX_CACHE_LOCK:
        _INDEX_CACHE[cache_key] = index
        _INDEX_CACHE.move_to_end(cache_key)
        while len(_INDEX_CACHE) > max_personas:
            _INDEX_CACHE.popitem(last=False)
    return index


def _bm25_scores(query: str, index: _KnowledgeIndex) -> dict[str, float]:
    query_terms = list(dict.fromkeys(_tokenize(query)))
    if not query_terms or not index.chunks:
        return {}
    k1 = 1.5
    b = 0.75
    indexed_scores: defaultdict[int, float] = defaultdict(float)
    for term in query_terms:
        term_rows = index.term_postings.get(term, ())
        if not term_rows:
            continue
        inverse_frequency = math.log(
            1 + (len(index.chunks) - len(term_rows) + 0.5) / (len(term_rows) + 0.5)
        )
        for chunk_index, count in term_rows:
            length_ratio = index.token_lengths[chunk_index] / max(index.average_length, 1.0)
            indexed_scores[chunk_index] += inverse_frequency * (
                count * (k1 + 1) / (count + k1 * (1 - b + b * length_ratio))
            )
    return {
        index.chunks[chunk_index].id: score
        for chunk_index, score in indexed_scores.items()
        if score > 0
    }


def _rank_dense(query: str, index: _KnowledgeIndex) -> list[tuple[str, float]]:
    import numpy as np

    settings = get_settings()
    matrix = index.embedding_matrix
    if not settings.rag_embedding_enabled or matrix is None or matrix.size == 0:
        return []
    provider = get_embedding_provider()
    query_vector = np.asarray(provider.embed_query(query), dtype=np.float32)
    if matrix.shape[1] != query_vector.size:
        return []
    scores = matrix @ query_vector
    candidate_count = min(settings.rag_vector_candidates, scores.size)
    if candidate_count <= 0:
        return []
    indexes = np.argpartition(scores, -candidate_count)[-candidate_count:]
    ranked_indexes = indexes[np.argsort(scores[indexes])[::-1]]
    return [
        (index.embedding_chunk_ids[int(row)], float(scores[int(row)])) for row in ranked_indexes
    ]


def _chunk_metadata(chunk: _IndexedChunk) -> dict[str, Any]:
    try:
        value = json.loads(chunk.metadata_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _year_set(value: str) -> set[int]:
    return {int(year) for year in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", value)}


def _rerank_score(query: str, chunk: _IndexedChunk, fused_score: float) -> float:
    terms = set(_tokenize(query))
    content_terms = set(_tokenize(f"{chunk.heading or ''} {chunk.content}"))
    coverage = len(terms & content_terms) / max(len(terms), 1)
    phrase_bonus = 0.008 if len(query) >= 4 and query.strip() in chunk.content else 0.0
    quality = int(_chunk_metadata(chunk).get("quality_score", 0) or 0) / 100
    return fused_score + coverage * 0.025 + phrase_bonus + quality * 0.004


def _legacy_retrieval(
    documents: Iterable[KnowledgeDocument | _IndexedDocument], query: str, limit: int
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
    db: Session,
    persona_id: str,
    query: str,
    limit: int | None = None,
    *,
    version_id: str | None = None,
) -> list[KnowledgeHit]:
    settings = get_settings()
    final_limit = limit or settings.rag_final_limit
    index = _get_index(db, persona_id, version_id)
    if not index.chunks:
        return _legacy_retrieval(list(index.documents.values()), query, final_limit)

    keyword_scores = _bm25_scores(query, index)
    keyword_ranked = sorted(keyword_scores.items(), key=lambda item: item[1], reverse=True)[
        : settings.rag_keyword_candidates
    ]
    try:
        vector_ranked = _rank_dense(query, index)
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

    vector_scores = dict(vector_ranked)
    query_years = _year_set(query)
    explicitly_mismatched: set[str] = set()
    matching_years: set[str] = set()
    if query_years:
        for chunk_id in fused:
            metadata = _chunk_metadata(index.chunks_by_id[chunk_id])
            chunk_years = _year_set(str(metadata.get("time_range", "")))
            if chunk_years & query_years:
                matching_years.add(chunk_id)
            elif chunk_years:
                explicitly_mismatched.add(chunk_id)
    candidate_ids = [
        chunk_id
        for chunk_id in fused
        if not matching_years or chunk_id not in explicitly_mismatched
    ]
    ranked_ids = sorted(
        candidate_ids,
        key=lambda chunk_id: _rerank_score(
            query,
            index.chunks_by_id[chunk_id],
            fused[chunk_id],
        ),
        reverse=True,
    )
    hits: list[KnowledgeHit] = []
    per_document: Counter[str] = Counter()
    # Studio users commonly upload one consolidated export. Keeping the global
    # two-chunk diversity cap in that case silently discards half of the evidence
    # budget and hurts recall for facts located later in a long transcript.
    per_document_limit = final_limit if len(index.documents) == 1 else 2
    for chunk_id in ranked_ids:
        chunk = index.chunks_by_id[chunk_id]
        document = index.documents.get(chunk.document_id)
        if document is None or per_document[document.id] >= per_document_limit:
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
                vector_score=vector_scores.get(chunk_id),
            )
        )
        per_document[document.id] += 1
        if len(hits) >= final_limit:
            break
    return hits
