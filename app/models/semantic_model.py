import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def generate_semantic_model_id() -> str:
    """Generate a prefixed unique semantic model identifier."""
    return f"sm_{uuid.uuid4().hex[:12]}"


class SemanticModel(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing the semantic business concept mapping of a dataset.
    """
    __tablename__ = "semantic_models"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_semantic_model_id,
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
        comment="Inferred or assigned business domain",
    )
    dataset_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="generic_business",
        comment="Dataset classification",
    )
    mappings_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        comment="JSON dictionary of business concept to column name mappings",
    )
    dimensions_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        comment="JSON list of categorical dimension columns",
    )
    measures_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        comment="JSON list of quantitative measure columns",
    )
    confidence_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        comment="JSON dictionary of mapping confidence scores",
    )
    model_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full JSON-serialized SemanticModelSchema payload",
    )

    def __repr__(self) -> str:
        return f"<SemanticModel(id={self.id!r}, dataset_id={self.dataset_id!r}, domain={self.domain!r})>"
