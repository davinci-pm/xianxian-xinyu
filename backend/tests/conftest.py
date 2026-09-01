import os
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_temp_dir = TemporaryDirectory(prefix="first-sage-tests-")
TEST_DATABASE = Path(_temp_dir.name) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DATABASE}"
os.environ["APP_ENV"] = "test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["RAG_EMBEDDING_PROVIDER"] = "hash"
os.environ["RAG_INDEX_CACHE_PERSONAS"] = "2"
os.environ["INVITE_CODES"] = "SAGE-ALPHA-001,SAGE-BETA-002"
os.environ["SESSION_SECRET"] = "test-session-secret-with-enough-entropy"

alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
command.upgrade(alembic_config, "head")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
