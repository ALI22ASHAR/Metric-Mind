from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset


class DatasetRepository:
    """
    Repository for PostgreSQL operations on Dataset entities.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, dataset: Dataset) -> Dataset:
        """Persist a new dataset entity."""
        self.db.add(dataset)
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def get_by_id(self, dataset_id: str, workspace_id: Optional[str] = None) -> Optional[Dataset]:
        """Fetch a dataset by its unique identifier."""
        query = select(Dataset).where(Dataset.id == dataset_id)
        if workspace_id:
            query = query.where(Dataset.workspace_id == workspace_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 50,
        workspace_id: Optional[str] = None,
    ) -> Tuple[List[Dataset], int]:
        """
        List datasets with pagination, ordered by creation time descending.
        Returns (list_of_datasets, total_count).
        """
        count_query = select(func.count(Dataset.id))
        if workspace_id:
            count_query = count_query.where(Dataset.workspace_id == workspace_id)
        total_count = (await self.db.execute(count_query)).scalar_one()

        list_query = (
            select(Dataset)
            .order_by(Dataset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if workspace_id:
            list_query = list_query.where(Dataset.workspace_id == workspace_id)
        result = await self.db.execute(list_query)
        datasets = list(result.scalars().all())

        return datasets, total_count

    async def update(self, dataset_id: str, update_data: dict) -> Optional[Dataset]:
        """Update dataset attributes."""
        dataset = await self.get_by_id(dataset_id)
        if not dataset:
            return None

        for key, value in update_data.items():
            if hasattr(dataset, key) and value is not None:
                setattr(dataset, key, value)

        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def delete(self, dataset_id: str) -> bool:
        """Delete a dataset from the database."""
        dataset = await self.get_by_id(dataset_id)
        if not dataset:
            return False

        await self.db.delete(dataset)
        await self.db.commit()
        return True
