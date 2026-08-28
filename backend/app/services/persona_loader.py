from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings


class PersonaPackError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersonaPack:
    root: Path
    manifest: dict[str, Any]
    starters: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    style: str
    fallback: str

    @property
    def slug(self) -> str:
        return str(self.manifest["profile"]["slug"])

    @property
    def profile(self) -> dict[str, Any]:
        return dict(self.manifest["profile"])


def _read_yaml(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise PersonaPackError(f"缺少 Persona Pack 文件：{path}")
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PersonaPackError(f"Persona Pack 文件格式错误：{path}")
    return raw


def load_persona_pack(slug: str) -> PersonaPack:
    if not slug.replace("-", "").isalnum():
        raise PersonaPackError("人物标识不合法")
    root = get_settings().persona_root / slug
    if not root.is_dir():
        return _load_registry_persona(slug)
    manifest = _read_yaml(root / "manifest.yaml")
    opening = _read_yaml(root / "opening.yaml")
    sources = _read_yaml(root / "sources.yaml", required=False)
    style_path = root / "style.md"
    fallback_path = root / "fallback.md"
    pack = PersonaPack(
        root=root,
        manifest=manifest,
        starters=list(opening.get("starters", [])),
        sources=list(sources.get("documents", [])),
        style=style_path.read_text(encoding="utf-8") if style_path.exists() else "",
        fallback=(
            fallback_path.read_text(encoding="utf-8").strip()
            if fallback_path.exists()
            else "我还在整理思路。我们先从你最在意的一点谈起，好吗？"
        ),
    )
    validate_persona_pack(pack)
    return pack


def load_all_persona_packs() -> list[PersonaPack]:
    root = get_settings().persona_root
    if not root.exists():
        return []
    directory_packs = [
        load_persona_pack(path.name) for path in sorted(root.iterdir()) if path.is_dir()
    ]
    registry = _read_yaml(root / "upstream_personas.yaml", required=False)
    registry_packs = [
        _registry_entry_to_pack(item)
        for item in registry.get("personas", [])
        if isinstance(item, dict)
    ]
    return directory_packs + registry_packs


def _load_registry_persona(slug: str) -> PersonaPack:
    registry_path = get_settings().persona_root / "upstream_personas.yaml"
    registry = _read_yaml(registry_path, required=False)
    for item in registry.get("personas", []):
        if isinstance(item, dict) and item.get("slug") == slug:
            return _registry_entry_to_pack(item)
    raise PersonaPackError(f"人物不存在：{slug}")


def _registry_entry_to_pack(item: dict[str, Any]) -> PersonaPack:
    slug = str(item["slug"])
    is_living = bool(item.get("is_living", False))
    name_zh = str(item["name_zh"])
    public_figure_notice = (
        "这是基于公开资料构建的非本人、非授权 AI 思想人格；不代表本人真实观点，"
        "也不提供投资、医疗、升学或其他专业建议。"
        if is_living
        else "这是基于公开资料构建的 AI 思想人格，不是本人，也不代表其在任何具体情境中的真实观点。"
    )
    manifest = {
        "id": f"persona-{slug}",
        "version": "1.0.0",
        "status": "active",
        "tier": "A",
        "profile": {
            "slug": slug,
            "name_zh": name_zh,
            "name_en": str(item["name_en"]),
            "era": str(item["era"]),
            "region": str(item["region"]),
            "domains": list(item.get("domains", [])),
            "topics": list(item.get("topics", [])),
            "dilemmas": list(item.get("dilemmas", [])),
            "short_intro": str(item["short_intro"]),
            "avatar_tone": str(item.get("avatar_tone", "paper")),
            "is_living": is_living,
        },
        "identity": {
            "role": str(item["identity"]),
            "historical_context": f"{item['era']}，{item['region']}相关公开资料视角。",
            "simulation_boundary": public_figure_notice,
        },
        "principles": [
            {
                "id": f"principle-{index}",
                "name": str(principle),
                "meaning": str(principle),
                "dialogue_use": "结合用户当前处境，通过追问、举例或行动建议解释这一方法。",
            }
            for index, principle in enumerate(item["principles"], start=1)
        ],
        "language_style": {
            "tone": str(item["style"]),
            "sentence_length": "以短句和清晰结构为主",
            "question_policy": "每轮最多一个核心问题；连续追问后必须先回应",
            "preferred_moves": ["复述处境", "挑战假设", "具体举例", "引导行动"],
        },
        "forbidden_behaviors": [
            "不得宣称自己是真人、获得本人授权或正在传达本人实时观点",
            "不得把人物风格凌驾于事实、来源、安全流程和用户选择权之上",
            "不得提供确定性的投资、医疗、法律或升学录取承诺",
            "高风险心理信号必须停止角色演绎并进入平台安全响应",
        ],
        "proactive_strategy": {
            "opening_goal": "从该人物最具辨识度的方法切入用户的具体处境",
            "identify_goal": "识别事实、情绪、目标与现实约束",
            "clarify_goal": "挑战未经验证的假设",
            "guidance_goal": "用上游 Skill 与检索资料给出一个方法和下一步",
            "reflection_goal": "把判断权交还用户",
            "end_goal": "总结已澄清内容和未解决问题",
            "max_question_streak": 2,
        },
        "memory_strategy": {
            "read_scope": "仅读取同一用户、同一人物、已确认的长期记忆",
            "write_policy": "只有用户确认后才跨会话记忆",
            "never_store": ["自伤细节", "医疗诊断", "精确住址", "证件信息", "密钥和密码"],
        },
        "skills": [str(item["skill_key"])],
        "disclaimer": public_figure_notice,
    }
    opening = str(item["opening"])
    pack = PersonaPack(
        root=get_settings().persona_root,
        manifest=manifest,
        starters=[
            {
                "text": opening,
                "quick_replies": list(
                    item.get(
                        "quick_replies",
                        ["我正卡在一个选择上", "我想换个角度看问题", "我需要一个能马上行动的办法"],
                    )
                ),
            }
        ],
        sources=[],
        style=f"{item['style']}\n始终保留 AI 思想人格声明，不冒充{name_zh}本人。",
        fallback=f"我们先别急着下结论。把你现在最难取舍的两件事摆出来，我用{name_zh}相关的方法陪你拆开看。",
    )
    validate_persona_pack(pack)
    return pack


def validate_persona_pack(pack: PersonaPack) -> None:
    required_top = {
        "id",
        "version",
        "status",
        "tier",
        "profile",
        "identity",
        "principles",
        "language_style",
        "forbidden_behaviors",
        "proactive_strategy",
        "memory_strategy",
        "skills",
        "disclaimer",
    }
    missing = required_top.difference(pack.manifest)
    if missing:
        raise PersonaPackError(f"{pack.root.name} 缺少字段：{sorted(missing)}")
    if not pack.starters:
        raise PersonaPackError(f"{pack.root.name} 缺少主动开场")
    for starter in pack.starters:
        if not starter.get("text") or not starter.get("quick_replies"):
            raise PersonaPackError(f"{pack.root.name} 开场缺少文本或快捷回答")
