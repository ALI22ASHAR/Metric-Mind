import enum
import uuid
from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DatasetStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def generate_dataset_id() -> str:
    """Generate a prefixed unique dataset identifier."""
    return f"ds_{uuid.uuid4().hex[:12]}"


class Dataset(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model representing an uploaded dataset and its metadata.
    """
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_dataset_id,
        index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Owning workspace for tenant isolation",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original uploaded filename",
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Local or storage path to the raw dataset file",
    )
    clean_file_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Local path to the clean analytical parquet file",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Size of uploaded file in bytes",
    )
    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="application/octet-stream",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DatasetStatus.UPLOADED.value,
        index=True,
        comment="Lifecycle status: uploaded, processing, ready, failed",
    )
    row_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total number of rows detected",
    )
    column_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total number of columns detected",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Diagnostic error details if processing fails",
    )

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id!r}, filename={self.filename!r}, status={self.status!r})>"
