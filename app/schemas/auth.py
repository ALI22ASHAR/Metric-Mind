from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    full_name: Optional[str] = Field(None, description="Full name")
    workspace_name: Optional[str] = Field(None, description="Initial workspace name")


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    workspace_id: str


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    role: str = "owner"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    workspaces: List[WorkspaceResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
