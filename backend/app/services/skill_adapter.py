import json
from dataclasses import dataclass
from typing import Any, Protocol

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SkillConfig


class SkillHandler(Protocol):
    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RegisteredSkill:
    key: str
    handler: SkillHandler


class SkillAdapter:
    """只调用数据库明确允许、启用且本地已注册的 Skill。"""

    def __init__(self) -> None:
        self._handlers: dict[str, SkillHandler] = {}

    def register(self, key: str, handler: SkillHandler) -> None:
        self._handlers[key] = handler

    def invoke(self, db: Session, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        config = db.scalar(select(SkillConfig).where(SkillConfig.skill_key == key))
        if config is None or not config.allowlisted or not config.enabled:
            raise PermissionError(f"Skill 未进入允许列表：{key}")
        if config.license_name == "UNVERIFIED" or config.risk_level not in {"low", "medium"}:
            raise PermissionError(f"Skill 审核状态不满足调用要求：{key}")
        handler = self._handlers.get(key)
        if handler is None:
            raise LookupError(f"Skill 未注册本地处理器：{key}")
        result = handler({**payload, "config": json.loads(config.config_json)})
        return {"skill": key, "result": result}


skill_adapter = SkillAdapter()
skill_adapter.register(
    "reflective_question",
    lambda payload: {"instruction": "用一个开放问题帮助用户形成自己的判断", **payload},
)
skill_adapter.register(
    "perspective_reframe",
    lambda payload: {"instruction": "提供一个新视角但保留用户选择权", **payload},
)
skill_adapter.register(
    "source_citation",
    lambda payload: {"instruction": "仅引用已检索到且可追溯的资料", **payload},
)


def _original_fengge_perspective(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("config")
    if not isinstance(config, dict):
        raise ValueError("Skill 缺少上游配置")
    skill_name = config.get("installed_skill_name")
    source_files = config.get("source_files")
    if (
        not isinstance(skill_name, str)
        or not skill_name
        or skill_name in {".", ".."}
        or "/" in skill_name
        or "\\" in skill_name
    ):
        raise ValueError("Skill 安装名称不合法")
    if not isinstance(source_files, list) or not source_files:
        raise ValueError("Skill 缺少上游原文列表")

    skill_root = (get_settings().codex_skill_root / skill_name).resolve()
    if not skill_root.is_dir():
        raise LookupError(f"Skill 原版安装目录不存在：{skill_name}")

    sections: list[str] = []
    loaded_files: list[str] = []
    for item in source_files:
        if not isinstance(item, str) or not item:
            raise ValueError("Skill 上游文件名不合法")
        source_path = (skill_root / item).resolve()
        if skill_root not in source_path.parents or not source_path.is_file():
            raise LookupError(f"Skill 上游原文不存在：{item}")
        source_text = source_path.read_text(encoding="utf-8")
        sections.append(f"\n\n--- 上游原文：{item} ---\n\n{source_text}")
        loaded_files.append(item)

    return {
        "instruction": "".join(sections).strip(),
        "mode": "upstream_original",
        "loaded_files": loaded_files,
    }


skill_adapter.register("fengge_perspective_reviewed", _original_fengge_perspective)


def _vendored_persona_skill(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("config")
    if not isinstance(config, dict):
        raise ValueError("Skill 缺少上游配置")
    install_dir = config.get("install_dir")
    instruction_file = config.get("instruction_file", "SKILL.md")
    if (
        not isinstance(install_dir, str)
        or not install_dir
        or "/" in install_dir
        or "\\" in install_dir
        or instruction_file != "SKILL.md"
    ):
        raise ValueError("项目 Skill 路径不合法")
    upstream_root = get_settings().upstream_skill_root.resolve()
    skill_root = (upstream_root / install_dir).resolve()
    instruction_path = (skill_root / instruction_file).resolve()
    if (
        upstream_root not in skill_root.parents
        or skill_root not in instruction_path.parents
        or not instruction_path.is_file()
    ):
        raise LookupError(f"项目 Skill 原文不存在：{install_dir}/{instruction_file}")
    return {
        "instruction": instruction_path.read_text(encoding="utf-8"),
        "mode": "upstream_original_read_only",
        "loaded_files": [instruction_file],
    }


def _register_vendored_skills() -> None:
    path = get_settings().upstream_skill_root / "ALLOWLIST.yaml"
    if not path.is_file():
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for item in data.get("skills", []):
        if isinstance(item, dict) and isinstance(item.get("skill_key"), str):
            skill_adapter.register(str(item["skill_key"]), _vendored_persona_skill)


_register_vendored_skills()
