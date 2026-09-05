import json
import logging
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import BaseLLMProvider
from app.ai.schema_agent import schema_understanding_agent
from app.repositories.ai_understanding_repository import AIUnderstandingRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.semantic import SemanticMappingUpdate
from app.services.profiler_service import ProfilerService
from app.services.semantic_service import SemanticService

logger = logging.getLogger(__name__)


class AIDatasetService:
    """
    Service layer orchestrating the AI Dataset Understanding Agent.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.ai_repo = AIUnderstandingRepository(db)
        self.profiler_service = ProfilerService(db)
        self.semantic_service = SemanticService(db)

    async def generate_understanding(
        self,
        dataset_id: str,
        provider: Optional[BaseLLMProvider] = None,
    ) -> AIDatasetUnderstanding:
        """
        Executes the AI schema understanding agent, persists the synthesis,
        and syncs refined mappings into the semantic model.
        """
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )

        logger.info("Executing AI understanding analysis for dataset '%s'...", dataset_id)

        # 1. Fetch profiling and semantic model
        profile = await self.profiler_service.get_dataset_profile(dataset_id)
        semantic_model = await self.semantic_service.get_semantic_model(dataset_id)

        # 2. Run agent
        understanding = await schema_understanding_agent.analyze_dataset(
            dataset_id=dataset_id,
            profile=profile,
            semantic_model=semantic_model,
            provider=provider,
        )

        # 3. Persist in database
        await self.ai_repo.save_understanding(dataset_id, understanding)

        # 4. Sync refined mappings back into SemanticModel if any exist
        if understanding.refined_mappings:
            try:
                await self.semantic_service.update_semantic_model(
                    dataset_id=dataset_id,
                    update_data=SemanticMappingUpdate(
                        domain=understanding.domain,
                        dataset_type="ai_refined",
                        mappings=understanding.refined_mappings,
                    ),
                )
            except Exception as exc:
                logger.warning("Could not sync AI refined mappings to SemanticModel: %s", exc)

        logger.info(
            "AI Understanding completed for '%s': Domain='%s', Hierarchies=%s",
            dataset_id,
            understanding.domain,
            understanding.dimension_hierarchies,
        )

        return understanding

    async def get_understanding(
        self,
        dataset_id: str,
    ) -> AIDatasetUnderstanding:
        """
        Retrieves cached AI understanding or generates it on demand.
        """
        existing = await self.ai_repo.get_by_dataset_id(dataset_id)
        if existing:
            data = json.loads(existing.understanding_json)
            return AIDatasetUnderstanding.model_validate(data)

        # Generate on demand
        return await self.generate_understanding(dataset_id)
