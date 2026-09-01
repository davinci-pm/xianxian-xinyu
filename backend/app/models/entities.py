from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN")
    long_memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class VisitorSession(Base, TimestampMixin):
    __tablename__ = "visitor_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Persona(Base, TimestampMixin):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name_zh: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(120))
    era: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(80))
    domains_json: Mapped[str] = mapped_column(Text, default="[]")
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    dilemmas_json: Mapped[str] = mapped_column(Text, default="[]")
    short_intro: Mapped[str] = mapped_column(Text)
    avatar_tone: Mapped[str] = mapped_column(String(64), default="ink")
    chat_tier: Mapped[str] = mapped_column(String(1), default="B")
    status: Mapped[str] = mapped_column(String(24), default="active")
    is_living: Mapped[bool] = mapped_column(Boolean, default=False)
    pack_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    origin_type: Mapped[str] = mapped_column(String(32), default="curated", index=True)
    visibility: Mapped[str] = mapped_column(String(24), default="public", index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(32), index=True)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    visitor_id: Mapped[str] = mapped_column(
        ForeignKey("visitor_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    persona_id: Mapped[str] = mapped_column(ForeignKey("personas.id"), index=True)
    persona_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_versions.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), default="一场未命名的对话")
    stage: Mapped[str] = mapped_column(String(40), default="BREAK_ICE")
    status: Mapped[str] = mapped_column(String(24), default="active")
    short_summary: Mapped[str | None] = mapped_column(Text)
    unresolved_issue: Mapped[str | None] = mapped_column(Text)
    question_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_message_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(String(40))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(120))
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    visitor_id: Mapped[str] = mapped_column(
        ForeignKey("visitor_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    persona_id: Mapped[str] = mapped_column(ForeignKey("personas.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(32), default="unresolved_issue")
    content: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(24), default="candidate")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    confidence: Mapped[int] = mapped_column(Integer, default=70)
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    persona_id: Mapped[str] = mapped_column(ForeignKey("personas.id"), index=True)
    persona_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_versions.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    source_type: Mapped[str] = mapped_column(String(40), default="public_domain")
    source_url: Mapped[str | None] = mapped_column(Text)
    citation_label: Mapped[str] = mapped_column(String(240))
    license_note: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_position"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    persona_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_versions.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    citation_label: Mapped[str] = mapped_column(String(240))
    source_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    embedding_blob: Mapped[bytes | None] = mapped_column(LargeBinary)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SkillConfig(Base, TimestampMixin):
    __tablename__ = "skill_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    skill_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    source: Mapped[str] = mapped_column(Text)
    license_name: Mapped[str] = mapped_column(String(80))
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    allowlisted: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))


class SafetyEvent(Base, TimestampMixin):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitor_sessions.id", ondelete="CASCADE"))
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    level: Mapped[str] = mapped_column(String(8))
    category: Mapped[str] = mapped_column(String(40))
    matched_rule: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(80))
    redacted_excerpt: Mapped[str] = mapped_column(String(160))


class PersonaProject(Base, TimestampMixin):
    __tablename__ = "persona_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[str | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(32))
    relationship: Mapped[str] = mapped_column(String(80), default="")
    purpose: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN")
    visibility: Mapped[str] = mapped_column(String(24), default="private")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    calibration_json: Mapped[str] = mapped_column(Text, default="{}")
    source_char_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)


class PersonaSourceFile(Base, TimestampMixin):
    __tablename__ = "persona_source_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(240))
    source_type: Mapped[str] = mapped_column(String(40), default="text")
    mime_type: Mapped[str] = mapped_column(String(120), default="text/plain")
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    target_speaker: Mapped[str | None] = mapped_column(String(80))
    time_range: Mapped[str | None] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(40))
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="ready")


class PersonaEvidenceUnit(Base, TimestampMixin):
    __tablename__ = "persona_evidence_units"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[str] = mapped_column(
        ForeignKey("persona_source_files.id", ondelete="CASCADE"), index=True
    )
    speaker: Mapped[str | None] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    duplicate_group: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    time_range: Mapped[str | None] = mapped_column(String(120), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    start_char: Mapped[int] = mapped_column(Integer, default=0)
    end_char: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[int] = mapped_column(Integer, default=60)
    review_status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class PersonaCognitiveArtifact(Base, TimestampMixin):
    __tablename__ = "persona_cognitive_artifacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160))
    content_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=60)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    time_range: Mapped[str | None] = mapped_column(String(120), index=True)
    review_status: Mapped[str] = mapped_column(String(24), default="suggested", index=True)


class PersonaClaim(Base, TimestampMixin):
    __tablename__ = "persona_claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    claim_type: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=60)
    review_status: Mapped[str] = mapped_column(String(24), default="suggested")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")


class PersonaVersion(Base, TimestampMixin):
    __tablename__ = "persona_versions"
    __table_args__ = (UniqueConstraint("persona_id", "version", name="uq_persona_version_number"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DistillationJob(Base, TimestampMixin):
    __tablename__ = "distillation_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    pipeline_version: Mapped[str] = mapped_column(String(40), default="nuwa-internal-v1")
    error_message: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[str] = mapped_column(Text, default="{}")


class PersonaFeedback(Base, TimestampMixin):
    __tablename__ = "persona_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    persona_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_versions.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(40))
    target_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_cognitive_artifacts.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PersonaEvaluation(Base, TimestampMixin):
    __tablename__ = "persona_evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("persona_projects.id", ondelete="CASCADE"), index=True
    )
    persona_version_id: Mapped[str] = mapped_column(
        ForeignKey("persona_versions.id", ondelete="CASCADE"), index=True
    )
    suite_version: Mapped[str] = mapped_column(String(40), default="soul-eval-v1")
    score: Mapped[int] = mapped_column(Integer, default=0)
    dimensions_json: Mapped[str] = mapped_column(Text, default="{}")
    cases_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
