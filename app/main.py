import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import decode_access_token
from app.db.session import engine
from app.models import Base

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager for startup and shutdown events.
    """
    logger.info("Starting %s in %s mode...", settings.PROJECT_NAME, settings.ENVIRONMENT)
    # Ensure database tables exist
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")
    except Exception as exc:
        logger.warning("Database table auto-initialization skipped: %s", exc)

    yield
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    # Dispose database engine connection pool
    await engine.dispose()
    logger.info("Database engine connections closed.")


def create_application() -> FastAPI:
    """
    FastAPI application factory.
    """
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="MetricMind: AI-Powered Automated Business Intelligence Platform API",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def enforce_api_auth(request: Request, call_next):
        if settings.REQUIRE_AUTH and request.url.path.startswith(settings.API_V1_PREFIX):
            public_paths = {
                f"{settings.API_V1_PREFIX}/health",
                "/health",
                f"{settings.API_V1_PREFIX}/auth/register",
                f"{settings.API_V1_PREFIX}/auth/login",
                "/docs",
                "/redoc",
            }
            if request.url.path not in public_paths:
                authorization = request.headers.get("Authorization", "")
                token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
                if not token or not decode_access_token(token):
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Authentication required."},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        return await call_next(request)

    # Configure CORS
    if settings.ALLOWED_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.ALLOWED_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Mount static assets
    if STATIC_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Serve Single-Page Application UI
    @application.get("/", include_in_schema=False)
    @application.get("/dashboard", include_in_schema=False)
    async def serve_spa_ui() -> FileResponse:
        index_file = TEMPLATES_DIR / "index.html"
        return FileResponse(str(index_file))

    @application.get("/kpi-tool", include_in_schema=False)
    @application.get("/flight-kpi", include_in_schema=False)
    @application.get("/universal-kpi", include_in_schema=False)
    async def serve_flight_kpi_ui() -> FileResponse:
        kpi_file = TEMPLATES_DIR / "flight_kpi_tool.html"
        return FileResponse(str(kpi_file))

    # Root health endpoint
    application.include_router(health_router, tags=["Health"])

    # API v1 routes
    application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return application


app = create_application()
