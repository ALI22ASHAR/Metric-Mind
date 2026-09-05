from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import Dashboard
from app.schemas.dashboard import DashboardSpec


class DashboardRepository:
    """
    Repository for PostgreSQL operations on Dashboard entities.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, dashboard_id: str) -> Optional[Dashboard]:
        """Fetch dashboard by ID."""
        query = select(Dashboard).where(Dashboard.id == dashboard_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_default_by_dataset_id(self, dataset_id: str) -> Optional[Dashboard]:
        """Fetch primary default dashboard for a dataset."""
        query = (
            select(Dashboard)
            .where(Dashboard.dataset_id == dataset_id, Dashboard.is_default == True)
            .order_by(Dashboard.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_dataset_id(self, dataset_id: str) -> List[Dashboard]:
        """List all dashboards associated with a dataset."""
        query = (
            select(Dashboard)
            .where(Dashboard.dataset_id == dataset_id)
            .order_by(Dashboard.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_dashboard(
        self,
        dataset_id: str,
        spec: DashboardSpec,
        is_default: bool = True,
    ) -> Dashboard:
        """
        Creates or updates a dashboard record in PostgreSQL.
        """
        existing = await self.get_by_id(spec.id)
        spec_json = spec.model_dump_json()

        if existing:
            existing.title = spec.title
            existing.subtitle = spec.subtitle
            existing.theme = spec.theme
            existing.spec_json = spec_json
            existing.is_default = is_default
            record = existing
        else:
            record = Dashboard(
                id=spec.id,
                dataset_id=dataset_id,
                title=spec.title,
                subtitle=spec.subtitle,
                theme=spec.theme,
                is_default=is_default,
                spec_json=spec_json,
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def update(self, dashboard: Dashboard) -> Dashboard:
        """Update an existing dashboard model in database."""
        self.db.add(dashboard)
        await self.db.commit()
        await self.db.refresh(dashboard)
        return dashboard

    async def delete(self, dashboard_id: str) -> bool:
        """Delete a dashboard by ID."""
        record = await self.get_by_id(dashboard_id)
        if record:
            await self.db.delete(record)
            await self.db.commit()
            return True
        return False

