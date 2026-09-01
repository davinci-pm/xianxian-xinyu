from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import (
    PersonaCognitiveArtifact,
    PersonaEvidenceUnit,
    PersonaFeedback,
    PersonaProject,
    PersonaSourceFile,
)
from app.services.chat_corpus import extract_target_messages, parse_chat_turns

PIPELINE_VERSION = "nuwa-soul-v3"

_SPEAKER_RE = re.compile(r"^\s*(?:\[[^\]]{1,40}\]\s*)?([^:：]{1,30})[:：]\s*(.+?)\s*$")
_SEGMENT_RE = re.compile(r"[^。！？!?\uff1b;\n]+(?:[。！？!?\uff1b;]+|\n|$)")
_YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
_DECISION_MARKERS = (
    "因为",
    "所以",
    "决定",
    "选择",
    "宁愿",
    "如果",
    "取舍",
    "代价",
    "风险",
    "放弃",
    "更重要",
    "后来",
    "结果",
)
_EVENT_MARKERS = (
    "开始",
    "加入",
    "离开",
    "创立",
    "创业",
    "发布",
    "成为",
    "收购",
    "发生",
    "推出",
    "遇到",
)
_CHANGE_MARKERS = (
    "以前",
    "曾经",
    "后来",
    "现在",
    "不再",
    "改变",
    "转变",
    "但是",
    "却",
    "反而",
)
_NEGATIONS = ("不", "没", "从未", "不会", "不能", "放弃", "反对")
_VALUE_MARKERS = (
    "长期",
    "诚实",
    "信任",
    "责任",
    "自由",
    "公平",
    "效率",
    "速度",
    "规模",
    "用户",
    "家庭",
    "创造",
    "真实",
    "边界",
)


@dataclass(frozen=True)
class LayerReport:
    key: str
    label: str
    status: str
    count: int
    detail: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "count": self.count,
            "detail": self.detail,
        }


def _normalise_speaker(value: str) -> str:
    return re.sub(r"[\s@（）()\[\]]", "", value).lower()


def _target_text(source: PersonaSourceFile) -> str:
    content = source.content.replace("\x00", "").strip()
    target = (source.target_speaker or "").strip()
    if not target:
        return content
    if source.source_type == "chat":
        return extract_target_messages(content, target)
    parsed = [
        (match.group(1).strip(), match.group(2).strip())
        for line in content.splitlines()
        if (match := _SPEAKER_RE.match(line))
    ]
    if not parsed:
        return content
    selected = [
        text
        for speaker, text in parsed
        if _normalise_speaker(speaker) == _normalise_speaker(target)
    ]
    return "\n".join(selected)


def _redact(text: str) -> str:
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    text = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "[邮箱已隐藏]",
        text,
    )
    return re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "[证件号已隐藏]", text)


def _semantic_segments(text: str, *, limit: int = 520) -> list[tuple[str, int, int]]:
    pieces = [
        (match.group().strip(), match.start(), match.end())
        for match in _SEGMENT_RE.finditer(text)
        if match.group().strip()
    ]
    segments: list[tuple[str, int, int]] = []
    buffer: list[str] = []
    start = 0
    end = 0

    def flush() -> None:
        nonlocal buffer
        content = "".join(buffer).strip()
        if content:
            segments.append((content, start, end))
        buffer = []

    for piece, piece_start, piece_end in pieces:
        if len(piece) > limit:
            flush()
            for offset in range(0, len(piece), limit):
                chunk = piece[offset : offset + limit].strip()
                if chunk:
                    segments.append(
                        (chunk, piece_start + offset, min(piece_start + offset + limit, piece_end))
                    )
            continue
        buffered_chars = sum(map(len, buffer))
        if buffer and buffered_chars + len(piece) > limit:
            flush()
        if not buffer:
            start = piece_start
        buffer.append(piece)
        end = piece_end
    flush()
    return [(content, start, end) for content, start, end in segments if len(content) >= 20]


def _content_fingerprint(text: str) -> str:
    compact = re.sub(r"[^\w\u4e00-\u9fff]", "", text).lower()
    return hashlib.sha256(compact.encode()).hexdigest()


def _simhash(text: str) -> int:
    compact = re.sub(r"\s+", "", text.lower())
    tokens = [compact[index : index + 3] for index in range(max(len(compact) - 2, 1))]
    weights = [0] * 64
    for token in tokens:
        value = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if value & (1 << bit) else -1
    return sum(1 << bit for bit, weight in enumerate(weights) if weight >= 0)


def _quality_score(content: str, source: PersonaSourceFile, time_range: str | None) -> int:
    score = 35
    score += min(25, len(content) // 20)
    score += 15 if source.target_speaker else 5
    score += 10 if time_range else 0
    score += 15 if any(marker in content for marker in _DECISION_MARKERS) else 0
    return min(score, 100)


def build_evidence_layer(
    db: Session,
    project: PersonaProject,
    sources: list[PersonaSourceFile],
) -> tuple[list[PersonaEvidenceUnit], LayerReport]:
    db.execute(
        delete(PersonaCognitiveArtifact).where(PersonaCognitiveArtifact.project_id == project.id)
    )
    db.execute(delete(PersonaEvidenceUnit).where(PersonaEvidenceUnit.project_id == project.id))
    db.flush()

    exact_groups: dict[str, str] = {}
    simhash_buckets: defaultdict[int, list[tuple[int, str]]] = defaultdict(list)
    units: list[PersonaEvidenceUnit] = []
    duplicates = 0
    for source in sources:
        text = _redact(_target_text(source))
        segments: list[tuple[str, int, int, dict[str, Any]]] = []
        if source.source_type == "chat" and source.target_speaker:
            target = _normalise_speaker(source.target_speaker)
            for turn in parse_chat_turns(source.content):
                if _normalise_speaker(turn.speaker) != target or len(turn.content) < 12:
                    continue
                safe_content = _redact(turn.content)
                segments.append(
                    (
                        safe_content,
                        0,
                        len(safe_content),
                        {
                            "context_before": _redact(turn.context_before or "")[:500],
                            "chat_session_index": turn.session_index,
                            "chat_timestamp": turn.timestamp,
                        },
                    )
                )
        if not segments:
            segments = [
                (content, start, end, {})
                for content, start, end in _semantic_segments(text)
            ]
        for content, start, end, segment_metadata in segments:
            fingerprint = _content_fingerprint(content)
            signature = _simhash(content)
            bucket = signature >> 52
            duplicate_group = exact_groups.get(fingerprint)
            if duplicate_group is None:
                near = next(
                    (
                        group
                        for candidate, group in simhash_buckets[bucket]
                        if (candidate ^ signature).bit_count() <= 4
                    ),
                    None,
                )
                duplicate_group = near or fingerprint
            review_status = (
                "duplicate"
                if duplicate_group != fingerprint or fingerprint in exact_groups
                else "active"
            )
            if review_status == "duplicate":
                duplicates += 1
            exact_groups.setdefault(fingerprint, duplicate_group)
            simhash_buckets[bucket].append((signature, duplicate_group))
            years = _YEAR_RE.findall(content)
            time_range = (
                "-".join(list(dict.fromkeys(years))[:2])
                if years
                else source.published_at or source.time_range
            )
            unit = PersonaEvidenceUnit(
                project_id=project.id,
                source_file_id=source.id,
                speaker=source.target_speaker,
                content=content,
                content_hash=fingerprint,
                duplicate_group=duplicate_group,
                source_type=source.source_type,
                time_range=time_range,
                source_url=source.source_url,
                start_char=start,
                end_char=end,
                quality_score=_quality_score(content, source, time_range),
                review_status=review_status,
                metadata_json=json.dumps(
                    {
                        "filename": source.filename,
                        "published_at": source.published_at,
                        "speaker_separated": bool(source.target_speaker),
                        "years_in_text": years,
                        **segment_metadata,
                    },
                    ensure_ascii=False,
                ),
            )
            db.add(unit)
            units.append(unit)
    holdout_candidates = [
        unit
        for unit in units
        if unit.review_status == "active"
        and unit.source_type == "chat"
        and json.loads(unit.metadata_json).get("context_before")
    ]
    if len(holdout_candidates) >= 8:
        holdout_count = max(1, min(12, len(holdout_candidates) // 8))
        for unit in sorted(holdout_candidates, key=lambda item: item.content_hash)[-holdout_count:]:
            unit.review_status = "holdout"
    db.flush()
    active = sum(unit.review_status == "active" for unit in units)
    holdout = sum(unit.review_status == "holdout" for unit in units)
    return units, LayerReport(
        key="evidence",
        label="证据层",
        status="completed",
        count=active,
        detail=(
            f"形成 {active} 个可追溯训练证据单元，隔离 {holdout} 个盲测回复，"
            f"标记 {duplicates} 个重复片段"
        ),
    )


def _best_evidence(units: list[PersonaEvidenceUnit], phrase: str) -> list[PersonaEvidenceUnit]:
    tokens = {
        phrase[index : index + 2]
        for index in range(max(len(phrase) - 1, 0))
        if phrase[index : index + 2].strip()
    }
    return sorted(
        units,
        key=lambda unit: (
            -sum(token in unit.content for token in tokens),
            -unit.quality_score,
        ),
    )[:2]


def _add_artifact(
    db: Session,
    project_id: str,
    artifact_type: str,
    title: str,
    content: dict[str, Any],
    evidence: list[PersonaEvidenceUnit],
    *,
    confidence: int,
    time_range: str | None = None,
    review_status: str = "suggested",
) -> PersonaCognitiveArtifact:
    artifact = PersonaCognitiveArtifact(
        project_id=project_id,
        artifact_type=artifact_type,
        title=title[:160],
        content_json=json.dumps(content, ensure_ascii=False),
        confidence=confidence,
        evidence_json=json.dumps(
            [
                {
                    "evidence_id": item.id,
                    "source_file_id": item.source_file_id,
                    "excerpt": item.content[:220],
                }
                for item in evidence
            ],
            ensure_ascii=False,
        ),
        time_range=time_range
        or next((item.time_range for item in evidence if item.time_range), None),
        review_status=review_status,
    )
    db.add(artifact)
    return artifact


def _extract_decision(content: str) -> dict[str, str]:
    condition = next(
        (
            part.strip()
            for part in re.split(r"[，,。]", content)
            if part.strip().startswith(("如果", "当", "面对"))
        ),
        "",
    )
    reason_match = re.search(r"因为(.{4,90}?)(?:所以|[。；;]|$)", content)
    choice_match = re.search(r"(?:决定|选择|宁愿|会)(.{4,90}?)(?:[。；;]|$)", content)
    tradeoff_match = re.search(r"(?:放弃|代价|取舍)(.{3,70}?)(?:[。；;]|$)", content)
    return {
        "situation": condition,
        "choice": choice_match.group(1).strip() if choice_match else content[:100],
        "reason": reason_match.group(1).strip() if reason_match else "",
        "tradeoff": tradeoff_match.group(1).strip() if tradeoff_match else "",
        "outcome": "",
        "source_text": content,
    }


def build_cognitive_layer(
    db: Session,
    project: PersonaProject,
    evidence_units: list[PersonaEvidenceUnit],
    calibration: dict[str, str],
    keywords: list[str],
    accepted_feedback: list[PersonaFeedback],
) -> tuple[list[PersonaCognitiveArtifact], dict[str, Any], LayerReport]:
    active = [unit for unit in evidence_units if unit.review_status == "active"]
    artifacts: list[PersonaCognitiveArtifact] = []

    values = [
        item.strip()
        for item in re.split(r"[，,、；;\n]+", calibration.get("core_values", ""))
        if item.strip()
    ]
    if not values:
        value_counts = Counter(
            marker for marker in _VALUE_MARKERS for unit in active if marker in unit.content
        )
        values = [value for value, _count in value_counts.most_common(6)] or keywords[:4]
    for priority, value in enumerate(values[:7], 1):
        evidence = _best_evidence(active, value)
        artifact = _add_artifact(
            db,
            project.id,
            "value",
            value,
            {
                "value": value,
                "priority": priority,
                "meaning": f"当多个目标冲突时，将“{value}”作为第 {priority} 级判断依据。",
                "source": "creator_calibration"
                if calibration.get("core_values", "").strip()
                else "corpus",
            },
            evidence,
            confidence=88 if calibration.get("core_values", "").strip() else 64,
            review_status="creator_provided"
            if calibration.get("core_values", "").strip()
            else "suggested",
        )
        artifacts.append(artifact)

    calibrated_decision = calibration.get("decision_case", "").strip()
    if calibrated_decision:
        calibrated_evidence = _best_evidence(active, calibrated_decision)
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "decision",
                "创建者校准的典型决策",
                _extract_decision(calibrated_decision),
                calibrated_evidence,
                confidence=90,
                review_status="creator_provided",
            )
        )
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "conditional_rule",
                "从典型决策归纳的条件规则",
                {
                    "condition": "面对与校准案例类似的选择时",
                    "preferred_action": calibrated_decision,
                    "reason": "来自创建者确认的典型决策。",
                    "exceptions": [],
                },
                calibrated_evidence,
                confidence=86,
                review_status="creator_provided",
            )
        )
    for field, artifact_type, title in (
        ("never_do", "boundary", "创建者校准的价值底线"),
        ("unlike_response", "negative_example", "最不像该人物的回答反例"),
    ):
        content = calibration.get(field, "").strip()
        if content:
            artifacts.append(
                _add_artifact(
                    db,
                    project.id,
                    artifact_type,
                    title,
                    {"content": content, "source": "creator_calibration"},
                    _best_evidence(active, content),
                    confidence=90,
                    review_status="creator_provided",
                )
            )

    decision_units = sorted(
        (unit for unit in active if any(marker in unit.content for marker in _DECISION_MARKERS)),
        key=lambda unit: (-unit.quality_score, unit.start_char),
    )[:24]
    for index, unit in enumerate(decision_units, 1):
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "decision",
                f"决策样本 {index}",
                _extract_decision(unit.content),
                [unit],
                confidence=min(90, 55 + unit.quality_score // 3),
            )
        )

    event_units = [
        unit
        for unit in active
        if _YEAR_RE.search(unit.content)
        and any(marker in unit.content for marker in _EVENT_MARKERS)
    ][:16]
    for index, unit in enumerate(event_units, 1):
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "event",
                f"事件 {index}",
                {"event": unit.content, "years": _YEAR_RE.findall(unit.content)},
                [unit],
                confidence=75,
            )
        )

    rule_units = [
        unit
        for unit in decision_units
        if any(marker in unit.content for marker in ("如果", "当", "面对", "只要"))
    ][:14]
    for index, unit in enumerate(rule_units, 1):
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "conditional_rule",
                f"条件化规则 {index}",
                {
                    "condition": _extract_decision(unit.content)["situation"],
                    "preferred_action": _extract_decision(unit.content)["choice"],
                    "reason": _extract_decision(unit.content)["reason"],
                    "exceptions": [],
                },
                [unit],
                confidence=72,
            )
        )

    change_units = [
        unit for unit in active if sum(marker in unit.content for marker in _CHANGE_MARKERS) >= 2
    ][:12]
    for index, unit in enumerate(change_units, 1):
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "change",
                f"观点变化 {index}",
                {
                    "before_after_evidence": unit.content,
                    "change_reason": "资料显示存在时间或立场转变，需要人工确认原因。",
                },
                [unit],
                confidence=62,
            )
        )

    # Conservative contradiction candidates: require a shared value/topic and
    # opposite negation polarity. They remain suggested until reviewed.
    candidates = active[:80]
    contradiction_count = 0
    for left_index, left in enumerate(candidates):
        if contradiction_count >= 8:
            break
        left_polarity = any(marker in left.content for marker in _NEGATIONS)
        for right in candidates[left_index + 1 :]:
            right_polarity = any(marker in right.content for marker in _NEGATIONS)
            shared = [
                marker
                for marker in (*_VALUE_MARKERS, *keywords)
                if marker and marker in left.content and marker in right.content
            ]
            if left_polarity == right_polarity or not shared:
                continue
            artifacts.append(
                _add_artifact(
                    db,
                    project.id,
                    "contradiction",
                    f"待核验矛盾：{shared[0]}",
                    {
                        "topic": shared[0],
                        "positions": [left.content, right.content],
                        "resolution": "检查是时间变化、情境差异还是真实矛盾。",
                    },
                    [left, right],
                    confidence=48,
                )
            )
            contradiction_count += 1
            break

    for feedback in accepted_feedback:
        artifacts.append(
            _add_artifact(
                db,
                project.id,
                "correction",
                "创建者已审核纠正",
                {"feedback_type": feedback.feedback_type, "content": feedback.content},
                [],
                confidence=95,
                review_status="approved",
            )
        )

    db.flush()
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for artifact in artifacts:
        grouped[artifact.artifact_type].append(
            {
                "id": artifact.id,
                "title": artifact.title,
                "confidence": artifact.confidence,
                "time_range": artifact.time_range,
                "review_status": artifact.review_status,
                **json.loads(artifact.content_json),
                "evidence_ids": [
                    item.get("evidence_id")
                    for item in json.loads(artifact.evidence_json)
                    if isinstance(item, dict)
                ],
            }
        )
    cognitive_model = {
        "value_hierarchy": grouped["value"],
        "decision_samples": grouped["decision"],
        "conditional_rules": grouped["conditional_rule"],
        "events": grouped["event"],
        "changes": grouped["change"],
        "contradictions": grouped["contradiction"],
        "boundaries": grouped["boundary"],
        "negative_examples": grouped["negative_example"],
        "approved_corrections": grouped["correction"],
    }
    return (
        artifacts,
        cognitive_model,
        LayerReport(
            key="cognition",
            label="认知层",
            status="completed",
            count=len(artifacts),
            detail=(
                f"提取 {len(grouped['decision'])} 个决策样本、"
                f"{len(grouped['conditional_rule'])} 条条件规则、"
                f"{len(grouped['change']) + len(grouped['contradiction'])} 个变化或矛盾候选"
            ),
        ),
    )


def build_evaluation_blueprint(
    evidence_units: list[PersonaEvidenceUnit],
    artifacts: list[PersonaCognitiveArtifact],
    source_count: int,
) -> tuple[dict[str, int], list[dict[str, Any]], int, LayerReport]:
    active = [unit for unit in evidence_units if unit.review_status == "active"]
    holdout = [unit for unit in evidence_units if unit.review_status == "holdout"]
    type_counts = Counter(artifact.artifact_type for artifact in artifacts)
    traced = sum(bool(json.loads(artifact.evidence_json)) for artifact in artifacts)
    dimensions = {
        "evidence_traceability": round(100 * traced / max(len(artifacts), 1)),
        "speaker_integrity": round(
            100 * sum(bool(unit.speaker) for unit in active) / max(len(active), 1)
        ),
        "temporal_coverage": round(
            100 * sum(bool(unit.time_range) for unit in active) / max(len(active), 1)
        ),
        "decision_depth": min(100, type_counts["decision"] * 6),
        "conditional_reasoning": min(100, type_counts["conditional_rule"] * 10),
        "change_awareness": min(100, (type_counts["change"] + type_counts["contradiction"]) * 12),
        "source_diversity": min(100, source_count * 25),
        "holdout_readiness": min(100, len(holdout) * 25),
    }
    weights = {
        "evidence_traceability": 0.20,
        "speaker_integrity": 0.14,
        "temporal_coverage": 0.12,
        "decision_depth": 0.20,
        "conditional_reasoning": 0.14,
        "change_awareness": 0.10,
        "source_diversity": 0.06,
        "holdout_readiness": 0.04,
    }
    score = round(sum(dimensions[key] * weight for key, weight in weights.items()))
    generic_cases: list[dict[str, Any]] = [
        {"category": "origin", "question": "你为什么走上这条路？", "expected_mode": "fact"},
        {
            "category": "decision",
            "question": "短期利益与长期目标冲突时怎么选？",
            "expected_mode": "mixed",
        },
        {
            "category": "counterfactual",
            "question": "如果关键条件反过来，你还会这样选吗？",
            "expected_mode": "inference",
        },
        {
            "category": "change",
            "question": "你这些年改变最大的看法是什么？",
            "expected_mode": "fact",
        },
        {
            "category": "unknown",
            "question": "说一件从未公开的私人经历。",
            "expected_mode": "insufficient",
        },
        {
            "category": "style",
            "question": "给一个今天就能执行的建议。",
            "expected_mode": "inference",
        },
    ]
    holdout_cases: list[dict[str, Any]] = []
    for unit in holdout:
        metadata = json.loads(unit.metadata_json)
        context_before = str(metadata.get("context_before", "")).strip()
        if not context_before:
            continue
        holdout_cases.append(
            {
                "category": "dialogue_holdout",
                "question": context_before,
                "expected_mode": "inference",
                "expected_response": unit.content,
                "evidence_id": unit.id,
                "excluded_from_training": True,
                "rubric": ["semantic_choice", "voice_style", "boundary_integrity"],
            }
        )
    cases = holdout_cases + generic_cases
    return (
        dimensions,
        cases,
        score,
        LayerReport(
            key="learning",
            label="学习层",
            status="completed",
            count=len(cases),
            detail=(
                f"生成 {len(generic_cases)} 类边界回归题与 {len(holdout_cases)} 条真实盲测题，"
                f"当前 {score} 分仅表示结构完备度"
            ),
        ),
    )


def retrieval_layer_report(evidence_units: list[PersonaEvidenceUnit]) -> LayerReport:
    active = [unit for unit in evidence_units if unit.review_status == "active"]
    temporal = sum(bool(unit.time_range) for unit in active)
    return LayerReport(
        key="retrieval",
        label="检索层",
        status="completed",
        count=len(active),
        detail=f"BM25 + Embedding 候选已建索引，{temporal} 段证据可进行时间过滤",
    )


def generation_layer_report(cognitive_model: dict[str, Any]) -> LayerReport:
    constraints = sum(len(items) for items in cognitive_model.values())
    return LayerReport(
        key="generation",
        label="生成层",
        status="completed",
        count=constraints,
        detail=f"已装载问题规划、事实/推演分类与 {constraints} 条人格约束",
    )
