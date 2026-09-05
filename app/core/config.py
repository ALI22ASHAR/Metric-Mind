from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables and .env file.
    """
    # Project Info
    PROJECT_NAME: str = "MetricMind"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    REQUIRE_AUTH: bool = False

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Storage Settings
    UPLOAD_DIR: str = "data/uploads"
    upload_dir: str = "data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    max_upload_size_bytes: int = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx"]
    allowed_upload_extensions: List[str] = [".csv", ".xlsx"]

    # Database Settings (PostgreSQL default for prod, SQLite fallback for local test/dev)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/metricmind"

    # LLM Settings
    LLM_PROVIDER: str = "mock"  # "mock", "openai", "gemini", "nvidia", "deepseek"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "deepseek-ai/deepseek-v4-pro-0813"
    JWT_SECRET: str = "change-this-secret-in-production"

    @property
    def async_database_url(self) -> str:
        """
        Ensures SQLAlchemy asyncpg dialect is used for PostgreSQL connections.
        """
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL

    @property
    def sync_database_url(self) -> str:
        """
        Synchronous database URL for Alembic migrations.
        """
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
