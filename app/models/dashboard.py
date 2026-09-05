import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def generate_dashboard_id() -> str:
    """Generate a prefixed unique dashboard identifier."""
    return f"dsh_{uuid.uuid4().hex[:12]}"


class Dashboard(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing declarative dashboard specifications.
    """
    __tablename__ = "dashboards"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_dashboard_id,
        index=True,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated dataset ID",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Executive Business Intelligence Dashboard",
        comment="Dashboard title",
    )
    subtitle: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Dashboard subtitle or description",
    )
    theme: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="dark",
        comment="Visual theme (dark / light)",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is the primary auto-generated dashboard for the dataset",
    )
    spec_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full JSON-serialized DashboardSpec payload",
    )

    def __repr__(self) -> str:
        return f"<Dashboard(id={self.id!r}, dataset_id={self.dataset_id!r}, title={self.title!r})>"
