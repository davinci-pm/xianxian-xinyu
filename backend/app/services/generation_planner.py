from __future__ import annotations

import re
from typing import Any

from app.services.knowledge import KnowledgeHit

_FACT_MARKERS = (
    "什么时候",
    "哪一年",
    "发生了什么",
    "经历",
    "生平",
    "为什么当时",
    "为什么进入",
    "为什么创立",
    "合作",
    "说过",
)
_INFERENCE_MARKERS = (
    "你会怎么",
    "你会建议",
    "如果",
    "假如",
    "怎么选",
    "怎么做",
    "应该",
)
_INSUFFICIENT_MARKERS = (
    "从未公开",
    "未公开",
    "私人经历",
    "内幕",
    "秘密",
    "现在正在",
    "实时状态",
)
_DELIBERATION_MARKERS = (
    "选择",
    "决定",
    "冲突",
    "两难",
    "权衡",
    "取舍",
    "风险",
    "长期",
    "该不该",
    "还是",
    "如果",
)
_CHANGE_QUERY_MARKERS = ("改变", "变化", "矛盾", "前后", "以前", "后来", "现在怎么看")


def _compact_asset(item: dict[str, Any]) -> dict[str, Any]:
    excluded = {"id", "evidence_ids", "source_text", "positions"}
    compact: dict[str, Any] = {}
    for key, value in item.items():
        if key in excluded:
            continue
        if isinstance(value, str):
            compact[key] = value[:260]
        elif isinstance(value, (int, float, bool)) or value is None:
            compact[key] = value
        elif isinstance(value, list):
            compact[key] = [str(entry)[:180] for entry in value[:3]]
    return compact


def _terms(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", text.lower())
    chinese = {
        compact[index : index + 2]
        for index in range(max(len(compact) - 1, 0))
        if re.search(r"[\u4e00-\u9fff]", compact[index : index + 2])
    }
    latin = set(re.findall(r"[a-z0-9]{3,}", compact))
    return chinese | latin


def _activate_assets(
    user_text: str,
    cognitive_model: dict[str, Any],
    *,
    limit: int = 7,
) -> dict[str, list[dict[str, Any]]]:
    query_terms = _terms(user_text)
    category_priority = {
        "approved_corrections": 8,
        "boundaries": 7,
        "negative_examples": 6,
        "conditional_rules": 5,
        "decision_samples": 4,
        "value_hierarchy": 3,
        "changes": 2,
        "contradictions": 2,
        "events": 1,
    }
    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    asks_change = any(marker in user_text for marker in _CHANGE_QUERY_MARKERS)
    asks_event = any(marker in user_text for marker in _FACT_MARKERS) or bool(
        re.search(r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)", user_text)
    )
    for category, raw_items in cognitive_model.items():
        if not isinstance(raw_items, list):
            continue
        if category in {"changes", "contradictions"} and not asks_change:
            continue
        if category == "events" and not asks_event:
            continue
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            searchable = " ".join(str(value) for value in item.values())
            overlap = len(query_terms & _terms(searchable))
            confidence = int(item.get("confidence", 0) or 0)
            score = overlap * 20 + category_priority.get(category, 0) + confidence // 20
            if overlap or category in {"approved_corrections", "boundaries"}:
                ranked.append((score, -index, category, item))
    if not any(category == "value_hierarchy" for _score, _index, category, _item in ranked):
        values = cognitive_model.get("value_hierarchy", [])
        if isinstance(values, list):
            fallback = next((item for item in values if isinstance(item, dict)), None)
            if fallback:
                ranked.append((1, 0, "value_hierarchy", fallback))
    category_limits = {
        "approved_corrections": 1,
        "boundaries": 1,
        "negative_examples": 1,
        "conditional_rules": 2,
        "decision_samples": 2,
        "value_hierarchy": 1,
        "events": 2,
        "changes": 1,
        "contradictions": 1,
    }
    selected: dict[str, list[dict[str, Any]]] = {}
    for _score, _index, category, item in sorted(ranked, reverse=True):
        if sum(map(len, selected.values())) >= limit:
            break
        if len(selected.get(category, [])) >= category_limits.get(category, 1):
            continue
        selected.setdefault(category, []).append(_compact_asset(item))
    return selected


def _subquestions(text: str) -> list[str]:
    items = [item.strip(" ，,。；;") for item in re.split(r"[？?]+", text) if item.strip()]
    return items[:4] or [text.strip()]


def _coverage(question: str, hits: list[KnowledgeHit]) -> int:
    terms = {
        question[index : index + 2]
        for index in range(max(len(question) - 1, 0))
        if re.search(r"[\u4e00-\u9fffA-Za-z0-9]", question[index : index + 2])
    }
    if not terms or not hits:
        return 0
    matched = sum(any(term in hit.content for hit in hits) for term in terms)
    return round(100 * matched / len(terms))


def plan_generation(
    user_text: str,
    hits: list[KnowledgeHit],
    cognitive_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    asks_fact = any(marker in user_text for marker in _FACT_MARKERS) or bool(
        re.search(r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)", user_text)
    )
    asks_inference = any(marker in user_text for marker in _INFERENCE_MARKERS)
    explicitly_unavailable = any(marker in user_text for marker in _INSUFFICIENT_MARKERS)
    mode = (
        "insufficient"
        if explicitly_unavailable
        else "mixed"
        if asks_fact and asks_inference
        else "fact"
        if asks_fact
        else "inference"
    )
    coverage = _coverage(user_text, hits)
    direct_evidence = bool(hits) and coverage >= 12
    if mode == "fact" and not direct_evidence:
        answer_policy = "先明确说资料没有直接覆盖，再提供已知的相关证据，不补写动机或细节。"
    elif mode == "insufficient":
        answer_policy = "明确说明资料边界，不生成未公开事实；可转向最相关的公开判断。"
    elif mode == "inference":
        answer_policy = "用认知模型的价值排序和条件规则推演，不得把推演写成本人经历。"
    else:
        answer_policy = "先分别回答有证据的事实，再明确标记依据人物方法做出的推演。"
    cognitive_model = cognitive_model or {}
    activated_assets = _activate_assets(user_text, cognitive_model)
    asks_deliberation = any(marker in user_text for marker in _DELIBERATION_MARKERS)
    deliberation_required = (
        mode == "mixed"
        or (asks_inference and asks_deliberation)
        or bool(
            activated_assets.get("conditional_rules")
            and activated_assets.get("decision_samples")
        )
    )
    return {
        "mode": mode,
        "subquestions": _subquestions(user_text),
        "direct_evidence_available": direct_evidence,
        "evidence_coverage": coverage,
        "time_scope": re.findall(r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)", user_text),
        "answer_policy": answer_policy,
        "available_cognitive_assets": {
            key: len(value) if isinstance(value, list) else 0
            for key, value in cognitive_model.items()
        },
        "activated_persona_assets": activated_assets,
        "deliberation_required": deliberation_required,
        "review_checklist": [
            "事实是否都有检索或网络证据",
            "推演是否明确区别于真人经历和实时观点",
            "是否使用了当前情境最相关的人格规则而非泛化建议",
            "是否避开反例、越界表达与未经确认的矛盾立场",
        ],
    }
