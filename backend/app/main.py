"""CapitalOS FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.csrf import CSRFMiddleware

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("capitalos")

FX_SYNC_INTERVAL_SECONDS = 24 * 60 * 60
FX_SYNC_STARTUP_DELAY_SECONDS = 60
PRICE_SYNC_INTERVAL_SECONDS = 24 * 60 * 60
PRICE_SYNC_STARTUP_DELAY_SECONDS = 120  # offset from the FX loop's 60s


def _run_fx_sync() -> None:
    """Open a session and sync FX rates for every user (runs in a thread)."""
    from app.core.db import SessionLocal
    from app.services.fx_sync import sync_all_users

    db = SessionLocal()
    try:
        sync_all_users(db)
    finally:
        db.close()


def _run_price_sync() -> None:
    """Open a session and sync holding prices for every user (runs in a thread)."""
    from app.core.db import SessionLocal
    from app.services.price_sync import sync_all_users

    db = SessionLocal()
    try:
        sync_all_users(db)
    finally:
        db.close()


async def _daily_loop(
    name: str, run: Callable[[], None], startup_delay: int, interval: int
) -> None:
    await asyncio.sleep(startup_delay)
    while True:
        try:
            await asyncio.to_thread(run)
        except Exception:  # noqa: BLE001 - keep the loop alive whatever happens
            logger.exception("Daily %s sync run failed", name)
        await asyncio.sleep(interval)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    tasks: list[asyncio.Task] = []
    if settings.fx_auto_sync:
        tasks.append(asyncio.create_task(_daily_loop(
            "FX", _run_fx_sync, FX_SYNC_STARTUP_DELAY_SECONDS, FX_SYNC_INTERVAL_SECONDS)))
        logger.info("Daily FX auto-sync enabled")
    if settings.price_auto_sync:
        tasks.append(asyncio.create_task(_daily_loop(
            "price", _run_price_sync,
            PRICE_SYNC_STARTUP_DELAY_SECONDS, PRICE_SYNC_INTERVAL_SECONDS)))
        logger.info("Daily price auto-sync enabled")
    yield
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="CapitalOS — privacy-first personal & household finance.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if settings.trusted_host_list != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
    app.add_middleware(CSRFMiddleware)

    @app.middleware("http")
    async def correlation_and_headers(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "request_id": rid},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled error (request_id=%s)", request_id)
        detail = "Internal server error"
        if not settings.is_production:
            detail = f"{type(exc).__name__}: {exc}"
        return JSONResponse(status_code=500, content={"detail": detail, "request_id": request_id})

    # Import here so all routers (and their models) are registered.
    from app.api.v1.router import api_router

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"app": settings.app_name, "status": "ok", "docs": "/api/docs"}

    return app


app = create_app()
