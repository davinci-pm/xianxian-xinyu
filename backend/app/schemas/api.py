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
