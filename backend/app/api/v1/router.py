import asyncio
import hashlib
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import VisitorIdentity, resolve_visitor
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.models import (
    Conversation,
    GenerationRun,
    KnowledgeDocument,
    Memory,
    Message,
    Persona,
    PersonaClaim,
    PersonaProject,
    PersonaSourceFile,
    PersonaVersion,
    SafetyEvent,
    SkillConfig,
)
from app.schemas.api import (
    ChatMessageCreate,
    Citation,
    ConversationCreate,
    ConversationCreateResponse,
    ConversationDetail,
    ConversationSummary,
    InviteLoginRequest,
    MemoryConfirmRequest,
    MemoryResponse,
    MemoryUpdateRequest,
    MessageResponse,
    OwnedPersonaResponse,
    PersonaCard,
    PersonaDetail,
    SessionResponse,
    SkillResponse,
    SourceItem,
    StudioCalibration,
    StudioClaimResponse,
    StudioDistillationResponse,
    StudioHealthReport,
    StudioProjectCreate,
    StudioProjectResponse,
    StudioSourceCreate,
    StudioSourceResponse,
)
from app.services.auth import (
    attach_visitor_to_user,
    encode_session_cookie,
    get_or_create_invite_user,
    match_invite_code,
)
from app.services.conversation_director import DialogueStage, conversation_director
from app.services.intent_classifier import analyze_intent
from app.services.knowledge import KnowledgeHit, retrieve_knowledge
from app.services.llm.base import GenerationContext
from app.services.llm.factory import get_model_provider
from app.services.llm.openai_compatible import EmptyModelContentError
from app.services.memory import confirm_memory, create_memory_candidate, list_confirmed_memories
from app.services.persona_distillation import (
    DistillationInputError,
    analyze_project_health,
    distill_project,
)
from app.services.persona_loader import PersonaPack
from app.services.persona_runtime import load_runtime_persona_pack
from app.services.safety import (
    SafetyAssessment,
    assess_safety,
    confirms_current_safety,
    confirms_immediate_danger,
    crisis_response,
    redact_excerpt,
    safety_followup_response,
    safety_recovery_response,
)
from app.services.skill_adapter import skill_adapter

router = APIRouter()


def _json_list(value: str) -> list[str]:
    loaded = json.loads(value)
    return [str(item) for item in loaded]


def _persona_card(persona: Persona) -> PersonaCard:
    return PersonaCard(
        id=persona.id,
        slug=persona.slug,
        name_zh=persona.name_zh,
        name_en=persona.name_en,
        era=persona.era,
        region=persona.region,
        domains=_json_list(persona.domains_json),
        topics=_json_list(persona.topics_json),
        dilemmas=_json_list(persona.dilemmas_json),
        short_intro=persona.short_intro,
        avatar_tone=persona.avatar_tone,
        chat_tier=persona.chat_tier,
        chat_enabled=persona.status == "active",
        is_living=persona.is_living,
    )


def _citations(message: Message) -> list[Citation]:
    return [Citation.model_validate(item) for item in json.loads(message.citations_json)]


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        stage=message.stage,
        citations=_citations(message),
        degraded=message.degraded,
        created_at=message.created_at,
    )


def _memory_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse.model_validate(memory)


def _conversation_detail(
    db: Session, conversation: Conversation, persona: Persona
) -> ConversationDetail:
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at, Message.id)
        )
    )
    candidates = list(
        db.scalars(
            select(Memory)
            .where(
                Memory.conversation_id == conversation.id,
                Memory.scope == "candidate",
                Memory.status == "pending",
            )
            .order_by(Memory.created_at.desc())
        )
    )
    confirmed = list_confirmed_memories(
        db,
        conversation.visitor_id,
        persona.id,
        user_id=conversation.user_id,
        conversation_id=conversation.id,
    )
    return ConversationDetail(
        id=conversation.id,
        persona=_persona_card(persona),
        title=conversation.title,
        stage=conversation.stage,
        status=conversation.status,
        short_summary=conversation.short_summary,
        unresolved_issue=conversation.unresolved_issue,
        messages=[_message_response(message) for message in messages],
        memory_candidates=[_memory_response(memory) for memory in candidates],
        confirmed_memories=[_memory_response(memory) for memory in confirmed],
    )


def _set_visitor_cookie(response: Response, identity: VisitorIdentity) -> None:
    if not identity.cookie_created:
        return
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=encode_session_cookie(identity.visitor.id),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=60 * 60 * 24 * 365,
    )


def _owned_conversation(
    db: Session, conversation_id: str, identity: VisitorIdentity
) -> Conversation:
    owner_filter = (
        Conversation.user_id == identity.user.id
        if identity.user
        else Conversation.visitor_id == identity.visitor.id
    )
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            owner_filter,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该会话")
    return conversation


def _owned_memory(db: Session, memory_id: str, identity: VisitorIdentity) -> Memory:
    owner_filter = (
        Memory.user_id == identity.user.id
        if identity.user
        else Memory.visitor_id == identity.visitor.id
    )
    memory = db.scalar(select(Memory).where(Memory.id == memory_id, owner_filter))
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该记忆")
    return memory


def _owned_project(db: Session, project_id: str, identity: VisitorIdentity) -> PersonaProject:
    if identity.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    project = db.scalar(
        select(PersonaProject).where(
            PersonaProject.id == project_id,
            PersonaProject.owner_user_id == identity.user.id,
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该人物草稿")
    return project


def _require_persona_access(persona: Persona, identity: VisitorIdentity) -> None:
    if persona.origin_type != "user_created" or persona.visibility == "public":
        return
    if identity.user is None or persona.owner_user_id != identity.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该人物")


def _studio_source_response(source: PersonaSourceFile) -> StudioSourceResponse:
    return StudioSourceResponse.model_validate(source)


def _studio_claim_response(claim: PersonaClaim) -> StudioClaimResponse:
    try:
        evidence = json.loads(claim.evidence_json)
    except json.JSONDecodeError:
        evidence = []
    return StudioClaimResponse(
        id=claim.id,
        claim_type=claim.claim_type,
        content=claim.content,
        confidence=claim.confidence,
        review_status=claim.review_status,
        evidence_count=len(evidence) if isinstance(evidence, list) else 0,
    )


def _studio_project_response(db: Session, project: PersonaProject) -> StudioProjectResponse:
    sources = list(
        db.scalars(
            select(PersonaSourceFile)
            .where(PersonaSourceFile.project_id == project.id)
            .order_by(PersonaSourceFile.created_at, PersonaSourceFile.id)
        )
    )
    claims = list(
        db.scalars(
            select(PersonaClaim)
            .where(PersonaClaim.project_id == project.id)
            .order_by(PersonaClaim.created_at, PersonaClaim.id)
        )
    )
    persona = db.get(Persona, project.persona_id) if project.persona_id else None
    return StudioProjectResponse(
        id=project.id,
        name=project.name,
        target_type=project.target_type,
        relationship=project.relationship,
        purpose=project.purpose,
        language=project.language,
        visibility=project.visibility,
        status=project.status,
        source_char_count=project.source_char_count,
        quality_score=project.quality_score,
        persona_slug=persona.slug if persona else None,
        sources=[_studio_source_response(source) for source in sources],
        claims=[_studio_claim_response(claim) for claim in claims],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _retrieval_query(user_text: str, recent_messages: list[dict[str, str]]) -> str:
    """Restore the subject for short follow-ups without dragging old topics forward."""
    compact = user_text.strip()
    noise = re.sub(r"[\s，。！？!?~～哈呵嗯哦啊欸]", "", compact)
    clear_small_talk = {
        "你好",
        "在吗",
        "早安",
        "晚安",
        "谢谢",
        "谢啦",
        "吃什么",
        "天气怎么样",
    }
    if compact in clear_small_talk or not noise or re.fullmatch(r"(.)\1{2,}", compact):
        return ""
    continuation_markers = (
        "这个",
        "那个",
        "为什么",
        "然后呢",
        "继续",
        "具体呢",
        "怎么说",
        "那我",
        "所以呢",
    )
    if len(compact) > 28 and not any(marker in compact for marker in continuation_markers):
        return compact
    previous_user = next(
        (
            message["content"]
            for message in reversed(recent_messages)
            if message.get("role") == "user" and message.get("content")
        ),
        "",
    )
    if not previous_user and compact in {
        "为什么",
        "怎么办",
        "然后呢",
        "继续",
        "具体呢",
        "是吗",
        "对吗",
    }:
        return ""
    return f"{previous_user[-500:]}\n{compact}".strip()


async def _stream_with_heartbeats(
    source: AsyncIterator[str], *, interval_seconds: float = 3.0
) -> AsyncIterator[str]:
    """Keep the browser connection visibly alive while preprocessing or reasoning."""
    queue: asyncio.Queue[tuple[str, str | Exception | None]] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for event in source:
                await queue.put(("event", event))
        except Exception as exc:
            await queue.put(("error", exc))
        else:
            await queue.put(("done", None))

    producer = asyncio.create_task(pump())
    phase = "preparing"
    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=interval_seconds)
            except TimeoutError:
                yield _sse("heartbeat", {"phase": phase})
                continue
            if kind == "done":
                return
            if kind == "error":
                assert isinstance(payload, Exception)
                raise payload
            assert isinstance(payload, str)
            if payload.startswith("event: chunk\n"):
                phase = "writing"
            yield payload
    finally:
        if not producer.done():
            producer.cancel()
        try:
            await producer
        except asyncio.CancelledError:
            pass


@router.get("/session", response_model=SessionResponse)
def get_session(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> SessionResponse:
    identity = resolve_visitor(request, db, require_auth=False)
    _set_visitor_cookie(response, identity)
    return SessionResponse(
        authenticated=identity.authenticated,
        auth_required=get_settings().auth_required,
        locale=identity.visitor.locale,
        long_memory_available=identity.authenticated,
        display_name=identity.user.display_name if identity.user else None,
    )


@router.post("/auth/login", response_model=SessionResponse)
def login_with_invite(
    payload: InviteLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    client_host = request.client.host if request.client else "unknown"
    rate_limiter.check(f"invite-login:{client_host}")
    match = match_invite_code(payload.invite_code)
    if match is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邀请码无效")
    identity = resolve_visitor(request, db, require_auth=False)
    user = get_or_create_invite_user(db, match)
    attach_visitor_to_user(db, identity.visitor, user)
    db.commit()
    authenticated = VisitorIdentity(visitor=identity.visitor, user=user, cookie_created=True)
    _set_visitor_cookie(response, authenticated)
    return SessionResponse(
        authenticated=True,
        auth_required=get_settings().auth_required,
        locale=user.locale,
        long_memory_available=user.long_memory_enabled,
        display_name=user.display_name,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(
        settings.cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/studio/projects", response_model=list[StudioProjectResponse])
def list_studio_projects(
    request: Request, db: Session = Depends(get_db)
) -> list[StudioProjectResponse]:
    identity = resolve_visitor(request, db, require_auth=True)
    assert identity.user is not None
    projects = list(
        db.scalars(
            select(PersonaProject)
            .where(PersonaProject.owner_user_id == identity.user.id)
            .order_by(PersonaProject.updated_at.desc())
        )
    )
    return [_studio_project_response(db, project) for project in projects]


@router.post(
    "/studio/projects",
    response_model=StudioProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_studio_project(
    payload: StudioProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> StudioProjectResponse:
    identity = resolve_visitor(request, db, require_auth=True)
    assert identity.user is not None
    rate_limiter.check(f"studio-project:{identity.user.id}")
    project = PersonaProject(
        owner_user_id=identity.user.id,
        name=payload.name.strip(),
        target_type=payload.target_type,
        relationship=payload.relationship.strip(),
        purpose=payload.purpose.strip(),
        language=payload.language,
        visibility="private",
        status="draft",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _studio_project_response(db, project)


@router.get("/studio/projects/{project_id}", response_model=StudioProjectResponse)
def get_studio_project(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> StudioProjectResponse:
    identity = resolve_visitor(request, db, require_auth=True)
    project = _owned_project(db, project_id, identity)
    return _studio_project_response(db, project)


@router.post(
    "/studio/projects/{project_id}/sources",
    response_model=StudioSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_studio_source(
    project_id: str,
    payload: StudioSourceCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> StudioSourceResponse:
    identity = resolve_visitor(request, db, require_auth=True)
    project = _owned_project(db, project_id, identity)
    assert identity.user is not None
    rate_limiter.check(f"studio-source:{identity.user.id}")
    filename = payload.filename.strip()
    if Path(filename).name != filename or any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=422, detail="资料文件名不合法")
    if Path(filename).suffix.lower() not in {".txt", ".md", ".csv", ".json", ".jsonl"}:
        raise HTTPException(
            status_code=415,
            detail="内测版仅支持 TXT、Markdown、CSV、JSON 和 JSONL",
        )
    if not payload.rights_confirmed:
        raise HTTPException(status_code=422, detail="请先确认你有权使用这份资料")
    content = payload.content.replace("\x00", "").strip()
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    duplicate = db.scalar(
        select(PersonaSourceFile).where(
            PersonaSourceFile.project_id == project.id,
            PersonaSourceFile.content_hash == content_hash,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="这份资料已经上传过了")
    source = PersonaSourceFile(
        project_id=project.id,
        filename=filename,
        source_type=payload.source_type,
        mime_type=payload.mime_type,
        content=content,
        char_count=len(content),
        content_hash=content_hash,
        target_speaker=payload.target_speaker.strip() if payload.target_speaker else None,
        time_range=payload.time_range.strip() if payload.time_range else None,
        rights_confirmed=True,
        status="ready",
    )
    db.add(source)
    project.status = "sources_ready"
    project.source_char_count += len(content)
    db.commit()
    db.refresh(source)
    return _studio_source_response(source)


@router.post(
    "/studio/projects/{project_id}/health",
    response_model=StudioHealthReport,
)
def analyze_studio_project(
    project_id: str,
    payload: StudioCalibration,
    request: Request,
    db: Session = Depends(get_db),
) -> StudioHealthReport:
    identity = resolve_visitor(request, db, require_auth=True)
    project = _owned_project(db, project_id, identity)
    sources = list(
        db.scalars(
            select(PersonaSourceFile)
            .where(PersonaSourceFile.project_id == project.id)
            .order_by(PersonaSourceFile.created_at, PersonaSourceFile.id)
        )
    )
    return StudioHealthReport.model_validate(analyze_project_health(sources, payload.model_dump()))


@router.post(
    "/studio/projects/{project_id}/distill",
    response_model=StudioDistillationResponse,
)
def run_studio_distillation(
    project_id: str,
    payload: StudioCalibration,
    request: Request,
    db: Session = Depends(get_db),
) -> StudioDistillationResponse:
    identity = resolve_visitor(request, db, require_auth=True)
    project = _owned_project(db, project_id, identity)
    assert identity.user is not None
    rate_limiter.check(f"studio-distill:{identity.user.id}")
    try:
        persona, version, job = distill_project(
            db,
            project,
            owner_user_id=identity.user.id,
            calibration=payload.model_dump(),
        )
        db.commit()
    except DistillationInputError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(project)
    return StudioDistillationResponse(
        project=_studio_project_response(db, project),
        persona=_persona_card(persona),
        version=version.version,
        job_id=job.id,
        quality_score=version.quality_score,
    )


@router.get("/me/personas", response_model=list[OwnedPersonaResponse])
def list_owned_personas(
    request: Request, db: Session = Depends(get_db)
) -> list[OwnedPersonaResponse]:
    identity = resolve_visitor(request, db, require_auth=True)
    assert identity.user is not None
    personas = list(
        db.scalars(
            select(Persona)
            .where(
                Persona.owner_user_id == identity.user.id,
                Persona.origin_type == "user_created",
            )
            .order_by(Persona.updated_at.desc())
        )
    )
    result: list[OwnedPersonaResponse] = []
    for persona in personas:
        version = db.get(PersonaVersion, persona.current_version_id)
        project = db.scalar(select(PersonaProject).where(PersonaProject.persona_id == persona.id))
        result.append(
            OwnedPersonaResponse(
                **_persona_card(persona).model_dump(),
                version=version.version if version else persona.pack_version,
                quality_score=version.quality_score if version else 0,
                visibility=persona.visibility,
                project_id=project.id if project else None,
            )
        )
    return result


@router.get("/personas", response_model=list[PersonaCard])
def list_personas(db: Session = Depends(get_db)) -> list[PersonaCard]:
    personas = list(
        db.scalars(
            select(Persona)
            .where(Persona.origin_type == "curated")
            .order_by(Persona.chat_tier, Persona.name_en)
        )
    )
    return [_persona_card(persona) for persona in personas]


@router.get("/personas/{slug}", response_model=PersonaDetail)
def get_persona(slug: str, request: Request, db: Session = Depends(get_db)) -> PersonaDetail:
    persona = db.scalar(select(Persona).where(Persona.slug == slug))
    if persona is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该人物")
    identity = resolve_visitor(request, db, require_auth=False)
    _require_persona_access(persona, identity)
    pack = load_runtime_persona_pack(db, persona)
    profile = pack.profile
    source_conditions = [
        KnowledgeDocument.persona_id == persona.id,
        KnowledgeDocument.enabled.is_(True),
    ]
    if persona.origin_type == "user_created" and persona.current_version_id:
        source_conditions.append(KnowledgeDocument.persona_version_id == persona.current_version_id)
    stored_sources = list(
        db.scalars(
            select(KnowledgeDocument)
            .where(*source_conditions)
            .order_by(KnowledgeDocument.title)
            .limit(20)
        )
    )
    source_items = (
        [
            SourceItem(
                title=document.title,
                citation_label=document.citation_label,
                source_url=document.source_url,
                license_note=document.license_note,
            )
            for document in stored_sources
        ]
        if stored_sources
        else [
            SourceItem(
                title=str(item["title"]),
                citation_label=str(item["citation_label"]),
                source_url=item.get("source_url"),
                license_note=str(item["license_note"]),
            )
            for item in pack.sources
        ]
    )
    return PersonaDetail(
        **_persona_card(persona).model_dump(),
        identity=dict(pack.manifest["identity"]),
        principles=[dict(item) for item in pack.manifest["principles"]],
        suitable_questions=[str(item) for item in profile.get("dilemmas", [])],
        representative_views=[
            str(item.get("meaning", item.get("name", ""))) for item in pack.manifest["principles"]
        ],
        quick_replies=[str(item) for item in pack.starters[0]["quick_replies"]],
        sources=source_items,
        disclaimer=str(pack.manifest["disclaimer"]),
    )


@router.post(
    "/conversations",
    response_model=ConversationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ConversationCreateResponse:
    identity = resolve_visitor(request, db)
    rate_limiter.check(f"conversation:{identity.visitor.id}")
    persona = db.scalar(select(Persona).where(Persona.slug == payload.persona_slug))
    if persona is None or persona.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该人物暂不可聊天")
    _require_persona_access(persona, identity)
    pack = load_runtime_persona_pack(db, persona)
    remembered = list_confirmed_memories(
        db,
        identity.visitor.id,
        persona.id,
        user_id=identity.user.id if identity.user else None,
    )
    starter = pack.starters[0]
    opening_text = str(starter["text"])
    if remembered:
        opening_text += (
            f" 我记得你上次提到：{remembered[0].content}。如果你愿意，我们可以从那里继续。"
        )
    conversation = Conversation(
        visitor_id=identity.visitor.id,
        user_id=identity.user.id if identity.user else None,
        persona_id=persona.id,
        persona_version_id=persona.current_version_id,
        title=f"与{persona.name_zh}的对话",
        stage=DialogueStage.IDENTIFY_PROBLEM,
    )
    db.add(conversation)
    db.flush()
    opening = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=opening_text,
        stage=DialogueStage.BREAK_ICE,
        provider="persona_pack",
        model="deterministic-opening",
    )
    db.add(opening)
    db.commit()
    db.refresh(opening)
    _set_visitor_cookie(response, identity)
    detail = _conversation_detail(db, conversation, persona)
    return ConversationCreateResponse(
        conversation=detail,
        opening_message=_message_response(opening),
        quick_replies=[str(item) for item in starter["quick_replies"]],
        remembered_context=[item.content for item in remembered],
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> list[ConversationSummary]:
    identity = resolve_visitor(request, db)
    _set_visitor_cookie(response, identity)
    rows = db.execute(
        select(Conversation, Persona)
        .join(Persona, Persona.id == Conversation.persona_id)
        .where(
            Conversation.user_id == identity.user.id
            if identity.user
            else Conversation.visitor_id == identity.visitor.id
        )
        .order_by(Conversation.last_message_at.desc())
    ).all()
    return [
        ConversationSummary(
            id=conversation.id,
            persona_slug=persona.slug,
            persona_name=persona.name_zh,
            title=conversation.title,
            stage=conversation.stage,
            status=conversation.status,
            short_summary=conversation.short_summary,
            last_message_at=conversation.last_message_at,
        )
        for conversation, persona in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ConversationDetail:
    identity = resolve_visitor(request, db)
    conversation = _owned_conversation(db, conversation_id, identity)
    persona = db.get(Persona, conversation.persona_id)
    if persona is None:
        raise HTTPException(status_code=500, detail="会话人物数据缺失")
    _set_visitor_cookie(response, identity)
    return _conversation_detail(db, conversation, persona)


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: str,
    payload: ChatMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    identity = resolve_visitor(request, db)
    rate_limiter.check(f"chat:{identity.visitor.id}")
    conversation = _owned_conversation(db, conversation_id, identity)
    persona = db.get(Persona, conversation.persona_id)
    if persona is None:
        raise HTTPException(status_code=500, detail="会话人物数据缺失")
    pack = load_runtime_persona_pack(db, persona, conversation.persona_version_id)

    existing = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.idempotency_key == payload.idempotency_key,
        )
    )

    async def event_stream() -> AsyncIterator[str]:
        if existing is not None:
            replay = db.scalar(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.role == "assistant",
                    Message.created_at >= existing.created_at,
                )
                .order_by(Message.created_at, Message.id)
                .limit(1)
            )
            if replay is not None:
                yield _sse("meta", {"replay": True, "stage": replay.stage})
                yield _sse("chunk", {"text": replay.content})
                yield _sse(
                    "done",
                    {"message": _message_response(replay).model_dump(mode="json"), "replay": True},
                )
                return
        source = _generate_reply(
            db=db,
            identity=identity,
            conversation=conversation,
            persona=persona,
            pack=pack,
            payload=payload,
            existing_user_message=existing,
        )
        async for event in _stream_with_heartbeats(source):
            yield event

    response = StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    _set_visitor_cookie(response, identity)
    return response


async def _generate_reply(
    *,
    db: Session,
    identity: VisitorIdentity,
    conversation: Conversation,
    persona: Persona,
    pack: PersonaPack,
    payload: ChatMessageCreate,
    existing_user_message: Message | None = None,
) -> AsyncIterator[str]:
    turn_started = monotonic()
    if existing_user_message is None:
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.content.strip(),
            stage=conversation.stage,
            idempotency_key=payload.idempotency_key,
        )
        db.add(user_message)
        db.flush()
    else:
        user_message = existing_user_message
    assessment = assess_safety(user_message.content)
    if conversation.stage == DialogueStage.SAFETY and confirms_immediate_danger(
        user_message.content
    ):
        assessment = SafetyAssessment(
            "L3",
            "self_harm",
            "immediate_danger_confirmation",
            True,
        )
    if assessment.should_break_role:
        assistant = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=crisis_response(assessment.level),
            stage=DialogueStage.SAFETY,
            provider="safety_policy",
            model="deterministic-safety",
        )
        db.add(assistant)
        db.flush()
        db.add(
            SafetyEvent(
                visitor_id=identity.visitor.id,
                conversation_id=conversation.id,
                message_id=user_message.id,
                level=assessment.level,
                category=assessment.category,
                matched_rule=assessment.matched_rule,
                action="break_role_and_show_crisis_response",
                redacted_excerpt=redact_excerpt(user_message.content),
            )
        )
        conversation.stage = DialogueStage.SAFETY
        conversation.last_message_at = datetime.now(UTC)
        db.commit()
        yield _sse("meta", {"stage": DialogueStage.SAFETY, "safety_level": assessment.level})
        yield _sse("chunk", {"text": assistant.content})
        yield _sse("done", {"message": _message_response(assistant).model_dump(mode="json")})
        return

    if conversation.stage == DialogueStage.SAFETY:
        recovered = confirms_current_safety(user_message.content)
        next_safety_stage = DialogueStage.CLARIFY if recovered else DialogueStage.SAFETY
        assistant = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=safety_recovery_response() if recovered else safety_followup_response(),
            stage=next_safety_stage,
            provider="safety_policy",
            model="deterministic-safety-recovery",
        )
        db.add(assistant)
        conversation.stage = next_safety_stage
        conversation.question_streak = 0
        conversation.last_message_at = datetime.now(UTC)
        db.commit()
        db.refresh(assistant)
        yield _sse(
            "meta",
            {
                "stage": next_safety_stage,
                "safety_status": "recovered" if recovered else "awaiting_confirmation",
            },
        )
        yield _sse("chunk", {"text": assistant.content})
        yield _sse(
            "done",
            {
                "message": _message_response(assistant).model_dump(mode="json"),
                "conversation_stage": next_safety_stage,
            },
        )
        return

    recent = list(
        db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.id != user_message.id,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(8)
        )
    )
    recent.reverse()
    recent_payload = [{"role": message.role, "content": message.content} for message in recent]
    intent_task = asyncio.create_task(analyze_intent(user_message.content, recent_payload))
    # 先让远端语义分析请求发出，再并行完成 RAG；避免把两段耗时串联。
    await asyncio.sleep(0)
    confirmed_memories = list_confirmed_memories(
        db,
        identity.visitor.id,
        persona.id,
        user_id=identity.user.id if identity.user else None,
        conversation_id=conversation.id,
    )
    retrieval_started = monotonic()
    knowledge_query = _retrieval_query(user_message.content, recent_payload)
    knowledge_hits = (
        retrieve_knowledge(
            db,
            persona.id,
            knowledge_query,
            version_id=conversation.persona_version_id,
        )
        if knowledge_query
        else []
    )
    retrieval_ms = int((monotonic() - retrieval_started) * 1000)
    intent_result = await intent_task
    intent_payload = intent_result.analysis.model_dump(mode="json")
    if assessment.level != "L0":
        intent_payload["safety_context"] = {
            "level": assessment.level,
            "category": assessment.category,
            "response_mode": "stay_in_character_supportively",
            "guidance": "完整回应主要问题；不因敏感词中断；必要时最多确认一次当前安全状况",
        }
    memory_candidate = create_memory_candidate(
        db,
        visitor_id=identity.visitor.id,
        user_id=identity.user.id if identity.user else None,
        persona_id=persona.id,
        conversation_id=conversation.id,
        message=user_message,
        should_offer=intent_result.analysis.memory_should_offer,
        kind=intent_result.analysis.memory_kind,
        content=intent_result.analysis.memory_content,
        confidence=intent_result.analysis.memory_confidence,
    )
    next_stage = conversation_director.next_stage(
        conversation.stage,
        user_message.content,
        conversation.question_streak,
        intent_payload,
    )
    should_ask = conversation_director.should_ask_question(
        next_stage, conversation.question_streak, intent_payload
    )
    applied_skills: list[str] = []
    applied_skill_modes: dict[str, str] = {}
    skill_prompt_source_chars = 0
    skill_prompt_runtime_chars = 0
    skill_instructions: list[str] = []
    skill_failure: Exception | None = None
    skill_started = monotonic()
    for skill_key in pack.manifest.get("skills", []):
        key = str(skill_key)
        try:
            invoked = skill_adapter.invoke(
                db,
                key,
                {
                    "persona_slug": persona.slug,
                    "stage": next_stage,
                    "user_text": user_message.content,
                    "intent": intent_payload,
                },
            )
        except (LookupError, PermissionError, ValueError) as exc:
            skill_failure = exc
            break
        result = invoked.get("result", {})
        instruction = result.get("instruction") if isinstance(result, dict) else None
        if isinstance(instruction, str) and instruction.strip():
            applied_skills.append(key)
            skill_instructions.append(instruction.strip())
            mode = result.get("mode")
            if isinstance(mode, str):
                applied_skill_modes[key] = mode
            skill_prompt_source_chars += int(result.get("source_chars", len(instruction)))
            skill_prompt_runtime_chars += int(result.get("runtime_chars", len(instruction)))
    skill_ms = int((monotonic() - skill_started) * 1000)
    context = GenerationContext(
        persona_slug=persona.slug,
        persona_name=persona.name_zh,
        persona_manifest=pack.manifest,
        persona_style=pack.style,
        stage=next_stage,
        should_ask_question=should_ask,
        user_text=user_message.content,
        recent_messages=recent_payload,
        memories=[memory.content for memory in confirmed_memories],
        knowledge=[
            {
                "document_id": hit.document.id,
                "chunk_id": hit.chunk.id if hit.chunk else hit.document.id,
                "label": (
                    f"{hit.document.citation_label} · {hit.heading}"
                    if hit.heading
                    else hit.document.citation_label
                ),
                "content": hit.content,
                "source_url": hit.document.source_url or "",
                "retrieval_method": hit.retrieval_method,
            }
            for hit in knowledge_hits
        ],
        skill_instructions=skill_instructions,
        intent_analysis=intent_payload,
    )
    # 记忆候选一旦通过 SSE 展示，确认接口就必须能在另一个事务中读到它。
    # 同时先持久化用户消息，即使后续模型连接中断也不会丢失输入。
    db.commit()
    preprocessing_ms = int((monotonic() - turn_started) * 1000)
    generation_started = monotonic()
    first_chunk_ms: int | None = None
    output: list[str] = []
    degraded = False
    provider_name = "unavailable"
    model_name = "unavailable"
    error_code: str | None = None
    yield _sse(
        "meta",
        {
            "stage": next_stage,
            "intent": {
                **intent_payload,
                "provider": intent_result.provider,
                "model": intent_result.model,
                "degraded": intent_result.degraded,
                "latency_ms": intent_result.latency_ms,
            },
            "performance": {
                "preprocessing_ms": preprocessing_ms,
                "retrieval_ms": retrieval_ms,
                "skill_ms": skill_ms,
            },
            "memory_candidate": (
                _memory_response(memory_candidate).model_dump(mode="json")
                if memory_candidate
                else None
            ),
            "applied_skills": applied_skills,
            "applied_skill_modes": applied_skill_modes,
            "skill_status": "unavailable" if skill_failure else "ready",
            "skill_prompt": {
                "source_chars": skill_prompt_source_chars,
                "runtime_chars": skill_prompt_runtime_chars,
            },
            "rag": {
                "mode": (
                    "hybrid"
                    if any(hit.retrieval_method == "hybrid_rrf" for hit in knowledge_hits)
                    else "keyword_or_vector"
                    if knowledge_hits
                    else "no_hit"
                ),
                "hit_count": len(knowledge_hits),
                "hits": [
                    {
                        "document_id": hit.document.id,
                        "chunk_id": hit.chunk.id if hit.chunk else None,
                        "method": hit.retrieval_method,
                        "keyword_rank": hit.keyword_rank,
                        "vector_rank": hit.vector_rank,
                        "vector_score": hit.vector_score,
                    }
                    for hit in knowledge_hits
                ],
            },
        },
    )
    try:
        if skill_failure is not None:
            raise RuntimeError("required_skill_unavailable") from skill_failure
        provider = get_model_provider()
        provider_name = provider.name
        model_name = provider.model
        attempt_error: Exception | None = None
        for attempt in range(get_settings().llm_retry_attempts):
            try:
                async for chunk in provider.stream(context):
                    if first_chunk_ms is None:
                        first_chunk_ms = int((monotonic() - turn_started) * 1000)
                    output.append(chunk)
                    yield _sse("chunk", {"text": chunk})
            except Exception as exc:
                attempt_error = exc
                # 已经向页面送出部分正文时不能整轮重放，否则会导致重复文本。
                if output:
                    raise
            if output:
                break
            if attempt < get_settings().llm_retry_attempts - 1:
                reason = (
                    "reasoning_without_final_content"
                    if isinstance(attempt_error, EmptyModelContentError)
                    and attempt_error.reasoning_chars > 0
                    else "empty_or_interrupted_model_stream"
                )
                yield _sse("retry", {"reason": reason, "attempt": attempt + 2})
                await asyncio.sleep(0.15 * (attempt + 1))
        if not output:
            raise attempt_error or RuntimeError("模型返回空内容")
    except Exception as exc:  # 适配器边界必须统一降级，不向客户端泄露供应商错误。
        degraded = True
        if isinstance(exc, EmptyModelContentError):
            error_code = (
                f"empty_content:{exc.finish_reason or 'unknown'}:reasoning_{exc.reasoning_chars}"
            )[:80]
        else:
            error_code = type(exc).__name__
        fallback = f"我先接住你这句“{user_message.content[:80]}”。{pack.fallback}"
        first_chunk_ms = int((monotonic() - turn_started) * 1000)
        output = [fallback]
        yield _sse("degraded", {"reason": "model_unavailable", "message": "已切换人物降级回复"})
        yield _sse("chunk", {"text": fallback})

    content = "".join(output)
    citation_items = _citation_payloads(knowledge_hits) if not degraded else []
    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        stage=next_stage,
        citations_json=json.dumps(citation_items, ensure_ascii=False),
        provider=provider_name,
        model=model_name,
        degraded=degraded,
    )
    db.add(assistant)
    db.flush()
    db.add(
        GenerationRun(
            conversation_id=conversation.id,
            message_id=assistant.id,
            provider=provider_name,
            model=model_name,
            latency_ms=int((monotonic() - generation_started) * 1000),
            success=not degraded,
            fallback_used=degraded,
            error_code=error_code,
        )
    )
    conversation.stage = next_stage
    conversation.question_streak = (
        conversation.question_streak + 1 if "？" in content or "?" in content else 0
    )
    conversation.short_summary = f"用户最近提到：{user_message.content[:120]}"
    conversation.unresolved_issue = intent_result.analysis.unresolved_issue[:500]
    conversation.last_message_at = datetime.now(UTC)
    if conversation.title.startswith("与"):
        conversation.title = user_message.content[:28]
    if next_stage == DialogueStage.END:
        conversation.status = "completed"
    db.commit()
    db.refresh(assistant)
    yield _sse(
        "done",
        {
            "message": _message_response(assistant).model_dump(mode="json"),
            "conversation_stage": conversation.stage,
            "degraded": degraded,
            "performance": {
                "preprocessing_ms": preprocessing_ms,
                "first_chunk_ms": first_chunk_ms,
                "total_ms": int((monotonic() - turn_started) * 1000),
            },
        },
    )


def _citation_payloads(hits: list[KnowledgeHit]) -> list[dict[str, str | None]]:
    return [
        {
            "document_id": hit.document.id,
            "label": (
                f"{hit.document.citation_label} · {hit.heading}"
                if hit.heading
                else hit.document.citation_label
            ),
            "source_url": hit.document.source_url,
        }
        for hit in hits
    ]


@router.post("/memories/{memory_id}/confirm", response_model=MemoryResponse)
def update_memory(
    memory_id: str,
    payload: MemoryConfirmRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MemoryResponse:
    identity = resolve_visitor(request, db)
    memory = _owned_memory(db, memory_id, identity)
    confirm_memory(memory, payload.action, payload.content)
    db.commit()
    db.refresh(memory)
    _set_visitor_cookie(response, identity)
    return _memory_response(memory)


@router.get("/memories", response_model=list[MemoryResponse])
def get_memories(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> list[MemoryResponse]:
    identity = resolve_visitor(request, db)
    memories = list(
        db.scalars(
            select(Memory)
            .where(
                Memory.user_id == identity.user.id
                if identity.user
                else Memory.visitor_id == identity.visitor.id,
                Memory.scope == "long_term",
                Memory.status.in_(("confirmed", "paused")),
            )
            .order_by(Memory.confirmed_at.desc())
        )
    )
    _set_visitor_cookie(response, identity)
    return [_memory_response(memory) for memory in memories]


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
def edit_memory(
    memory_id: str,
    payload: MemoryUpdateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MemoryResponse:
    identity = resolve_visitor(request, db)
    memory = _owned_memory(db, memory_id, identity)
    if memory.scope != "long_term" or memory.status not in {"confirmed", "paused"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该记忆不可编辑")
    if payload.content is not None:
        memory.content = payload.content.strip()
    if payload.paused is not None:
        memory.status = "paused" if payload.paused else "confirmed"
    db.commit()
    db.refresh(memory)
    _set_visitor_cookie(response, identity)
    return _memory_response(memory)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, request: Request, db: Session = Depends(get_db)) -> None:
    identity = resolve_visitor(request, db)
    memory = _owned_memory(db, memory_id, identity)
    if memory.scope != "long_term":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该记忆不可删除")
    db.delete(memory)
    db.commit()


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(db: Session = Depends(get_db)) -> list[SkillResponse]:
    skills = list(db.scalars(select(SkillConfig).order_by(SkillConfig.skill_key)))
    return [
        SkillResponse(
            skill_key=skill.skill_key,
            name=skill.name,
            version=skill.version,
            source=skill.source,
            license_name=skill.license_name,
            risk_level=skill.risk_level,
            permissions=_json_list(skill.permissions_json),
            allowlisted=skill.allowlisted,
            enabled=skill.enabled,
        )
        for skill in skills
    ]
