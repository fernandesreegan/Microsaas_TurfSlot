"""FastAPI application entrypoint for the TurfSlot API."""

import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import ModuleType

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import engine
from app.exceptions import AppError
from app.logging_config import configure_logging
from app.rate_limit import limiter
from app.routers import admin, auth, bookings, owner, owner_bookings, payments, slots, turfs

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"


def _load_scheduler() -> ModuleType | None:
    """Import ``app.services.scheduler`` if it exists (written in Phase 2).

    The module is expected to expose ``start_scheduler() -> None`` and
    ``shutdown_scheduler() -> None``.
    """
    try:
        return importlib.import_module("app.services.scheduler")
    except ModuleNotFoundError as exc:
        if exc.name == "app.services.scheduler":
            logger.warning("Scheduler module not available; background jobs disabled")
            return None
        raise


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Configure logging and start/stop the background scheduler."""
    configure_logging()
    if settings.uses_dev_secret_key:
        logger.warning(
            "SECRET_KEY is not set; using the insecure development default. "
            "Set SECRET_KEY for any non-local deployment."
        )
    scheduler = _load_scheduler() if settings.SCHEDULER_ENABLED else None
    if scheduler is not None:
        scheduler.start_scheduler()
        logger.info("Background scheduler started")
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown_scheduler()
            logger.info("Background scheduler stopped")


app = FastAPI(
    title="TurfSlot API",
    version="1.0.0",
    description="Sports turf slot booking marketplace API.",
    lifespan=lifespan,
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL.rstrip("/")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers - every error body is {"detail": str, "code": str | null}
# ---------------------------------------------------------------------------


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Render ``AppError`` subclasses as ``{"detail", "code"}``."""
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render framework HTTP errors (404 route, 405, ...) in the shared error shape."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": None},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Render validation errors with a string ``detail`` plus the raw ``errors`` list."""
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"{loc}: {first.get('msg', 'Invalid value')}" if loc else first.get("msg")
    else:
        message = "Invalid request"
    return JSONResponse(
        status_code=422,
        content={
            "detail": message,
            "code": "VALIDATION_ERROR",
            "errors": jsonable_encoder(errors),
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Render slowapi rate-limit errors as 429 ``RATE_LIMITED``."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Too many requests: {exc.detail}", "code": "RATE_LIMITED"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors and return a generic 500."""
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

for _router_module in (auth, turfs, slots, bookings, payments, owner, owner_bookings, admin):
    app.include_router(_router_module.router, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness/readiness probe; checks DB connectivity with ``SELECT 1``."""
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Health check database query failed: %s", type(exc).__name__)
        db_status = "error"
    return {"status": "ok", "db": db_status}
