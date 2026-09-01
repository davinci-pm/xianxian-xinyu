from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SessionResponse(ApiModel):
    authenticated: bool
    auth_required: bool
    locale: str
    long_memory_available: bool
    display_name: str | None = None


class InviteLoginRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=128)


class PersonaCard(ApiModel):
    id: str
    slug: str
    name_zh: str
    name_en: str
    era: str
    region: str
    domains: list[str]
    topics: list[str]
    dilemmas: list[str]
    short_intro: str
    avatar_tone: str
    chat_tier: str
    chat_enabled: bool
    is_living: bool


class SourceItem(ApiModel):
    title: str
    citation_label: str
    source_url: str | None = None
    license_note: str


class PersonaDetail(PersonaCard):
    identity: dict[str, Any]
    principles: list[dict[str, Any]]
    suitable_questions: list[str]
    representative_views: list[str]
    quick_replies: list[str]
    sources: list[SourceItem]
    disclaimer: str


class Citation(ApiModel):
    document_id: str
    label: str
    source_url: str | None = None


class MessageResponse(ApiModel):
    id: str
    role: str
    content: str
    stage: str | None
    citations: list[Citation] = Field(default_factory=list)
    degraded: bool = False
    created_at: datetime


class MemoryResponse(ApiModel):
    id: str
    kind: str
    content: str
    scope: str
    status: str
    confidence: int
    created_at: datetime


class ConversationSummary(ApiModel):
    id: str
    persona_slug: str
    persona_name: str
    title: str
    stage: str
    status: str
    short_summary: str | None
    last_message_at: datetime


class ConversationDetail(ApiModel):
    id: str
    persona: PersonaCard
    title: str
    stage: str
    status: str
    short_summary: str | None
    unresolved_issue: str | None
    messages: list[MessageResponse]
    memory_candidates: list[MemoryResponse]
    confirmed_memories: list[MemoryResponse]


class ConversationCreate(BaseModel):
    persona_slug: str


class ConversationCreateResponse(ApiModel):
    conversation: ConversationDetail
    opening_message: MessageResponse
    quick_replies: list[str]
    remembered_context: list[str]


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=64)


class MemoryConfirmRequest(BaseModel):
    action: Literal["remember", "session_only", "discard"]
    content: str | None = Field(default=None, min_length=1, max_length=500)


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=500)
    paused: bool | None = None


class SkillResponse(ApiModel):
    skill_key: str
    name: str
    version: str
    source: str
    license_name: str
    risk_level: str
    permissions: list[str]
    allowlisted: bool
    enabled: bool


PersonaTargetType = Literal[
    "self",
    "authorized_private",
    "public_figure",
    "deceased",
    "composite",
    "fictional",
]


class StudioProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    target_type: PersonaTargetType
    relationship: str = Field(default="", max_length=80)
    purpose: str = Field(min_length=8, max_length=1000)
    language: str = Field(default="zh-CN", min_length=2, max_length=16)


class StudioSourceCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    source_type: Literal[
        "chat",
        "writing",
        "timeline",
        "interview",
        "public_statements",
        "social",
        "speech",
        "text",
    ] = "text"
    mime_type: str = Field(default="text/plain", max_length=120)
    content: str = Field(min_length=20, max_length=500_000)
    target_speaker: str | None = Field(default=None, max_length=80)
    time_range: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=2000)
    published_at: str | None = Field(default=None, max_length=40)
    rights_confirmed: bool


class StudioCalibration(BaseModel):
    core_values: str = Field(default="", max_length=2000)
    decision_case: str = Field(default="", max_length=3000)
    never_do: str = Field(default="", max_length=2000)
    unlike_response: str = Field(default="", max_length=2000)


class StudioHealthDimension(ApiModel):
    key: str
    label: str
    score: int
    status: Literal["strong", "usable", "gap"]
    detail: str


class StudioHealthReport(ApiModel):
    readiness_level: Literal["轮廓版", "可用版", "推荐版", "高保真版"]
    overall_score: int
    effective_chars: int
    substantive_utterances: int
    decision_signals: int
    domains_covered: list[str]
    source_types: list[str]
    adaptive_tier: Literal["outline", "structured", "deep", "trainable"]
    enabled_capabilities: list[str]
    fidelity_validated: bool
    metric_scope: str
    data_profile: dict[str, int | bool]
    dimensions: list[StudioHealthDimension]
    gaps: list[str]
    recommended_questions: list[str]
    can_distill: bool


class StudioSourceResponse(ApiModel):
    id: str
    filename: str
    source_type: str
    mime_type: str
    char_count: int
    target_speaker: str | None
    time_range: str | None
    source_url: str | None
    published_at: str | None
    rights_confirmed: bool
    status: str
    created_at: datetime


class StudioClaimResponse(ApiModel):
    id: str
    claim_type: str
    content: str
    confidence: int
    review_status: str
    evidence_count: int


class StudioProjectResponse(ApiModel):
    id: str
    name: str
    target_type: str
    relationship: str
    purpose: str
    language: str
    visibility: str
    status: str
    source_char_count: int
    quality_score: int
    persona_slug: str | None = None
    sources: list[StudioSourceResponse] = Field(default_factory=list)
    claims: list[StudioClaimResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StudioDistillationResponse(ApiModel):
    project: StudioProjectResponse
    persona: PersonaCard
    version: str
    job_id: str
    quality_score: int
    pipeline: dict[str, Any]


class StudioPipelineStage(ApiModel):
    key: str
    label: str
    status: str
    count: int
    detail: str


class StudioPipelineResponse(ApiModel):
    pipeline_version: str
    job_id: str | None = None
    status: str
    progress: int
    stages: list[StudioPipelineStage] = Field(default_factory=list)
    evaluation_score: int | None = None
    evaluation_dimensions: dict[str, int] = Field(default_factory=dict)
    artifact_counts: dict[str, int] = Field(default_factory=dict)
    pending_feedback: int = 0


class StudioFeedbackCreate(BaseModel):
    feedback_type: Literal["fact_error", "unlike", "missing_context", "better_response"]
    content: str = Field(min_length=4, max_length=3000)
    target_artifact_id: str | None = Field(default=None, max_length=32)


class StudioFeedbackReview(BaseModel):
    action: Literal["approve", "reject"]
    review_note: str | None = Field(default=None, max_length=1000)


class StudioFeedbackResponse(ApiModel):
    id: str
    feedback_type: str
    content: str
    target_artifact_id: str | None
    status: str
    review_note: str | None
    created_at: datetime


class OwnedPersonaResponse(PersonaCard):
    version: str
    quality_score: int
    visibility: str
    project_id: str | None = None
