import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessageModel, ChatSession


class ChatRepository:
    """
    Database access layer for persistent multi-turn chat sessions and messages.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_default_session(self, dataset_id: str) -> ChatSession:
        """Fetch the default chat session for a dataset or create one."""
        query = (
            select(ChatSession)
            .where(ChatSession.dataset_id == dataset_id)
            .order_by(ChatSession.created_at.asc())
        )
        result = await self.db.execute(query)
        session = result.scalars().first()

        if not session:
            session = ChatSession(
                dataset_id=dataset_id,
                title="Primary Analysis Thread",
            )
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)

        return session

    async def create_session(self, dataset_id: str, title: str) -> ChatSession:
        """Create a new conversational session."""
        session = ChatSession(
            dataset_id=dataset_id,
            title=title,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_sessions(self, dataset_id: str) -> List[ChatSession]:
        """List all chat sessions for a dataset."""
        query = (
            select(ChatSession)
            .where(ChatSession.dataset_id == dataset_id)
            .order_by(ChatSession.updated_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sql_query: Optional[str] = None,
        chart_type: Optional[str] = None,
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatMessageModel:
        """Append a message to a session."""
        data_json = json.dumps(data) if data else None
        msg = ChatMessageModel(
            session_id=session_id,
            role=role,
            content=content,
            sql_query=sql_query,
            chart_type=chart_type,
            data_json=data_json,
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def get_messages(self, session_id: str, limit: int = 50) -> List[ChatMessageModel]:
        """Fetch chronological message history for a session."""
        query = (
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
