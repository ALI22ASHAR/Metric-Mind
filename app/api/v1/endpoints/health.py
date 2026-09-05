import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.health import DatabaseHealth, HealthCheckResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health & Liveness Check",
    description="Returns service metadata and probes PostgreSQL database connectivity.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthCheckResponse:
    """
    Performs liveness check and probes database connection.
    """
    db_health = DatabaseHealth(status="connected")
    overall_status = "healthy"

    try:
        # Execute lightweight ping query
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Database health check ping failed: %s", exc)
        db_health = DatabaseHealth(
            status="disconnected",
            details="Database unreachable or offline",
        )
        overall_status = "degraded"

    return HealthCheckResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        database=db_health,
    )
