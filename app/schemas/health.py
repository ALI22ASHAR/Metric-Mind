from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: str = Field(..., description="Database connection status: 'connected' | 'disconnected' | 'not_configured'")
    details: Optional[str] = Field(None, description="Optional error or diagnostic details")


class HealthCheckResponse(BaseModel):
    status: str = Field("healthy", description="Overall application status")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment (e.g. development, production)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of the health check")
    database: DatabaseHealth = Field(..., description="Database connectivity status")
