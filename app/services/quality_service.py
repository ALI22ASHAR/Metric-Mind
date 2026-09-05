import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.loader import dataset_loader
from app.ingestion.normalizer import dataset_normalizer
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.quality_repository import QualityRepository
from app.schemas.quality import CleaningPolicy, DataQualityReport

logger = logging.getLogger(__name__)


class QualityService:
    """
    Service coordinating dataset quality evaluation, normalization,
    Parquet persistence, and audit logging.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.quality_repo = QualityRepository(db)

    async def normalize_dataset(
        self,
        dataset_id: str,
        policy: Optional[CleaningPolicy] = None,
    ) -> DataQualityReport:
        """
        Executes data quality checks and normalization rules on raw dataset,
        exports clean_data.parquet, and persists quality report.
        """
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )

        policy = policy or CleaningPolicy()
        raw_path = Path(dataset.file_path)
        output_dir = raw_path.parent

        logger.info("Executing normalization on dataset '%s' (raw: %s)...", dataset_id, dataset.file_path)

        try:
            # 1. Load raw dataframe
            raw_df = dataset_loader.load_polars_dataframe(raw_path)

            # 2. Run normalization and quality scoring
            clean_df, report, clean_file_path = dataset_normalizer.normalize_dataset(
                raw_df=raw_df,
                dataset_id=dataset_id,
                output_dir=output_dir,
                policy=policy,
            )

            # 3. Update dataset record with clean file path
            await self.dataset_repo.update(
                dataset_id,
                {
                    "clean_file_path": clean_file_path,
                },
            )

            # 4. Save quality report in database
            await self.quality_repo.save_quality_report(
                dataset_id=dataset_id,
                quality_score=report.quality_score,
                clean_file_path=clean_file_path,
                cleaning_policy_json=policy.model_dump_json(),
                report_json=report.model_dump_json(),
            )

            logger.info(
                "Completed normalization for dataset '%s': Quality Score %.1f/100, Clean Rows: %d (Parquet: %s)",
                dataset_id,
                report.quality_score,
                report.clean_rows,
                clean_file_path,
            )

            return report

        except Exception as exc:
            logger.error("Normalization failed for dataset '%s': %s", dataset_id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to normalize dataset: {str(exc)}",
            )

    async def get_quality_report(self, dataset_id: str) -> DataQualityReport:
        """
        Retrieves existing data quality report or executes initial normalization.
        """
        existing = await self.quality_repo.get_by_dataset_id(dataset_id)
        if existing:
            data = json.loads(existing.report_data)
            return DataQualityReport.model_validate(data)

        # Generate on demand
        return await self.normalize_dataset(dataset_id)
