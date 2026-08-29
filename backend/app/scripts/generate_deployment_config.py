import argparse
import os
import secrets
from pathlib import Path

from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
OUTPUT_DIR = PROJECT_ROOT / ".deployment"
OUTPUT_FILE = OUTPUT_DIR / "backend.production.env"
INVITE_FILE = OUTPUT_DIR / "invite-codes.txt"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _invite_code() -> str:
    token = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return f"SAGE-{token[:4]}-{token[4:8]}-{token[8:]}"


def _write_private(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        raise ValueError("邀请码数量必须在 1 到 100 之间")
    if OUTPUT_FILE.exists() and not args.force:
        print(f"Deployment config already exists: {OUTPUT_FILE}")
        return

    local = dotenv_values(PROJECT_ROOT / ".env")
    required_model_keys = ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")
    missing = [key for key in required_model_keys if not local.get(key)]
    if missing:
        raise RuntimeError(f"真实模型配置缺失：{', '.join(missing)}")

    codes = [_invite_code() for _ in range(args.count)]
    session_secret = secrets.token_urlsafe(48)
    production: dict[str, str] = {
        "APP_ENV": "production",
        "AUTH_REQUIRED": "true",
        "INVITE_CODES": ",".join(codes),
        "SESSION_SECRET": session_secret,
        "COOKIE_SECURE": "true",
        "DATABASE_URL": "sqlite+pysqlite:////tmp/data/persona-chat.db",
        "FRONTEND_ORIGIN": "https://placeholder.invalid",
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_REQUESTS": "30",
        "RATE_LIMIT_WINDOW_SECONDS": "60",
        "RAG_EMBEDDING_ENABLED": "false",
        "STORAGE_PROVIDER": "local",
        "DB_BACKUP_KEY": "db/persona-chat.db",
        "DB_BACKUP_INTERVAL_SECONDS": "300",
        "DB_BACKUP_KEEP_VERSIONS": "12",
    }
    copy_keys = (
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_TOKENS",
        "LLM_RETRY_ATTEMPTS",
        "INTENT_LLM_ENABLED",
        "INTENT_LLM_API_KEY",
        "INTENT_LLM_BASE_URL",
        "INTENT_LLM_MODEL",
        "INTENT_LLM_TIMEOUT_SECONDS",
        "INTENT_LLM_REASONING_EFFORT",
        "INTENT_LOCAL_FAST_PATH_ENABLED",
        "INTENT_LOCAL_FAST_PATH_THRESHOLD",
    )
    for key in copy_keys:
        value = local.get(key)
        if value:
            production[key] = str(value)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_private(
        OUTPUT_FILE,
        "".join(f"{key}={value}\n" for key, value in production.items()),
    )
    _write_private(
        INVITE_FILE,
        "\n".join(f"内测用户 {index:02d}: {code}" for index, code in enumerate(codes, 1))
        + "\n",
    )
    print(f"Generated {len(codes)} invite accounts")
    print(f"Production env: {OUTPUT_FILE}")
    print(f"Invite handoff: {INVITE_FILE}")


if __name__ == "__main__":
    main()
