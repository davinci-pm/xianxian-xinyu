from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
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

    # 对话导演与人物生成分离。意图模型失败时始终回退到本地规则，不阻断聊天。
    intent_llm_enabled: bool = False
    intent_llm_api_key: str | None = Field(default=None, repr=False)
    intent_llm_base_url: str | None = None
    intent_llm_model: str = "qwen3.8-flash"
    intent_llm_timeout_seconds: float = 1.5
    intent_llm_reasoning_effort: str | None = "none"
    intent_local_fast_path_enabled: bool = True
    intent_local_fast_path_threshold: float = 0.82

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    cookie_secure: bool = False
    cookie_name: str = "sage_visitor_id"

    persona_root: Path = PROJECT_ROOT / "personas"
    seed_root: Path = PROJECT_ROOT / "data" / "seed"
    codex_skill_root: Path = Path.home() / ".codex" / "skills"
    upstream_skill_root: Path = PROJECT_ROOT / "skills" / "upstream"

    rag_embedding_enabled: bool = True
    rag_embedding_provider: str = "fastembed"
    rag_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    rag_embedding_cache_dir: Path = PROJECT_ROOT / "data" / "models" / "fastembed"
    rag_chunk_chars: int = 520
    rag_chunk_overlap_chars: int = 80
    rag_keyword_candidates: int = 12
    rag_vector_candidates: int = 12
    rag_final_limit: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
