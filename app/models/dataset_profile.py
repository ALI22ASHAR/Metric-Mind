import uuid
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def generate_profile_id() -> str:
    """Generate a prefixed unique dataset profile identifier."""
    return f"prof_{uuid.uuid4().hex[:12]}"


class DatasetProfile(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model representing statistical profile and quality analysis of a dataset.
    """
    __tablename__ = "dataset_profiles"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_profile_id,
        index=True,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Associated dataset ID",
    )
    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    duplicate_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    quality_warnings_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    profile_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON-serialized full profile payload",
    )

    def __repr__(self) -> str:
        return f"<DatasetProfile(id={self.id!r}, dataset_id={self.dataset_id!r}, rows={self.row_count}, cols={self.column_count})>"
