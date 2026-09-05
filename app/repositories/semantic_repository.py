import json
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic_model import SemanticModel
from app.schemas.semantic import SemanticModelSchema


class SemanticRepository:
    """
    Repository for PostgreSQL operations on SemanticModel entities.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dataset_id(self, dataset_id: str) -> Optional[SemanticModel]:
        """Fetch semantic model by dataset ID."""
        query = select(SemanticModel).where(SemanticModel.dataset_id == dataset_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_semantic_model(
        self,
        dataset_id: str,
        schema: SemanticModelSchema,
    ) -> SemanticModel:
        """
        Creates or updates a semantic model record in the database.
        """
        existing = await self.get_by_dataset_id(dataset_id)
        mappings_json = json.dumps(schema.mappings)
        dimensions_json = json.dumps(schema.dimensions)
        measures_json = json.dumps(schema.measures)
        confidence_json = json.dumps(schema.confidence_scores)
        model_data_json = schema.model_dump_json()

        if existing:
            existing.domain = schema.domain
            existing.dataset_type = schema.dataset_type
            existing.mappings_json = mappings_json
            existing.dimensions_json = dimensions_json
            existing.measures_json = measures_json
            existing.confidence_json = confidence_json
            existing.model_data = model_data_json
            record = existing
        else:
            record = SemanticModel(
                dataset_id=dataset_id,
                domain=schema.domain,
                dataset_type=schema.dataset_type,
                mappings_json=mappings_json,
                dimensions_json=dimensions_json,
                measures_json=measures_json,
                confidence_json=confidence_json,
                model_data=model_data_json,
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)
        return record
