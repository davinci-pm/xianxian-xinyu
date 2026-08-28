from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, Persona
from app.services.embeddings import get_embedding_provider, vector_to_blob
from app.services.knowledge import retrieve_knowledge
from app.services.rag_ingest import chunk_markdown, ingest_fengge_corpus


def test_markdown_chunker_preserves_headings_and_limits_size() -> None:
    markdown = "# 第一节\n" + "现实不是童话。" * 80 + "\n## 第二节\n先算代价，再做决定。" * 40
    chunks = chunk_markdown(markdown, limit=180, overlap=30)

    assert len(chunks) > 3
    assert {chunk.heading for chunk in chunks} >= {"第一节", "第二节"}
    assert all(len(chunk.content) <= 180 for chunk in chunks)
    assert all(chunk.end_char > chunk.start_char for chunk in chunks)


def test_hybrid_retrieval_uses_bm25_and_local_vectors() -> None:
    provider = get_embedding_provider()
    with SessionLocal() as db:
        persona = db.scalar(select(Persona).where(Persona.slug == "confucius"))
        assert persona is not None
        document = KnowledgeDocument(
            persona_id=persona.id,
            title="混合检索测试资料",
            source_type="test",
            citation_label="混合检索测试资料",
            license_note="test-only",
            content="裁员之后先盘点现金流和可迁移能力。",
            metadata_json="{}",
        )
        db.add(document)
        db.flush()
        contents = [
            "被裁员不是世界末日，先盘点现金流，再验证下一份工作的方向。",
            "旅行时要留意天气和交通，别把疲惫当成自由。",
        ]
        vectors = provider.embed_documents(contents)
        for index, (content, vector) in enumerate(zip(contents, vectors, strict=True)):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    persona_id=persona.id,
                    chunk_index=index,
                    heading="测试",
                    content=content,
                    content_hash=f"test-{index}",
                    citation_label=document.citation_label,
                    metadata_json="{}",
                    embedding_model=provider.model,
                    embedding_dim=len(vector),
                    embedding_blob=vector_to_blob(vector),
                )
            )
        db.commit()

        hits = retrieve_knowledge(db, persona.id, "我突然被公司裁员了，接下来怎么办")
        assert hits
        assert hits[0].chunk is not None
        assert "裁员" in hits[0].content
        assert hits[0].retrieval_method == "hybrid_rrf"

        db.delete(document)
        db.commit()


def test_fengge_corpus_import_is_complete_and_repeatable() -> None:
    with SessionLocal() as db:
        first = ingest_fengge_corpus(db)
        second = ingest_fengge_corpus(db)
        persona = db.scalar(select(Persona).where(Persona.slug == "fengge-wangmingtianya"))
        assert persona is not None
        stored_chunks = db.scalar(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.persona_id == persona.id)
        )

    assert first.documents == second.documents == 5
    assert first.chunks == second.chunks == stored_chunks
    assert second.embedded_chunks == second.chunks
    assert second.embedding_model == "deterministic-hash-128"
