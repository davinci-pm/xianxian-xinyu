from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument, Persona
from app.services.embeddings import get_embedding_provider, vector_to_blob

FENGGE_SLUG = "fengge-wangmingtianya"
FENGGE_SKILL_NAME = "fengge-wangmingtianya-perspective"
FENGGE_COMMIT = "fdf871015255ef8e568a7a86679fc4b183bce7ba"
FENGGE_FILES = (
    "SKILL.md",
    "references/research/01-public-research.md",
    "references/research/02-dialogue-templates.md",
    "references/research/03-safety-and-boundaries.md",
    "references/research/04-live-clip-quotes.md",
)


@dataclass(frozen=True)
class TextChunk:
    heading: str | None
    content: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class IngestReport:
    persona_slug: str
    documents: int
    chunks: int
    embedded_chunks: int
    embedding_model: str | None


@dataclass(frozen=True)
class BatchIngestReport:
    personas: int
    documents: int
    chunks: int
    embedded_chunks: int
    embedding_model: str | None


def _split_long_text(text: str, limit: int, overlap: int) -> list[tuple[str, int, int]]:
    if len(text) <= limit:
        return [(text, 0, len(text))]
    pieces: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        hard_end = min(start + limit, len(text))
        end = hard_end
        if hard_end < len(text):
            window = text[start:hard_end]
            candidates = [window.rfind(mark) for mark in ("\n\n", "。", "！", "？", "；", "\n")]
            boundary = max(candidates)
            if boundary >= limit // 2:
                marker_length = 2 if window[boundary : boundary + 2] == "\n\n" else 1
                end = start + boundary + marker_length
        piece = text[start:end].strip()
        if piece:
            pieces.append((piece, start, end))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


def chunk_markdown(text: str, limit: int, overlap: int) -> list[TextChunk]:
    if limit < 100 or overlap < 0 or overlap >= limit:
        raise ValueError("RAG 分块参数不合法")
    heading: str | None = None
    section_start = 0
    section_lines: list[str] = []
    chunks: list[TextChunk] = []

    def flush() -> None:
        nonlocal section_start
        section = "\n".join(section_lines).strip()
        if not section:
            return
        for content, local_start, local_end in _split_long_text(section, limit, overlap):
            chunks.append(
                TextChunk(
                    heading=heading,
                    content=content,
                    start_char=section_start + local_start,
                    end_char=section_start + local_end,
                )
            )

    cursor = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line.rstrip("\r\n"))
        if match:
            flush()
            section_lines = []
            heading = match.group(1).strip()[:240]
            section_start = cursor
        section_lines.append(line.rstrip("\r\n"))
        cursor += len(line)
    flush()
    return chunks


def _source_url(source_file: str) -> str:
    path = source_file.replace(" ", "%20")
    return (
        "https://github.com/rottenpen/fengge-wangmingtianya-perspective/blob/"
        f"{FENGGE_COMMIT}/{path}"
    )


def _title(source_file: str) -> str:
    titles = {
        "SKILL.md": "峰哥亡命天涯视角：原版 Skill 说明",
        "references/research/01-public-research.md": "峰哥公开资料研究",
        "references/research/02-dialogue-templates.md": "峰哥对话模板与场景示例",
        "references/research/03-safety-and-boundaries.md": "峰哥视角安全边界",
        "references/research/04-live-clip-quotes.md": "峰哥历史直播切片语录库",
    }
    return titles[source_file]


def _metadata(document: KnowledgeDocument) -> dict[str, Any]:
    try:
        value = json.loads(document.metadata_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def ingest_fengge_corpus(db: Session) -> IngestReport:
    settings = get_settings()
    persona = db.scalar(select(Persona).where(Persona.slug == FENGGE_SLUG))
    if persona is None:
        raise LookupError("未找到峰哥人物数据；请先执行种子数据初始化")
    skill_root = (settings.codex_skill_root / FENGGE_SKILL_NAME).resolve()
    if not skill_root.is_dir():
        raise LookupError(f"未找到已审核的峰哥 Skill：{skill_root}")

    existing_documents = list(
        db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.persona_id == persona.id))
    )
    by_source_file = {
        str(_metadata(document).get("source_file")): document
        for document in existing_documents
        if _metadata(document).get("source_file")
    }
    documents: list[KnowledgeDocument] = []
    for source_file in FENGGE_FILES:
        source_path = (skill_root / source_file).resolve()
        if skill_root not in source_path.parents or not source_path.is_file():
            raise LookupError(f"语料文件不存在：{source_file}")
        content = source_path.read_text(encoding="utf-8")
        document = by_source_file.get(source_file)
        if document is None:
            document = KnowledgeDocument(persona_id=persona.id)
            db.add(document)
        document.title = _title(source_file)
        document.persona_version_id = persona.current_version_id
        document.source_type = "upstream_original_skill"
        document.source_url = _source_url(source_file)
        document.citation_label = f"{_title(source_file)}（GitHub 固定版本）"
        document.license_note = f"MIT；上游提交固定为 {FENGGE_COMMIT}。"
        document.content = content
        document.metadata_json = json.dumps(
            {
                "ingestion": "local_hybrid_rag",
                "source_file": source_file,
                "pinned_commit": FENGGE_COMMIT,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            },
            ensure_ascii=False,
        )
        document.enabled = True
        db.flush()
        documents.append(document)

    provider = get_embedding_provider() if settings.rag_embedding_enabled else None
    total_chunks = 0
    embedded_chunks = 0
    for document in documents:
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        source_meta = _metadata(document)
        chunks = chunk_markdown(
            document.content,
            settings.rag_chunk_chars,
            settings.rag_chunk_overlap_chars,
        )
        vectors = provider.embed_documents([chunk.content for chunk in chunks]) if provider else []
        for index, chunk in enumerate(chunks):
            vector = vectors[index] if vectors else None
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    persona_id=persona.id,
                    persona_version_id=persona.current_version_id,
                    chunk_index=index,
                    heading=chunk.heading,
                    content=chunk.content,
                    content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    citation_label=document.citation_label,
                    source_url=document.source_url,
                    metadata_json=json.dumps(
                        {
                            "source_file": source_meta.get("source_file"),
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                        },
                        ensure_ascii=False,
                    ),
                    embedding_model=provider.model if vector is not None and provider else None,
                    embedding_dim=len(vector) if vector is not None else None,
                    embedding_blob=vector_to_blob(vector) if vector is not None else None,
                    enabled=True,
                )
            )
        total_chunks += len(chunks)
        embedded_chunks += len(vectors)
    db.commit()
    return IngestReport(
        persona_slug=FENGGE_SLUG,
        documents=len(documents),
        chunks=total_chunks,
        embedded_chunks=embedded_chunks,
        embedding_model=provider.model if provider else None,
    )


def ingest_vendored_persona_corpora(db: Session) -> BatchIngestReport:
    settings = get_settings()
    allowlist_path = settings.upstream_skill_root / "ALLOWLIST.yaml"
    if not allowlist_path.is_file():
        raise LookupError(f"项目 Skill 允许列表不存在：{allowlist_path}")
    allowlist = yaml.safe_load(allowlist_path.read_text(encoding="utf-8"))
    provider = get_embedding_provider() if settings.rag_embedding_enabled else None
    total_documents = 0
    total_chunks = 0
    total_embedded = 0
    persona_count = 0

    for spec in allowlist.get("skills", []):
        if not isinstance(spec, dict):
            continue
        persona_slug = str(spec["persona_slug"])
        persona = db.scalar(select(Persona).where(Persona.slug == persona_slug))
        if persona is None:
            raise LookupError(f"未找到上游 Skill 对应人物：{persona_slug}")
        install_dir = str(spec["install_dir"])
        skill_root = (settings.upstream_skill_root / install_dir).resolve()
        upstream_root = settings.upstream_skill_root.resolve()
        if upstream_root not in skill_root.parents or not skill_root.is_dir():
            raise LookupError(f"已允许的项目 Skill 不存在：{install_dir}")
        repository = str(spec["repository"])
        pinned_commit = str(spec["pinned_commit"])
        license_name = str(spec["license"])
        markdown_files = sorted(
            path for path in skill_root.rglob("*.md") if path.is_file() and not path.is_symlink()
        )
        if not markdown_files or skill_root / "SKILL.md" not in markdown_files:
            raise LookupError(f"项目 Skill 缺少 SKILL.md 或知识文档：{install_dir}")

        existing_documents = list(
            db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.persona_id == persona.id))
        )
        by_source_file = {
            str(_metadata(document).get("source_file")): document
            for document in existing_documents
            if _metadata(document).get("repository") == repository
            and _metadata(document).get("source_file")
        }
        for source_path in markdown_files:
            relative_path = source_path.relative_to(skill_root).as_posix()
            content = source_path.read_text(encoding="utf-8")
            if not content.strip():
                continue
            document = by_source_file.get(relative_path)
            if document is None:
                document = KnowledgeDocument(persona_id=persona.id)
                db.add(document)
            label = f"{persona.name_zh}上游 Skill · {relative_path}"
            document.title = label
            document.persona_version_id = persona.current_version_id
            document.source_type = "upstream_vendored_skill"
            document.source_url = (
                f"https://github.com/{repository}/blob/{pinned_commit}/{quote(relative_path)}"
            )
            document.citation_label = label
            document.license_note = f"{license_name}；上游提交固定为 {pinned_commit}。"
            document.content = content
            document.metadata_json = json.dumps(
                {
                    "ingestion": "local_hybrid_rag",
                    "repository": repository,
                    "source_file": relative_path,
                    "pinned_commit": pinned_commit,
                    "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                },
                ensure_ascii=False,
            )
            document.enabled = True
            db.flush()

            db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
            chunks = chunk_markdown(
                content,
                settings.rag_chunk_chars,
                settings.rag_chunk_overlap_chars,
            )
            vectors = (
                provider.embed_documents([chunk.content for chunk in chunks]) if provider else []
            )
            for index, chunk in enumerate(chunks):
                vector = vectors[index] if vectors else None
                db.add(
                    KnowledgeChunk(
                        document_id=document.id,
                        persona_id=persona.id,
                        persona_version_id=persona.current_version_id,
                        chunk_index=index,
                        heading=chunk.heading,
                        content=chunk.content,
                        content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                        citation_label=document.citation_label,
                        source_url=document.source_url,
                        metadata_json=json.dumps(
                            {
                                "repository": repository,
                                "source_file": relative_path,
                                "start_char": chunk.start_char,
                                "end_char": chunk.end_char,
                            },
                            ensure_ascii=False,
                        ),
                        embedding_model=provider.model if vector is not None and provider else None,
                        embedding_dim=len(vector) if vector is not None else None,
                        embedding_blob=vector_to_blob(vector) if vector is not None else None,
                        enabled=True,
                    )
                )
            total_documents += 1
            total_chunks += len(chunks)
            total_embedded += len(vectors)
            db.flush()
        db.commit()
        persona_count += 1

    return BatchIngestReport(
        personas=persona_count,
        documents=total_documents,
        chunks=total_chunks,
        embedded_chunks=total_embedded,
        embedding_model=provider.model if provider else None,
    )
