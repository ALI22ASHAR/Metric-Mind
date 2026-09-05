import json
import logging
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.semantic_heuristics import semantic_model_builder
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.semantic import SemanticMappingUpdate, SemanticModelSchema
from app.services.profiler_service import ProfilerService

logger = logging.getLogger(__name__)


class SemanticService:
    """
    Business logic layer for generating, validating, and updating dataset semantic models.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.semantic_repo = SemanticRepository(db)
        self.profiler_service = ProfilerService(db)

    async def build_semantic_model(self, dataset_id: str) -> SemanticModelSchema:
        """
        Infers semantic business concepts from column profiling metadata and persists the model.
        """
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )

        logger.info("Generating semantic model for dataset '%s'...", dataset_id)

        # 1. Fetch column profiles
        profile_response = await self.profiler_service.get_dataset_profile(dataset_id)

        # 2. Build semantic schema
        schema = semantic_model_builder.build_semantic_model(
            dataset_id=dataset_id,
            columns_info=profile_response.columns_info,
        )

        # 3. Persist in database
        await self.semantic_repo.save_semantic_model(dataset_id, schema)

        logger.info(
            "Constructed semantic model for dataset '%s': Domain='%s', Mappings=%s",
            dataset_id,
            schema.domain,
            schema.mappings,
        )

        return schema

    async def get_semantic_model(self, dataset_id: str) -> SemanticModelSchema:
        """
        Retrieves the cached semantic model or generates it on demand.
        """
        existing = await self.semantic_repo.get_by_dataset_id(dataset_id)
        if existing:
            data = json.loads(existing.model_data)
            return SemanticModelSchema.model_validate(data)

        # Generate on demand
        return await self.build_semantic_model(dataset_id)

    async def update_semantic_model(
        self,
        dataset_id: str,
        update_data: SemanticMappingUpdate,
    ) -> SemanticModelSchema:
        """
        Updates the semantic model with manual or AI-provided concept overrides,
        strictly validating that all target columns exist in the dataset.
        """
        # Fetch current model and column profiles for validation
        current_model = await self.get_semantic_model(dataset_id)
        profile_res = await self.profiler_service.get_dataset_profile(dataset_id)
        valid_columns = [col.name for col in profile_res.columns_info]

        # Apply updates
        new_mappings = dict(current_model.mappings)
        for concept, target_col in update_data.mappings.items():
            if target_col is None or target_col == "":
                new_mappings.pop(concept, None)
            else:
                if target_col not in valid_columns:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Invalid column '{target_col}' specified for concept '{concept}'. "
                            f"Valid dataset columns: {sorted(valid_columns)}"
                        ),
                    )
                new_mappings[concept] = target_col

        # Update confidence for manually specified mappings
        new_confidence = dict(current_model.confidence_scores)
        for concept in update_data.mappings.keys():
            if concept in new_mappings:
                new_confidence[concept] = 1.0  # Explicitly configured

        # Re-compute unmapped columns
        mapped_cols = set(new_mappings.values())
        unmapped = [c for c in valid_columns if c not in mapped_cols]

        updated_schema = SemanticModelSchema(
            dataset_id=dataset_id,
            domain=update_data.domain or current_model.domain,
            dataset_type=update_data.dataset_type or current_model.dataset_type,
            mappings=new_mappings,
            dimensions=current_model.dimensions,
            measures=current_model.measures,
            time_dimensions=current_model.time_dimensions,
            identifiers=current_model.identifiers,
            confidence_scores=new_confidence,
            unmapped_columns=unmapped,
            created_at=current_model.created_at,
        )

        await self.semantic_repo.save_semantic_model(dataset_id, updated_schema)
        logger.info("Updated semantic model for dataset '%s'", dataset_id)

        return updated_schema
