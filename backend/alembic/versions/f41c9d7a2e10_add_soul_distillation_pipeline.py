"""add evidence, cognition, feedback and evaluation pipeline

Revision ID: f41c9d7a2e10
Revises: d813f8c94b11
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f41c9d7a2e10"
down_revision: str | Sequence[str] | None = "d813f8c94b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("persona_source_files", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column(
        "persona_source_files", sa.Column("published_at", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "distillation_jobs",
        sa.Column("report_json", sa.Text(), server_default="{}", nullable=False),
    )

    op.create_table(
        "persona_evidence_units",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("source_file_id", sa.String(length=32), nullable=False),
        sa.Column("speaker", sa.String(length=80), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("duplicate_group", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("time_range", sa.String(length=120), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["persona_source_files.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "project_id",
        "source_file_id",
        "content_hash",
        "duplicate_group",
        "time_range",
        "review_status",
    ):
        op.create_index(
            f"idx_persona_evidence_units_{column}", "persona_evidence_units", [column]
        )

    op.create_table(
        "persona_cognitive_artifacts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("time_range", sa.String(length=120), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "artifact_type", "time_range", "review_status"):
        op.create_index(
            f"idx_persona_cognitive_artifacts_{column}",
            "persona_cognitive_artifacts",
            [column],
        )

    op.create_table(
        "persona_feedback",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("persona_version_id", sa.String(length=32), nullable=True),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("feedback_type", sa.String(length=40), nullable=False),
        sa.Column("target_artifact_id", sa.String(length=32), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["persona_version_id"], ["persona_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["target_artifact_id"], ["persona_cognitive_artifacts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "persona_version_id", "user_id", "status"):
        op.create_index(f"idx_persona_feedback_{column}", "persona_feedback", [column])

    op.create_table(
        "persona_evaluations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("persona_version_id", sa.String(length=32), nullable=False),
        sa.Column("suite_version", sa.String(length=40), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("dimensions_json", sa.Text(), nullable=False),
        sa.Column("cases_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["persona_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["persona_version_id"], ["persona_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "persona_version_id", "status"):
        op.create_index(f"idx_persona_evaluations_{column}", "persona_evaluations", [column])


def downgrade() -> None:
    for table, columns in (
        ("persona_evaluations", ("status", "persona_version_id", "project_id")),
        ("persona_feedback", ("status", "user_id", "persona_version_id", "project_id")),
        (
            "persona_cognitive_artifacts",
            ("review_status", "time_range", "artifact_type", "project_id"),
        ),
        (
            "persona_evidence_units",
            (
                "review_status",
                "time_range",
                "duplicate_group",
                "content_hash",
                "source_file_id",
                "project_id",
            ),
        ),
    ):
        for column in columns:
            op.drop_index(f"idx_{table}_{column}", table_name=table)
        op.drop_table(table)
    op.drop_column("distillation_jobs", "report_json")
    op.drop_column("persona_source_files", "published_at")
    op.drop_column("persona_source_files", "source_url")
