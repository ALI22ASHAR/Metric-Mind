from typing import Optional

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.dashboard_repository import DashboardRepository


async def get_workspace_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    if not settings.REQUIRE_AUTH:
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    workspace_id = payload.get("workspace_id") if payload else None
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active workspace is associated with this token.")
    return workspace_id


async def require_dataset_access(
    dataset_id: str = Path(...),
    workspace_id: Optional[str] = Depends(get_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not workspace_id:
        return
    dataset = await DatasetRepository(db).get_by_id(dataset_id)
    if not dataset or dataset.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")


async def require_dashboard_access(
    dashboard_id: str = Path(...),
    workspace_id: Optional[str] = Depends(get_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not workspace_id:
        return
    dashboard = await DashboardRepository(db).get_by_id(dashboard_id)
    dataset = await DatasetRepository(db).get_by_id(dashboard.dataset_id) if dashboard else None
    if not dashboard or not dataset or dataset.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")