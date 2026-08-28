"""add hybrid RAG knowledge chunks

Revision ID: b42d8af731a1
Revises: 9acf2121a884
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b42d8af731a1"
down_revision: Union[str, Sequence[str], None] = "9acf2121a884"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("persona_id", sa.String(length=32), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=240), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("citation_label", sa.String(length=240), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("embedding_blob", sa.LargeBinary(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_knowledge_chunk_position"
        ),
    )
    with op.batch_alter_table("knowledge_chunks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_knowledge_chunks_document_id"), ["document_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_knowledge_chunks_persona_id"), ["persona_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_knowledge_chunks_content_hash"), ["content_hash"], unique=False
        )

    op.execute(
        "CREATE VIRTUAL TABLE knowledge_chunks_fts USING fts5("
        "id UNINDEXED, document_id UNINDEXED, persona_id UNINDEXED, heading, content, "
        "tokenize='unicode61')"
    )
    op.execute(
        "CREATE TRIGGER knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN "
        "INSERT INTO knowledge_chunks_fts(id, document_id, persona_id, heading, content) "
        "VALUES (new.id, new.document_id, new.persona_id, new.heading, new.content); END"
    )
    op.execute(
        "CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN "
        "DELETE FROM knowledge_chunks_fts WHERE id = old.id; "
        "INSERT INTO knowledge_chunks_fts(id, document_id, persona_id, heading, content) "
        "VALUES (new.id, new.document_id, new.persona_id, new.heading, new.content); END"
    )
    op.execute(
        "CREATE TRIGGER knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN "
        "DELETE FROM knowledge_chunks_fts WHERE id = old.id; END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ad")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_au")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ai")
    op.execute("DROP TABLE IF EXISTS knowledge_chunks_fts")
    with op.batch_alter_table("knowledge_chunks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_chunks_content_hash"))
        batch_op.drop_index(batch_op.f("ix_knowledge_chunks_persona_id"))
        batch_op.drop_index(batch_op.f("ix_knowledge_chunks_document_id"))
    op.drop_table("knowledge_chunks")
