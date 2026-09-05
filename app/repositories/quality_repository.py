from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset_quality import DatasetQualityReport


class QualityRepository:
    """
    Repository for PostgreSQL operations on DatasetQualityReport entities.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dataset_id(self, dataset_id: str) -> Optional[DatasetQualityReport]:
        """Fetch quality report by dataset ID."""
        query = select(DatasetQualityReport).where(DatasetQualityReport.dataset_id == dataset_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_quality_report(
        self,
        dataset_id: str,
        quality_score: float,
        clean_file_path: str,
        cleaning_policy_json: str,
        report_json: str,
    ) -> DatasetQualityReport:
        """
        Creates or updates a dataset quality report in the database.
        """
        existing = await self.get_by_dataset_id(dataset_id)
        if existing:
            existing.quality_score = quality_score
            existing.clean_file_path = clean_file_path
            existing.cleaning_policy = cleaning_policy_json
            existing.report_data = report_json
            report = existing
        else:
            report = DatasetQualityReport(
                dataset_id=dataset_id,
                quality_score=quality_score,
                clean_file_path=clean_file_path,
                cleaning_policy=cleaning_policy_json,
                report_data=report_json,
            )
            self.db.add(report)

        await self.db.commit()
        await self.db.refresh(report)
        return report
