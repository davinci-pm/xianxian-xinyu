import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Persona
from app.services.auth import configured_invite_codes
from app.services.database_runtime import (
    backup_database,
    backup_loop,
    prepare_database,
    sqlite_backup_enabled,
)
from app.services.llm.factory import close_model_provider
from app.services.seed import seed_database

logger = logging.getLogger(__name__)


def _validate_runtime_security() -> None:
    settings = get_settings()
    if not settings.auth_required:
        return
    if len(settings.session_secret) < 32 or settings.session_secret == "development-only-change-me":
        raise RuntimeError("生产环境 SESSION_SECRET 未安全配置")
    codes = configured_invite_codes()
    if not codes or len(codes) != len(set(codes)):
        raise RuntimeError("生产环境邀请码缺失或存在重复")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _validate_runtime_security()
    await asyncio.to_thread(prepare_database)
    try:
        with SessionLocal() as db:
            seed_database(db)
    except OperationalError:
        # 数据库迁移是显式启动步骤；health 会报告未就绪。
        pass
    if sqlite_backup_enabled():
        # 立即标记当前滚动发布世代，避免旧实例关停时覆盖新快照。
        await asyncio.to_thread(backup_database)
    stop_event = asyncio.Event()
    backup_task = (
        asyncio.create_task(backup_loop(stop_event))
        if sqlite_backup_enabled()
        else None
    )
    try:
        yield
    finally:
        await close_model_provider()
        if backup_task is not None:
            stop_event.set()
            await backup_task
            try:
                await asyncio.to_thread(backup_database)
            except Exception:
                logger.exception("database_shutdown_backup_failed")


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_trace(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
    started = monotonic()
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    logger.info(
        "request_completed method=%s path=%s status=%s duration_ms=%s trace_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        int((monotonic() - started) * 1000),
        trace_id,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-Trace-Id"],
    expose_headers=["X-Trace-Id"],
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
