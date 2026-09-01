from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_ASSET_ROOT = BACKEND_ROOT / "deploy_assets"
DEPLOYMENT_GENERATION_FILE = DEPLOY_ASSET_ROOT / "deployment-generation.txt"
DEFAULT_ASSET_ROOT = DEPLOY_ASSET_ROOT if DEPLOY_ASSET_ROOT.is_dir() else PROJECT_ROOT
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "first_sage.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "先贤心语 API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite+pysqlite:///{DEFAULT_DATABASE_PATH}"
    frontend_origin: str = "http://127.0.0.1:3000"

    llm_provider: str = "mock"
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_base_url: str | None = None
    llm_model: str = "mock-thinker-v1"
    llm_timeout_seconds: float = 90.0
    # 思考型模型的 reasoning 与最终正文共享输出预算。过小会导致只有
    # reasoning_content 而没有 content，因此默认以内容完整性优先。
    llm_max_tokens: int = 4096
    llm_retry_attempts: int = 3
    # DeepSeek thinking defaults to enabled. Adaptive mode keeps ordinary dialogue
    # quick and reserves low-effort reasoning for genuinely complex decisions.
    llm_thinking_mode: str = "adaptive"
    llm_reasoning_effort: str = "low"
    llm_fast_max_tokens: int = 1_200
    llm_complex_max_tokens: int = 2_048

    # 对话导演与人物生成分离。意图模型失败时始终回退到本地规则，不阻断聊天。
    intent_llm_enabled: bool = False
    intent_llm_api_key: str | None = Field(default=None, repr=False)
    intent_llm_base_url: str | None = None
    intent_llm_model: str = "qwen3.8-flash"
    intent_llm_timeout_seconds: float = 1.5
    intent_llm_reasoning_effort: str | None = "none"
    intent_local_fast_path_enabled: bool = True
    intent_local_fast_path_threshold: float = 0.82

    # 对在世人物的近期事实使用独立网络证据层。网络内容不会自动改写稳定人格。
    web_search_enabled: bool = False
    web_search_provider: str = "so_search"
    web_search_base_url: str = "https://www.so.com/s"
    web_search_timeout_seconds: float = 6.0
    web_search_max_results: int = 5

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    auth_required: bool = False
    invite_codes: str = ""
    session_secret: str = Field(default="development-only-change-me", repr=False)
    cookie_secure: bool = False
    cookie_name: str = "sage_session"

    persona_root: Path = DEFAULT_ASSET_ROOT / "personas"
    seed_root: Path = DEFAULT_ASSET_ROOT / "data" / "seed"
    codex_skill_root: Path = (
        DEPLOY_ASSET_ROOT / "codex_skills"
        if DEPLOY_ASSET_ROOT.is_dir()
        else Path.home() / ".codex" / "skills"
    )
    upstream_skill_root: Path = DEFAULT_ASSET_ROOT / "skills" / "upstream"

    storage_provider: str = "local"
    s3_endpoint: str | None = None
    s3_access_key: str | None = Field(default=None, repr=False)
    s3_secret_key: str | None = Field(default=None, repr=False)
    s3_bucket: str | None = None
    s3_region: str = "cn-beijing"
    db_backup_key: str = "db/persona-chat.db"
    db_backup_interval_seconds: int = 86_400
    db_backup_keep_versions: int = 3
    db_backup_after_commit: bool = False
    database_bootstrap_path: Path = DEPLOY_ASSET_ROOT / "data" / "bootstrap.db"

    rag_embedding_enabled: bool = True
    rag_embedding_provider: str = "fastembed"
    rag_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    rag_embedding_cache_dir: Path = PROJECT_ROOT / "data" / "models" / "fastembed"
    rag_chunk_chars: int = 520
    rag_chunk_overlap_chars: int = 80
    rag_keyword_candidates: int = 12
    rag_vector_candidates: int = 12
    rag_index_cache_personas: int = 2
    rag_final_limit: int = 4

    @model_validator(mode="after")
    def use_revision_scoped_database_path(self) -> Self:
        if (
            self.app_env != "production"
            or self.storage_provider != "s3"
            or not self.database_url.startswith("sqlite")
        ):
            return self
        if not DEPLOYMENT_GENERATION_FILE.is_file():
            return self
        generation = DEPLOYMENT_GENERATION_FILE.read_text(encoding="utf-8").strip()
        if not generation or any(not (char.isalnum() or char == "-") for char in generation):
            raise ValueError("部署世代标识无效")
        self.database_url = f"sqlite+pysqlite:////tmp/data/{generation}/persona-chat.db"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
