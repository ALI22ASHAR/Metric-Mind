import os
import shutil
import tempfile
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.storage import storage_manager
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Isolated in-memory SQLite engine for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """
    Creates fresh schema before each test and drops it after.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an isolated test database session.
    """
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def override_dependencies(db_session: AsyncSession):
    """
    Overrides get_db dependency to point to the test in-memory database.
    """
    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def temporary_upload_dir(monkeypatch):
    """
    Isolates file upload storage in a temporary directory for each test.
    """
    temp_dir = tempfile.mkdtemp(prefix="metricmind_test_uploads_")
    monkeypatch.setattr(settings, "UPLOAD_DIR", temp_dir)
    storage_manager.base_dir = storage_manager.base_dir.__class__(temp_dir)
    storage_manager._ensure_base_directory()

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Asynchronous test client for FastAPI application.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
