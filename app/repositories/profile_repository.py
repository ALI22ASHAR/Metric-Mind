from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset_profile import DatasetProfile


class ProfileRepository:
    """
    Repository for PostgreSQL operations on DatasetProfile entities.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dataset_id(self, dataset_id: str) -> Optional[DatasetProfile]:
        """Fetch profile by dataset ID."""
        query = select(DatasetProfile).where(DatasetProfile.dataset_id == dataset_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_profile(
        self,
        dataset_id: str,
        row_count: int,
        column_count: int,
        duplicate_rows: int,
        quality_warnings_count: int,
        profile_json: str,
    ) -> DatasetProfile:
        """
        Creates or updates a dataset profile in the database.
        """
        existing = await self.get_by_dataset_id(dataset_id)
        if existing:
            existing.row_count = row_count
            existing.column_count = column_count
            existing.duplicate_rows = duplicate_rows
            existing.quality_warnings_count = quality_warnings_count
            existing.profile_data = profile_json
            profile = existing
        else:
            profile = DatasetProfile(
                dataset_id=dataset_id,
                row_count=row_count,
                column_count=column_count,
                duplicate_rows=duplicate_rows,
                quality_warnings_count=quality_warnings_count,
                profile_data=profile_json,
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile
