import json
import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.loader import dataset_loader
from app.ingestion.profiler import dataset_profiler
from app.models.dataset import DatasetStatus
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import DatasetProfileResponse

logger = logging.getLogger(__name__)


class ProfilerService:
    """
    Orchestration service for automated data profiling and quality analysis.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.profile_repo = ProfileRepository(db)

    async def profile_dataset(self, dataset_id: str) -> DatasetProfileResponse:
        """
        Profiles the dataset file using Polars, persists the profile in PostgreSQL,
        and transitions the dataset status to READY.
        """
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )

        logger.info("Profiling dataset '%s' (file: %s)...", dataset_id, dataset.file_path)

        # Update status to processing
        await self.dataset_repo.update(
            dataset_id,
            {"status": DatasetStatus.PROCESSING.value},
        )

        try:
            # 1. Load into Polars DataFrame
            df = dataset_loader.load_polars_dataframe(dataset.file_path)

            # 2. Compute statistical profile & quality metrics
            profile_response = dataset_profiler.profile_dataframe(df, dataset_id)

            # 3. Serialize profile response
            profile_json = profile_response.model_dump_json()

            # 4. Save profile entity
            await self.profile_repo.save_profile(
                dataset_id=dataset_id,
                row_count=profile_response.summary.row_count,
                column_count=profile_response.summary.column_count,
                duplicate_rows=profile_response.summary.duplicate_rows,
                quality_warnings_count=len(profile_response.quality_warnings),
                profile_json=profile_json,
            )

            # 5. Mark dataset as ready
            await self.dataset_repo.update(
                dataset_id,
                {
                    "status": DatasetStatus.READY.value,
                    "row_count": profile_response.summary.row_count,
                    "column_count": profile_response.summary.column_count,
                    "error_message": None,
                },
            )

            logger.info(
                "Completed profiling for dataset '%s' (%d rows, %d cols, %d warnings)",
                dataset_id,
                profile_response.summary.row_count,
                profile_response.summary.column_count,
                len(profile_response.quality_warnings),
            )

            return profile_response

        except Exception as exc:
            logger.error("Profiling failed for dataset '%s': %s", dataset_id, exc, exc_info=True)
            await self.dataset_repo.update(
                dataset_id,
                {
                    "status": DatasetStatus.FAILED.value,
                    "error_message": f"Profiling error: {str(exc)}",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to profile dataset: {str(exc)}",
            )

    async def get_dataset_profile(self, dataset_id: str) -> DatasetProfileResponse:
        """
        Retrieves the cached profile of a dataset or calculates it if missing.
        """
        # Check if cached profile exists
        existing_profile = await self.profile_repo.get_by_dataset_id(dataset_id)
        if existing_profile:
            data = json.loads(existing_profile.profile_data)
            return DatasetProfileResponse.model_validate(data)

        # Otherwise trigger on-demand profiling
        return await self.profile_dataset(dataset_id)
