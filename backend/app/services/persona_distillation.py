from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    DistillationJob,
    KnowledgeChunk,
    KnowledgeDocument,
    Persona,
    PersonaClaim,
    PersonaProject,
    PersonaSourceFile,
    PersonaVersion,
)
from app.services.rag_ingest import chunk_markdown

ALLOWED_TARGET_TYPES = {
    "self",
    "authorized_private",
    "public_figure",
    "deceased",
    "composite",
    "fictional",
}
PRIVATE_VISIBILITY = "private"
_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")
_SPEAKER_RE = re.compile(r"^\s*(?:\[[^\]]{1,40}\]\s*)?([^:：]{1,30})[:：]\s*(.+?)\s*$")
_STOP_BIGRAMS = {
    "我们",
    "你们",
    "他们",
    "这个",
    "那个",
    "就是",
    "因为",
    "所以",
    "但是",
    "然后",
    "如果",
    "还是",
    "可以",
    "一个",
    "自己",
    "什么",
    "怎么",
    "觉得",
    "没有",
    "不是",
}


class DistillationInputError(ValueError):
    pass


def distill_project(
    db: Session,
    project: PersonaProject,
    *,
    owner_user_id: str,
    calibration: dict[str, str],
) -> tuple[Persona, PersonaVersion, DistillationJob]:
    sources = list(
        db.scalars(
            select(PersonaSourceFile)
            .where(PersonaSourceFile.project_id == project.id)
            .order_by(PersonaSourceFile.created_at, PersonaSourceFile.id)
        )
    )
    if not sources:
        raise DistillationInputError("请先上传至少一份人物资料")
    if any(not source.rights_confirmed for source in sources):
        raise DistillationInputError("仍有资料未确认使用权")
    if project.target_type not in ALLOWED_TARGET_TYPES:
        raise DistillationInputError("人物类型不受支持")

    extracted = [_target_text(source) for source in sources]
    combined = "\n\n".join(item for item in extracted if item.strip())
    combined = _redact_private_tokens(combined)
    if len(combined) < 800:
        raise DistillationInputError("有效人物语料不足 800 字，请补充更多真实表达")

    job = DistillationJob(
        project_id=project.id,
        stage="extracting",
        status="running",
        progress=20,
    )
    db.add(job)
    db.flush()

    project.calibration_json = json.dumps(calibration, ensure_ascii=False)
    project.source_char_count = len(combined)
    style = _style_profile(combined)
    keywords = _keywords(combined)
    examples = _representative_lines(combined)
    principles = _principles(calibration.get("core_values", ""), keywords, examples)
    quality_score = _quality_score(sources, calibration, len(combined))
    project.quality_score = quality_score
    job.stage = "building"
    job.progress = 55

    persona = _upsert_persona(db, project, owner_user_id, keywords)
    version_name = _next_version(db, persona.id)
    snapshot = _build_snapshot(
        project=project,
        persona=persona,
        version_name=version_name,
        principles=principles,
        style=style,
        keywords=keywords,
        sources=sources,
        calibration=calibration,
    )
    previous_version = (
        db.get(PersonaVersion, persona.current_version_id)
        if persona.current_version_id
        else None
    )
    if previous_version is not None:
        previous_version.status = "superseded"
    version = PersonaVersion(
        persona_id=persona.id,
        project_id=project.id,
        version=version_name,
        status="active",
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        quality_score=quality_score,
        created_by_user_id=owner_user_id,
        activated_at=datetime.now(UTC),
    )
    db.add(version)
    db.flush()
    persona.current_version_id = version.id
    persona.pack_version = version.version
    project.persona_id = persona.id

    _replace_claims(db, project, principles, style, calibration, sources)
    _store_knowledge(db, persona, version, sources, extracted)

    project.status = "ready"
    job.stage = "ready"
    job.status = "completed"
    job.progress = 100
    db.flush()
    return persona, version, job


def _target_text(source: PersonaSourceFile) -> str:
    content = source.content.strip()
    speaker = (source.target_speaker or "").strip()
    if not speaker:
        return content
    parsed: list[tuple[str, str]] = []
    for line in content.splitlines():
        match = _SPEAKER_RE.match(line)
        if match:
            parsed.append((match.group(1).strip(), match.group(2).strip()))
    if not parsed:
        return content
    selected = [text for label, text in parsed if _speaker_equal(label, speaker)]
    return "\n".join(selected)


def _speaker_equal(label: str, target: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"[\s@（）()\[\]]", "", value).lower()

    return normalize(label) == normalize(target)


def _redact_private_tokens(text: str) -> str:
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    text = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "[邮箱已隐藏]",
        text,
    )
    text = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "[证件号已隐藏]", text)
    return text


def _representative_lines(text: str, limit: int = 10) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw in _SPLIT_RE.split(text):
        value = re.sub(r"\s+", " ", raw).strip()
        if not 12 <= len(value) <= 180 or value in seen:
            continue
        seen.add(value)
        candidates.append(value)
    candidates.sort(key=lambda value: (abs(len(value) - 48), -len(value)))
    return candidates[:limit]


def _keywords(text: str, limit: int = 6) -> list[str]:
    counts: Counter[str] = Counter()
    for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for index in range(len(sequence) - 1):
            token = sequence[index : index + 2]
            if token not in _STOP_BIGRAMS:
                counts[token] += 1
    return [token for token, count in counts.most_common(limit * 3) if count >= 2][:limit]


def _style_profile(text: str) -> dict[str, Any]:
    sentences = [item.strip() for item in _SPLIT_RE.split(text) if item.strip()]
    average = round(sum(map(len, sentences)) / max(len(sentences), 1), 1)
    question_ratio = round((text.count("？") + text.count("?")) / max(len(sentences), 1), 2)
    certainty = sum(text.count(marker) for marker in ("一定", "肯定", "必须", "显然"))
    uncertainty = sum(text.count(marker) for marker in ("可能", "也许", "我觉得", "不确定"))
    sentence_length = (
        "短句、直接" if average < 24 else "中等句长、层层展开" if average < 48 else "长句、完整铺陈"
    )
    certainty_style = "判断明确" if certainty > uncertainty else "保留余地、偏审慎"
    question_policy = "会用问题推动对话" if question_ratio >= 0.12 else "更常先陈述判断再解释"
    return {
        "tone": f"{sentence_length}；{certainty_style}；{question_policy}",
        "sentence_length": sentence_length,
        "question_policy": question_policy,
        "preferred_moves": ["复述具体处境", "调用资料中的判断方式", "给出一个可行动的下一步"],
        "metrics": {
            "average_sentence_chars": average,
            "question_ratio": question_ratio,
            "certainty_markers": certainty,
            "uncertainty_markers": uncertainty,
        },
    }


def _split_values(value: str) -> list[str]:
    items = [item.strip() for item in re.split(r"[，,、；;\n]+", value) if item.strip()]
    return list(dict.fromkeys(items))[:7]


def _principles(core_values: str, keywords: list[str], examples: list[str]) -> list[dict[str, str]]:
    values = _split_values(core_values)
    if not values:
        values = [f"重视{keyword}" for keyword in keywords[:3]]
    if not values:
        values = ["从具体经验出发", "先理解处境再判断", "保留不知道的空间"]
    while len(values) < 3:
        fallback = ["从具体经验出发", "把判断落到行动", "承认资料边界"]
        values.append(next(item for item in fallback if item not in values))
    principles: list[dict[str, str]] = []
    for index, value in enumerate(values[:7], start=1):
        evidence = examples[(index - 1) % len(examples)] if examples else "来自上传资料的综合提炼"
        principles.append(
            {
                "id": f"distilled-{index}",
                "name": value[:40],
                "meaning": f"把“{value[:60]}”作为理解问题和排序选择的重要依据。",
                "dialogue_use": "结合用户的具体问题使用，资料不足时明确说明是框架推断。",
                "evidence_excerpt": evidence,
            }
        )
    return principles


def _quality_score(
    sources: list[PersonaSourceFile], calibration: dict[str, str], char_count: int
) -> int:
    if char_count >= 100_000:
        volume = 35
    elif char_count >= 30_000:
        volume = 30
    elif char_count >= 5_000:
        volume = 22
    elif char_count >= 2_000:
        volume = 14
    else:
        volume = 8
    score = volume
    score += min(len(sources) * 4, 15)
    score += 15 if calibration.get("core_values", "").strip() else 0
    score += 15 if calibration.get("decision_case", "").strip() else 0
    score += 10 if calibration.get("never_do", "").strip() else 0
    score += 5 if calibration.get("unlike_response", "").strip() else 0
    score += 3 if any(source.time_range for source in sources) else 0
    score += 2 if any(source.target_speaker for source in sources) else 0
    return min(score, 100)


def _upsert_persona(
    db: Session,
    project: PersonaProject,
    owner_user_id: str,
    keywords: list[str],
) -> Persona:
    persona = db.get(Persona, project.persona_id) if project.persona_id else None
    if persona is None:
        persona = Persona(slug=f"created-{project.id[:12]}")
        db.add(persona)
    persona.name_zh = project.name
    persona.name_en = "Personal Digital Persona"
    persona.era = "当代" if project.target_type != "deceased" else "资料所载时期"
    persona.region = "个人空间"
    persona.domains_json = json.dumps(["个人数字人"], ensure_ascii=False)
    persona.topics_json = json.dumps(keywords or ["人生经验", "选择", "关系"], ensure_ascii=False)
    persona.dilemmas_json = json.dumps(
        ["想听听他的判断", "回顾共同经历", "换一个熟悉的角度"],
        ensure_ascii=False,
    )
    persona.short_intro = f"基于创建者上传资料生成，用{project.name}留下的表达与判断方式陪你对话。"
    persona.avatar_tone = "cinnabar"
    persona.chat_tier = "B"
    persona.status = "active"
    persona.is_living = project.target_type in {"self", "authorized_private", "public_figure"}
    persona.owner_user_id = owner_user_id
    persona.origin_type = "user_created"
    persona.visibility = PRIVATE_VISIBILITY
    db.flush()
    return persona


def _next_version(db: Session, persona_id: str) -> str:
    count = (
        db.scalar(
            select(func.count())
            .select_from(PersonaVersion)
            .where(PersonaVersion.persona_id == persona_id)
        )
        or 0
    )
    return "1.0.0" if count == 0 else f"1.{count}.0"


def _build_snapshot(
    *,
    project: PersonaProject,
    persona: Persona,
    version_name: str,
    principles: list[dict[str, str]],
    style: dict[str, Any],
    keywords: list[str],
    sources: list[PersonaSourceFile],
    calibration: dict[str, str],
) -> dict[str, Any]:
    boundary = "这是根据创建者提供资料生成的数字人物，不是真人本人；资料之外的回答属于框架推断。"
    manifest = {
        "id": persona.id,
        "version": version_name,
        "status": "active",
        "tier": "B",
        "profile": {
            "slug": persona.slug,
            "name_zh": persona.name_zh,
            "name_en": persona.name_en,
            "era": persona.era,
            "region": persona.region,
            "domains": ["个人数字人"],
            "topics": keywords or ["人生经验", "选择", "关系"],
            "dilemmas": ["想听听他的判断", "回顾共同经历", "换一个熟悉的角度"],
            "short_intro": persona.short_intro,
            "avatar_tone": persona.avatar_tone,
            "is_living": persona.is_living,
        },
        "identity": {
            "role": f"在私人思想对话中，以{project.name}资料呈现出的表达与判断方式直接回应。",
            "historical_context": "仅覆盖创建者本次上传资料所涉及的时期。",
            "source_basis": f"{len(sources)} 份创建者上传资料。",
            "simulation_boundary": boundary,
        },
        "principles": principles,
        "language_style": style,
        "forbidden_behaviors": [
            "不得声称是真人本人或拥有真人意识",
            "不得把资料未覆盖的内容伪装成真人原话",
            "不得向其他用户泄露创建者上传的原始私密资料",
        ],
        "proactive_strategy": {
            "opening_goal": "从创建者设定的用途和熟悉话题开始",
            "identify_goal": "理解用户当前真正想讨论的处境",
            "clarify_goal": "调用资料中的判断方式澄清选择",
            "guidance_goal": "提供有依据且具体的看法",
            "reflection_goal": "保留用户自己的决定权",
            "end_goal": "总结判断和下一步",
            "max_question_streak": 2,
        },
        "memory_strategy": {
            "read_scope": "仅读取当前用户与当前数字人物已确认的关系记忆",
            "write_policy": "用户确认后才保存跨会话记忆",
            "never_store": ["证件信息", "密码与密钥", "精确住址"],
        },
        "skills": [],
        "disclaimer": boundary,
        "calibration": calibration,
    }
    opening = (
        f"我已经读过你为“{project.name}”整理的资料。{project.purpose[:80]}，"
        "我们就从你此刻最想谈的那件事开始。"
    )
    return {
        "manifest": manifest,
        "starters": [
            {
                "text": opening,
                "quick_replies": ["我想听听你的判断", "我们回顾一件以前的事", "我正卡在一个选择上"],
            }
        ],
        "sources": [
            {
                "title": source.filename,
                "citation_label": f"创建者上传资料 · {source.filename}",
                "source_url": None,
                "license_note": "内测私有资料；仅当前创建者可使用。",
            }
            for source in sources
        ],
        "style": style["tone"],
        "fallback": f"这部分资料还不足以替“{project.name}”下结论。把你最在意的事实再告诉我一点。",
    }


def _replace_claims(
    db: Session,
    project: PersonaProject,
    principles: list[dict[str, str]],
    style: dict[str, Any],
    calibration: dict[str, str],
    sources: list[PersonaSourceFile],
) -> None:
    db.execute(delete(PersonaClaim).where(PersonaClaim.project_id == project.id))
    source_refs = [{"source_id": source.id, "filename": source.filename} for source in sources]
    for principle in principles:
        db.add(
            PersonaClaim(
                project_id=project.id,
                claim_type="principle",
                content=principle["meaning"],
                confidence=75 if calibration.get("core_values", "").strip() else 58,
                review_status="suggested",
                evidence_json=json.dumps(source_refs, ensure_ascii=False),
            )
        )
    db.add(
        PersonaClaim(
            project_id=project.id,
            claim_type="style",
            content=str(style["tone"]),
            confidence=70,
            review_status="suggested",
            evidence_json=json.dumps(source_refs, ensure_ascii=False),
        )
    )
    for field, claim_type in (("decision_case", "decision"), ("never_do", "boundary")):
        content = calibration.get(field, "").strip()
        if content:
            db.add(
                PersonaClaim(
                    project_id=project.id,
                    claim_type=claim_type,
                    content=content,
                    confidence=85,
                    review_status="creator_provided",
                    evidence_json="[]",
                )
            )


def _store_knowledge(
    db: Session,
    persona: Persona,
    version: PersonaVersion,
    sources: list[PersonaSourceFile],
    extracted: list[str],
) -> None:
    for source, content in zip(sources, extracted, strict=True):
        safe_content = _redact_private_tokens(content)
        document = KnowledgeDocument(
            persona_id=persona.id,
            persona_version_id=version.id,
            title=source.filename,
            source_type="private_creator_upload",
            source_url=None,
            citation_label=f"创建者上传资料 · {source.filename}",
            license_note="内测私有资料；仅当前创建者可使用。",
            content=safe_content,
            metadata_json=json.dumps(
                {
                    "source_file_id": source.id,
                    "content_sha256": hashlib.sha256(safe_content.encode()).hexdigest(),
                    "target_speaker": source.target_speaker,
                    "time_range": source.time_range,
                },
                ensure_ascii=False,
            ),
            enabled=True,
        )
        db.add(document)
        db.flush()
        for index, chunk in enumerate(chunk_markdown(safe_content, 520, 80)):
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    persona_id=persona.id,
                    persona_version_id=version.id,
                    chunk_index=index,
                    heading=chunk.heading,
                    content=chunk.content,
                    content_hash=hashlib.sha256(chunk.content.encode()).hexdigest(),
                    citation_label=document.citation_label,
                    source_url=None,
                    metadata_json=json.dumps(
                        {"start_char": chunk.start_char, "end_char": chunk.end_char},
                        ensure_ascii=False,
                    ),
                    enabled=True,
                )
            )
