from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Persona
from app.services.seed import seed_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        with SessionLocal() as db:
            seed_database(db)
    except OperationalError:
        # 数据库迁移是显式启动步骤；health 会报告未就绪。
        pass
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(api_v1_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, object]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            personas = db.scalar(select(func.count()).select_from(Persona)) or 0
        return {
            "status": "ok",
            "database": "ready",
            "personas": personas,
            "model_provider": settings.llm_provider,
        }
    except OperationalError:
        return {
            "status": "not_ready",
            "database": "migration_required",
            "personas": 0,
            "model_provider": settings.llm_provider,
        }
