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


def test_single_consolidated_document_can_fill_the_evidence_budget() -> None:
    with SessionLocal() as db:
        persona = Persona(
            slug="single-upload-retrieval-test",
            name_zh="单文件检索测试",
            name_en="Single upload test",
            era="当代",
            region="测试",
            short_intro="测试单个合并资料包的检索召回。",
        )
        db.add(persona)
        db.flush()
        document = KnowledgeDocument(
            persona_id=persona.id,
            title="合并资料包",
            source_type="interview",
            citation_label="合并资料包",
            license_note="test-only",
            content="创业动机与产品选择。",
            metadata_json="{}",
        )
        db.add(document)
        db.flush()
        for index in range(4):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    persona_id=persona.id,
                    chunk_index=index,
                    heading=f"动机记录 {index + 1}",
                    content=f"这是第 {index + 1} 段关于创业动机和产品选择的直接资料。",
                    content_hash=f"single-upload-{index}",
                    citation_label=document.citation_label,
                    metadata_json="{}",
                )
            )
        db.commit()

        hits = retrieve_knowledge(db, persona.id, "创业动机和产品选择", limit=4)

        assert len(hits) == 4

        db.delete(document)
        db.delete(persona)
        db.commit()


def test_retrieval_filters_explicitly_mismatched_time_ranges() -> None:
    with SessionLocal() as db:
        persona = Persona(
            slug="temporal-retrieval-test",
            name_zh="时间检索测试",
            name_en="Temporal retrieval test",
            era="当代",
            region="测试",
            short_intro="测试检索时间过滤。",
        )
        db.add(persona)
        db.flush()
        document = KnowledgeDocument(
            persona_id=persona.id,
            title="跨年资料",
            source_type="interview",
            citation_label="跨年资料",
            license_note="test-only",
            content="产品判断在不同年份发生了变化。",
            metadata_json="{}",
        )
        db.add(document)
        db.flush()
        for index, year in enumerate(("2020", "2025")):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    persona_id=persona.id,
                    chunk_index=index,
                    heading=f"{year}年访谈",
                    content=f"{year}年的产品选择是先验证用户需求。",
                    content_hash=f"temporal-{year}",
                    citation_label=document.citation_label,
                    metadata_json=f'{{"time_range":"{year}"}}',
                )
            )
        db.commit()

        hits = retrieve_knowledge(db, persona.id, "2020年的产品选择", limit=4)

        assert hits
        assert all("2025" not in hit.content for hit in hits)

        db.delete(document)
        db.delete(persona)
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
