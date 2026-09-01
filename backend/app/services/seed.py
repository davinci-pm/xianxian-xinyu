import json
from datetime import UTC, datetime
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeDocument, Persona, PersonaVersion, SkillConfig
from app.services.persona_loader import PersonaPack, load_all_persona_packs


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def seed_database(db: Session) -> None:
    for pack in load_all_persona_packs():
        persona = _upsert_persona(db, pack)
        version = _upsert_persona_version(db, persona, pack)
        _upsert_knowledge(db, persona, version, pack)
    _upsert_skills(db)
    _upsert_upstream_skills(db)
    db.commit()


def _upsert_persona(db: Session, pack: PersonaPack) -> Persona:
    profile = pack.profile
    persona = db.scalar(select(Persona).where(Persona.slug == pack.slug))
    if persona is None:
        persona = Persona(slug=pack.slug)
        db.add(persona)
    persona.name_zh = str(profile["name_zh"])
    persona.name_en = str(profile["name_en"])
    persona.era = str(profile["era"])
    persona.region = str(profile["region"])
    persona.domains_json = _json(profile.get("domains", []))
    persona.topics_json = _json(profile.get("topics", []))
    persona.dilemmas_json = _json(profile.get("dilemmas", []))
    persona.short_intro = str(profile["short_intro"])
    persona.avatar_tone = str(profile.get("avatar_tone", "ink"))
    persona.chat_tier = str(pack.manifest["tier"])
    persona.status = str(pack.manifest["status"])
    persona.is_living = bool(profile.get("is_living", False))
    persona.pack_version = str(pack.manifest["version"])
    persona.origin_type = "curated"
    persona.visibility = "public"
    db.flush()
    return persona


def _upsert_persona_version(db: Session, persona: Persona, pack: PersonaPack) -> PersonaVersion:
    version_name = str(pack.manifest["version"])
    version = db.scalar(
        select(PersonaVersion).where(
            PersonaVersion.persona_id == persona.id,
            PersonaVersion.version == version_name,
        )
    )
    snapshot = {
        "manifest": pack.manifest,
        "starters": pack.starters,
        "sources": pack.sources,
        "style": pack.style,
        "fallback": pack.fallback,
    }
    if version is None:
        version = PersonaVersion(
            persona_id=persona.id,
            version=version_name,
            status="active",
            snapshot_json=_json(snapshot),
            quality_score=90 if pack.manifest["tier"] == "A" else 75,
            activated_at=datetime.now(UTC),
        )
        db.add(version)
        db.flush()
    else:
        version.snapshot_json = _json(snapshot)
        version.status = "active"
    persona.current_version_id = version.id
    db.flush()
    return version


def _upsert_knowledge(
    db: Session, persona: Persona, version: PersonaVersion, pack: PersonaPack
) -> None:
    for source in pack.sources:
        metadata = dict(source.get("metadata", {}))
        metadata["seed_key"] = source.get("key")
        existing = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.persona_id == persona.id,
                KnowledgeDocument.citation_label == source["citation_label"],
            )
        )
        if existing is None:
            existing = KnowledgeDocument(persona_id=persona.id)
            db.add(existing)
        existing.title = str(source["title"])
        existing.persona_version_id = version.id
        existing.source_type = str(source.get("source_type", "public_domain"))
        existing.source_url = source.get("source_url")
        existing.citation_label = str(source["citation_label"])
        existing.license_note = str(source["license_note"])
        existing.content = str(source["content"])
        existing.metadata_json = _json(metadata)
        existing.enabled = True


def _upsert_skills(db: Session) -> None:
    path = get_settings().seed_root / "skills.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for item in data.get("skills", []):
        config = db.scalar(select(SkillConfig).where(SkillConfig.skill_key == item["skill_key"]))
        if config is None:
            config = SkillConfig(skill_key=item["skill_key"])
            db.add(config)
        config.name = item["name"]
        config.version = item["version"]
        config.source = item["source"]
        config.license_name = item["license_name"]
        config.risk_level = item["risk_level"]
        config.permissions_json = _json(item.get("permissions", []))
        config.config_json = _json(item.get("config", {}))
        config.allowlisted = bool(item.get("allowlisted", False))
        config.enabled = bool(item.get("enabled", False))


def _upsert_upstream_skills(db: Session) -> None:
    settings = get_settings()
    allowlist_path = settings.upstream_skill_root / "ALLOWLIST.yaml"
    if not allowlist_path.is_file():
        return
    allowlist = yaml.safe_load(allowlist_path.read_text(encoding="utf-8"))
    registry_path = settings.persona_root / "upstream_personas.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    persona_names = {
        str(item["slug"]): str(item["name_zh"])
        for item in registry.get("personas", [])
        if isinstance(item, dict)
    }
    for item in allowlist.get("skills", []):
        skill_key = str(item["skill_key"])
        config = db.scalar(select(SkillConfig).where(SkillConfig.skill_key == skill_key))
        if config is None:
            config = SkillConfig(skill_key=skill_key)
            db.add(config)
        repository = str(item["repository"])
        pinned_commit = str(item["pinned_commit"])
        persona_slug = str(item["persona_slug"])
        config.name = f"{persona_names.get(persona_slug, persona_slug)}（上游原版）"
        config.version = f"1.0.0+upstream.{pinned_commit[:8]}"
        config.source = f"https://github.com/{repository}/tree/{pinned_commit}"
        config.license_name = str(item["license"])
        config.risk_level = "medium"
        config.permissions_json = _json(["project_skill_markdown_read"])
        config.config_json = _json(
            {
                "persona_slug": persona_slug,
                "install_dir": str(item["install_dir"]),
                "instruction_file": "SKILL.md",
                "pinned_commit": pinned_commit,
                "stars_snapshot": int(item["stars_snapshot"]),
                "mode": "upstream_original_read_only",
            }
        )
        config.allowlisted = True
        config.enabled = True
