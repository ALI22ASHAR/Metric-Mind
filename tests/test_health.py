import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.core.config import settings
from app.db.session import get_db
from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient) -> None:
    """
    Test that the root /health endpoint returns 200 OK and valid schema.
    """
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["app_name"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "timestamp" in data
    assert "database" in data
    assert "status" in data["database"]


@pytest.mark.asyncio
async def test_api_v1_health_check_endpoint(client: AsyncClient) -> None:
    """
    Test that /api/v1/health endpoint returns 200 OK.
    """
    response = await client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == settings.PROJECT_NAME


@pytest.mark.asyncio
async def test_health_check_db_connected(client: AsyncClient) -> None:
    """
    Test /health response when database is connected.
    """
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=None)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "connected"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check_db_disconnected(client: AsyncClient) -> None:
    """
    Test /health response gracefully degrades when database is unreachable.
    """
    mock_db = AsyncMock()
    mock_db.execute.side_effect = ConnectionRefusedError("Database unreachable")

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"]["status"] == "disconnected"
        assert "Database unreachable" in data["database"]["details"]
    finally:
        app.dependency_overrides.clear()
