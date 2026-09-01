"""add persona studio and immutable runtime versions

Revision ID: d813f8c94b11
Revises: b42d8af731a1
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d813f8c94b11"
down_revision: str | Sequence[str] | None = "b42d8af731a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # These existing tables can be large in production. SQLite batch mode would
    # rebuild each table just to add nullable columns, which can exceed the
    # serverless startup deadline. The application validates these references,
    # while new Studio tables below retain database-level foreign keys.
    op.add_column("personas", sa.Column("owner_user_id", sa.String(length=32), nullable=True))
    op.add_column(
        "personas",
        sa.Column(
            "origin_type",
            sa.String(length=32),
            server_default="curated",
            nullable=False,
        ),
    )
    op.add_column(
        "personas",
        sa.Column(
            "visibility",
            sa.String(length=24),
            server_default="public",
            nullable=False,
        ),
    )
    op.add_column(
        "personas", sa.Column("current_version_id", sa.String(length=32), nullable=True)
    )
    op.create_index("idx_personas_owner_user_id", "personas", ["owner_user_id"])
    op.create_index("idx_personas_origin_type", "personas", ["origin_type"])
    op.create_index("idx_personas_visibility", "personas", ["visibility"])
    op.create_index("idx_personas_current_version_id", "personas", ["current_version_id"])

    op.create_table(
        "persona_projects",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("persona_id", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("relationship", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("calibration_json", sa.Text(), nullable=False),
        sa.Column("source_char_count", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_persona_projects_owner_user_id", "persona_projects", ["owner_user_id"])
    op.create_index("idx_persona_projects_persona_id", "persona_projects", ["persona_id"])
    op.create_index("idx_persona_projects_status", "persona_projects", ["status"])

    op.create_table(
        "persona_versions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("persona_id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=32), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("persona_id", "version", name="uq_persona_version_number"),
    )
    op.create_index("idx_persona_versions_persona_id", "persona_versions", ["persona_id"])
    op.create_index("idx_persona_versions_project_id", "persona_versions", ["project_id"])
    op.create_index("idx_persona_versions_status", "persona_versions", ["status"])

    op.create_table(
        "persona_source_files",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=240), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("target_speaker", sa.String(length=80), nullable=True),
        sa.Column("time_range", sa.String(length=120), nullable=True),
        sa.Column("rights_confirmed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_persona_source_files_project_id", "persona_source_files", ["project_id"])
    op.create_index(
        "idx_persona_source_files_content_hash",
        "persona_source_files",
        ["content_hash"],
    )

    op.create_table(
        "persona_claims",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("claim_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_persona_claims_project_id", "persona_claims", ["project_id"])

    op.create_table(
        "distillation_jobs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_distillation_jobs_project_id", "distillation_jobs", ["project_id"])
    op.create_index("idx_distillation_jobs_status", "distillation_jobs", ["status"])

    op.add_column(
        "conversations", sa.Column("persona_version_id", sa.String(length=32), nullable=True)
    )
    op.create_index(
        "idx_conversations_persona_version_id", "conversations", ["persona_version_id"]
    )

    op.add_column(
        "knowledge_documents",
        sa.Column("persona_version_id", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "idx_knowledge_documents_persona_version_id",
        "knowledge_documents",
        ["persona_version_id"],
    )

    op.add_column(
        "knowledge_chunks",
        sa.Column("persona_version_id", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "idx_knowledge_chunks_persona_version_id",
        "knowledge_chunks",
        ["persona_version_id"],
    )

    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    with op.batch_alter_table("knowledge_chunks", schema=None) as batch_op:
        batch_op.drop_index("idx_knowledge_chunks_persona_version_id")
        batch_op.drop_column("persona_version_id")

    with op.batch_alter_table("knowledge_documents", schema=None) as batch_op:
        batch_op.drop_index("idx_knowledge_documents_persona_version_id")
        batch_op.drop_column("persona_version_id")

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_index("idx_conversations_persona_version_id")
        batch_op.drop_column("persona_version_id")

    op.drop_index("idx_distillation_jobs_status", table_name="distillation_jobs")
    op.drop_index("idx_distillation_jobs_project_id", table_name="distillation_jobs")
    op.drop_table("distillation_jobs")
    op.drop_index("idx_persona_claims_project_id", table_name="persona_claims")
    op.drop_table("persona_claims")
    op.drop_index("idx_persona_source_files_content_hash", table_name="persona_source_files")
    op.drop_index("idx_persona_source_files_project_id", table_name="persona_source_files")
    op.drop_table("persona_source_files")
    op.drop_index("idx_persona_versions_status", table_name="persona_versions")
    op.drop_index("idx_persona_versions_project_id", table_name="persona_versions")
    op.drop_index("idx_persona_versions_persona_id", table_name="persona_versions")
    op.drop_table("persona_versions")
    op.drop_index("idx_persona_projects_status", table_name="persona_projects")
    op.drop_index("idx_persona_projects_persona_id", table_name="persona_projects")
    op.drop_index("idx_persona_projects_owner_user_id", table_name="persona_projects")
    op.drop_table("persona_projects")

    with op.batch_alter_table("personas", schema=None) as batch_op:
        batch_op.drop_index("idx_personas_current_version_id")
        batch_op.drop_index("idx_personas_visibility")
        batch_op.drop_index("idx_personas_origin_type")
        batch_op.drop_index("idx_personas_owner_user_id")
        batch_op.drop_column("current_version_id")
        batch_op.drop_column("visibility")
        batch_op.drop_column("origin_type")
        batch_op.drop_column("owner_user_id")
