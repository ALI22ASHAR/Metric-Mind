import uuid
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def generate_understanding_id() -> str:
    """Generate a prefixed unique AI understanding identifier."""
    return f"aiu_{uuid.uuid4().hex[:12]}"


class AIDatasetUnderstandingModel(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing the structured AI dataset understanding synthesis.
    """
    __tablename__ = "ai_dataset_understandings"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_understanding_id,
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
    domain: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="sales",
        comment="Inferred business domain",
    )
    business_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="AI-generated executive business summary",
    )
    primary_date_column: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        comment="Primary time dimension column",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.95,
        comment="Overall confidence score (0.0 - 1.0)",
    )
    understanding_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full serialized AIDatasetUnderstanding payload",
    )

    def __repr__(self) -> str:
        return f"<AIDatasetUnderstandingModel(id={self.id!r}, dataset_id={self.dataset_id!r}, domain={self.domain!r})>"
