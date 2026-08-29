import secrets
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
ASSET_ROOT = BACKEND_ROOT / "deploy_assets"
BUNDLE_ROOT = BACKEND_ROOT / "vefaas_bundle"


def _copy_runtime_assets() -> None:
    if ASSET_ROOT.exists():
        shutil.rmtree(ASSET_ROOT)
    shutil.copytree(PROJECT_ROOT / "personas", ASSET_ROOT / "personas")
    shutil.copytree(PROJECT_ROOT / "data" / "seed", ASSET_ROOT / "data" / "seed")

    source_upstream = PROJECT_ROOT / "skills" / "upstream"
    target_upstream = ASSET_ROOT / "skills" / "upstream"
    target_upstream.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_upstream / "ALLOWLIST.yaml", target_upstream / "ALLOWLIST.yaml")
    allowlist = yaml.safe_load((source_upstream / "ALLOWLIST.yaml").read_text(encoding="utf-8"))
    for item in allowlist.get("skills", []):
        install_dir = str(item["install_dir"])
        source_skill = source_upstream / install_dir / "SKILL.md"
        target_skill = target_upstream / install_dir / "SKILL.md"
        target_skill.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_skill, target_skill)

    fengge_source = Path.home() / ".codex" / "skills" / "fengge-wangmingtianya-perspective"
    fengge_target = ASSET_ROOT / "codex_skills" / "fengge-wangmingtianya-perspective"
    shutil.copytree(fengge_source, fengge_target)


def _create_sanitized_bootstrap() -> Path:
    source_path = PROJECT_ROOT / "data" / "first_sage.db"
    target_path = ASSET_ROOT / "data" / "bootstrap.db"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)
    with sqlite3.connect(target_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        for table in (
            "safety_events",
            "generation_runs",
            "memories",
            "messages",
            "conversations",
            "visitor_sessions",
            "users",
        ):
            connection.execute(f'DELETE FROM "{table}"')
        connection.commit()
        connection.execute("VACUUM")
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise RuntimeError("部署种子数据库完整性校验失败")
    return target_path


def _create_vefaas_bundle() -> None:
    """Build a deploy-only tree so veFaaS detects requirements.txt, not pyproject.toml."""
    if BUNDLE_ROOT.exists():
        shutil.rmtree(BUNDLE_ROOT)

    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    )
    shutil.copytree(BACKEND_ROOT / "app", BUNDLE_ROOT / "app", ignore=ignore)
    shutil.copytree(BACKEND_ROOT / "alembic", BUNDLE_ROOT / "alembic", ignore=ignore)
    shutil.copytree(ASSET_ROOT, BUNDLE_ROOT / "deploy_assets", ignore=ignore)
    shutil.copy2(BACKEND_ROOT / "alembic.ini", BUNDLE_ROOT / "alembic.ini")
    shutil.copy2(
        BACKEND_ROOT / "requirements.production.txt",
        BUNDLE_ROOT / "requirements.txt",
    )

    # veFaaS does not always attach the remote dependency task output to the
    # released revision. Build a Linux CPython 3.12 vendor tree locally so the
    # uploaded package is self-contained even when deployment runs from macOS.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--target",
            str(BUNDLE_ROOT / "_vendor"),
            "--platform",
            "manylinux2014_x86_64",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--only-binary=:all:",
            "-r",
            str(BACKEND_ROOT / "requirements.production.txt"),
        ],
        check=True,
    )

    (BUNDLE_ROOT / ".vefaasignore").write_text(
        "\n".join(
            (
                "__pycache__/",
                "**/__pycache__/",
                "*.pyc",
                "*.db-shm",
                "*.db-wal",
                ".DS_Store",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    _copy_runtime_assets()
    target_path = _create_sanitized_bootstrap()
    (ASSET_ROOT / "deployment-generation.txt").write_text(secrets.token_hex(12), encoding="utf-8")
    _create_vefaas_bundle()
    print(f"Prepared deploy assets: {ASSET_ROOT}")
    print(f"Bootstrap database: {target_path.stat().st_size / 1024 / 1024:.1f} MiB")
    print(f"Prepared veFaaS bundle: {BUNDLE_ROOT}")


if __name__ == "__main__":
    main()
