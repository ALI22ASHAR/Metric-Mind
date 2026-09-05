import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse, WorkspaceResponse

logger = logging.getLogger(__name__)


class AuthService:
    """
    Handles user registration, authentication, JWT token issuance, and workspace provisioning.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(self, payload: UserCreate) -> TokenResponse:
        """Register a new user and provision their default workspace."""
        existing = await self.user_repo.get_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
            )

        hashed = hash_password(payload.password)
        user = await self.user_repo.create_user(
            email=payload.email,
            hashed_password=hashed,
            full_name=payload.full_name,
        )

        ws_name = payload.workspace_name or f"{user.full_name or 'My'} Workspace"
        workspace = await self.user_repo.create_workspace(name=ws_name, owner_id=user.id)

        token_data = {"sub": user.id, "email": user.email, "workspace_id": workspace.id}
        token = create_access_token(token_data)

        return TokenResponse(
            access_token=token,
            user_id=user.id,
            email=user.email,
            workspace_id=workspace.id,
        )

    async def login(self, payload: UserLogin) -> TokenResponse:
        """Authenticate user and return JWT access token."""
        user = await self.user_repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        workspaces = await self.user_repo.get_user_workspaces(user.id)
        active_ws_id = workspaces[0].id if workspaces else "default"

        token_data = {"sub": user.id, "email": user.email, "workspace_id": active_ws_id}
        token = create_access_token(token_data)

        return TokenResponse(
            access_token=token,
            user_id=user.id,
            email=user.email,
            workspace_id=active_ws_id,
        )

    async def get_current_user_profile(self, user_id: str) -> UserResponse:
        """Retrieve user profile with accessible workspaces."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        workspaces = await self.user_repo.get_user_workspaces(user.id)
        ws_responses = [
            WorkspaceResponse(
                id=ws.id,
                name=ws.name,
                role="owner" if ws.owner_id == user.id else "member",
                created_at=ws.created_at,
            )
            for ws in workspaces
        ]

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            workspaces=ws_responses,
            created_at=user.created_at,
        )
