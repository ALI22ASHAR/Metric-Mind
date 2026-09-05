import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def generate_session_id() -> str:
    return f"ses_{uuid.uuid4().hex[:12]}"


def generate_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


class ChatSession(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing multi-turn conversational chat sessions.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_session_id,
        index=True,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated dataset identifier",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Data Analysis Conversation",
        comment="Session title or topic",
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id!r}, dataset_id={self.dataset_id!r}, title={self.title!r})>"


class ChatMessageModel(Base, TimestampMixin):
    """
    SQLAlchemy ORM Model storing individual conversational chat messages.
    """
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_message_id,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent chat session identifier",
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Message role: user, assistant, system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text content",
    )
    sql_query: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Executed DuckDB SQL query if applicable",
    )
    chart_type: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        comment="Rendered chart visualization type",
    )
    data_json: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-serialized query result data",
    )

    def __repr__(self) -> str:
        return f"<ChatMessageModel(id={self.id!r}, session_id={self.session_id!r}, role={self.role!r})>"
