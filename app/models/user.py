import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def generate_user_id() -> str:
    return f"usr_{uuid.uuid4().hex[:12]}"


def generate_workspace_id() -> str:
    return f"wsp_{uuid.uuid4().hex[:12]}"


class User(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing registered users.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_user_id,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, email={self.email!r})>"


class Workspace(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing multi-tenant business workspaces.
    """
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_workspace_id,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Default Workspace",
    )
    owner_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id!r}, name={self.name!r})>"


class WorkspaceMember(Base, TimestampMixin):
    """
    Association table linking users to workspaces with access roles.
    """
    __tablename__ = "workspace_members"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"wsm_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="owner",  # "owner", "admin", "member", "viewer"
    )
