import json
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_dataset_understanding import AIDatasetUnderstandingModel
from app.schemas.ai_dataset import AIDatasetUnderstanding


class AIUnderstandingRepository:
    """
    Repository for PostgreSQL operations on AIDatasetUnderstandingModel entities.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dataset_id(self, dataset_id: str) -> Optional[AIDatasetUnderstandingModel]:
        """Fetch AI understanding by dataset ID."""
        query = select(AIDatasetUnderstandingModel).where(
            AIDatasetUnderstandingModel.dataset_id == dataset_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_understanding(
        self,
        dataset_id: str,
        understanding: AIDatasetUnderstanding,
    ) -> AIDatasetUnderstandingModel:
        """
        Creates or updates an AI understanding record in the database.
        """
        existing = await self.get_by_dataset_id(dataset_id)
        understanding_json = understanding.model_dump_json()

        if existing:
            existing.domain = understanding.domain
            existing.business_summary = understanding.business_summary
            existing.primary_date_column = understanding.primary_date_column
            existing.confidence_score = understanding.confidence_score
            existing.understanding_json = understanding_json
            record = existing
        else:
            record = AIDatasetUnderstandingModel(
                dataset_id=dataset_id,
                domain=understanding.domain,
                business_summary=understanding.business_summary,
                primary_date_column=understanding.primary_date_column,
                confidence_score=understanding.confidence_score,
                understanding_json=understanding_json,
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)
        return record
