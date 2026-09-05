import uuid
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def generate_quality_report_id() -> str:
    """Generate a prefixed unique quality report identifier."""
    return f"qr_{uuid.uuid4().hex[:12]}"


class DatasetQualityReport(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing data quality assessment and normalization results.
    """
    __tablename__ = "dataset_quality_reports"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_quality_report_id,
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
    quality_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=100.0,
        comment="Overall dataset health score (0-100)",
    )
    clean_file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Path to the generated clean parquet file",
    )
    cleaning_policy: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON-serialized cleaning policy configuration",
    )
    report_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON-serialized full DataQualityReport payload",
    )

    def __repr__(self) -> str:
        return f"<DatasetQualityReport(id={self.id!r}, dataset_id={self.dataset_id!r}, score={self.quality_score})>"
