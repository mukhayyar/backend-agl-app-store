"""
FastAPI HTTP Server for App Store.
Dual proxy support: /agl for AGL store, /flathub for Flathub.org
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.http.routes import apps, auth, flatmanager, stats, favorites
from app.http.routes.flathub import apps as flathub_apps
from app.http.routes.flathub import collections as flathub_collections
from app.http.routes.flathub import stats as flathub_stats
from app.services.flatmanager_client import get_flat_manager_client
from app.services.flathub_client import close_flathub_client

logger = logging.getLogger(__name__)
settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing and correlation ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "client": request.client.host if request.client else "unknown",
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


async def _blacklist_cleanup_loop():
    """Periodically clean expired tokens from the blacklist."""
    import asyncio
    from app.core.auth_middleware import token_blacklist
    while True:
        await asyncio.sleep(3600)  # every hour
        try:
            token_blacklist.cleanup_expired()
            logger.debug("Token blacklist cleanup completed")
        except Exception as e:
            logger.error(f"Token blacklist cleanup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    import asyncio
    logger.info("Starting HTTP server...")
    cleanup_task = asyncio.create_task(_blacklist_cleanup_loop())
    yield
    # Cleanup
    logger.info("Shutting down HTTP server...")
    cleanup_task.cancel()
    fm_client = get_flat_manager_client()
    await fm_client.close()
    await close_flathub_client()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="PENS AGL App Store API",
        description="""
HTTP API for the AGL Application Store with dual proxy support.

## Route Structure

- `/http/agl/*` - AGL App Store (flat-manager integration)
- `/http/flathub/*` - Flathub.org API proxy

## Features

- **AGL Store**: App publishing, build management, RBAC
- **Flathub Proxy**: Browse apps, search, categories, stats
        """,
        version="2.0.0",
        docs_url="/http/docs",
        redoc_url="/http/redoc",
        openapi_url="/http/openapi.json",
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Security headers middleware (outermost — runs on every response)
    app.add_middleware(SecurityHeadersMiddleware)

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # CORS middleware — require explicit origins in production
    if settings.cors_origins:
        origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    else:
        origins = []
        logger.warning("CORS_ORIGINS is empty — no cross-origin requests will be allowed")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ==================== Health & Root ====================

    @app.get("/http/health")
    async def health_check():
        """Health check endpoint with database connectivity check."""
        from database import SessionLocal
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError
        from fastapi.responses import JSONResponse

        db_ok = False
        db = None
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db_ok = True
        except SQLAlchemyError as e:
            logger.warning(f"Health check DB failed: {e}")
        finally:
            if db:
                db.close()

        status = "healthy" if db_ok else "degraded"
        code = 200 if db_ok else 503
        return JSONResponse(
            status_code=code,
            content={"status": status, "service": "http", "database": "ok" if db_ok else "unreachable"},
        )

    @app.get("/http/")
    async def root():
        """Root endpoint with API information."""
        return {
            "service": "PENS AGL App Store HTTP API",
            "version": "2.0.0",
            "docs": "/http/docs",
            "stores": {
                "agl": {
                    "description": "AGL App Store with flat-manager",
                    "endpoints": {
                        "apps": "/http/agl/apps",
                        "auth": "/http/agl/auth",
                        "flatmanager": "/http/agl/flatmanager",
                        "stats": "/http/agl/stats",
                    }
                },
                "flathub": {
                    "description": "Flathub.org API proxy",
                    "endpoints": {
                        "appstream": "/http/flathub/appstream",
                        "search": "/http/flathub/search",
                        "collections": "/http/flathub/collection",
                        "stats": "/http/flathub/stats",
                    }
                }
            }
        }

    # ==================== AGL Store Routes ====================
    # All existing routes under /http/agl/

    agl_router = APIRouter(prefix="/http/agl", tags=["agl"])
    agl_router.include_router(apps.router)
    agl_router.include_router(auth.router)
    agl_router.include_router(flatmanager.router)
    agl_router.include_router(stats.router)
    agl_router.include_router(favorites.router)
    app.include_router(agl_router)

    # ==================== Flathub Proxy Routes ====================
    # All Flathub proxy routes under /http/flathub/

    flathub_router = APIRouter(prefix="/http/flathub", tags=["flathub"])
    flathub_router.include_router(flathub_apps.router)
    flathub_router.include_router(flathub_collections.router)
    flathub_router.include_router(flathub_stats.router)
    app.include_router(flathub_router)

    return app


# Create the FastAPI app instance
http_app = create_app()
