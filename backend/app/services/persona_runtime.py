import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Persona, PersonaVersion
from app.services.persona_loader import (
    PersonaPack,
    PersonaPackError,
    load_persona_pack,
    validate_persona_pack,
)


def load_runtime_persona_pack(
    db: Session, persona: Persona, version_id: str | None = None
) -> PersonaPack:
    selected_id = version_id or persona.current_version_id
    if selected_id:
        version = db.get(PersonaVersion, selected_id)
        if version is None or version.persona_id != persona.id:
            raise PersonaPackError("人物版本不存在或与人物不匹配")
        return _pack_from_snapshot(version.snapshot_json, persona.slug)
    return load_persona_pack(persona.slug)


def _pack_from_snapshot(snapshot_json: str, slug: str) -> PersonaPack:
    try:
        snapshot = json.loads(snapshot_json)
    except json.JSONDecodeError as exc:
        raise PersonaPackError("人物版本快照无法解析") from exc
    if not isinstance(snapshot, dict):
        raise PersonaPackError("人物版本快照格式错误")

    manifest = _dict(snapshot.get("manifest"), "manifest")
    starters = _list_of_dicts(snapshot.get("starters"), "starters")
    sources = _list_of_dicts(snapshot.get("sources", []), "sources")
    if str(manifest.get("profile", {}).get("slug", "")) != slug:
        raise PersonaPackError("人物版本快照 slug 不匹配")
    pack = PersonaPack(
        root=Path(get_settings().persona_root) / slug,
        manifest=manifest,
        starters=starters,
        sources=sources,
        style=str(snapshot.get("style", "")),
        fallback=str(snapshot.get("fallback", "")).strip()
        or "我还在整理思路。我们先从你最在意的一点谈起。",
    )
    validate_persona_pack(pack)
    return pack


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PersonaPackError(f"人物版本快照缺少 {label}")
    return value


def _list_of_dicts(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise PersonaPackError(f"人物版本快照中的 {label} 格式错误")
    return list(value)
