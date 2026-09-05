from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Workspace, WorkspaceMember


class UserRepository:
    """
    Data access layer for Users, Workspaces, and Tenant Memberships.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        query = select(User).where(User.email == email.lower().strip())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> Optional[User]:
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, email: str, hashed_password: str, full_name: Optional[str] = None) -> User:
        user = User(
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create_workspace(self, name: str, owner_id: str) -> Workspace:
        ws = Workspace(name=name, owner_id=owner_id)
        self.db.add(ws)
        await self.db.commit()
        await self.db.refresh(ws)

        member = WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role="owner")
        self.db.add(member)
        await self.db.commit()

        return ws

    async def get_user_workspaces(self, user_id: str) -> List[Workspace]:
        query = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
