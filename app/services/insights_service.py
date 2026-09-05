import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.anomaly_engine import anomaly_engine
from app.analytics.insights_engine import business_insights_engine
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.anomalies import AnomalyReportResponse
from app.schemas.insights import DatasetInsightsSummary
from app.services.analytics_service import AnalyticsService
from app.services.semantic_service import SemanticService

logger = logging.getLogger(__name__)


class InsightsService:
    """
    Orchestrates automated business insight computation, statistical anomaly detection,
    and root cause decomposition.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.semantic_service = SemanticService(db)
        self.analytics_service = AnalyticsService(db)

    async def _get_dataset_context(self, dataset_id: str):
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )

        parquet_path = dataset.clean_file_path or dataset.file_path
        if not parquet_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset '{dataset_id}' has not been normalized into clean analytical format.",
            )

        semantic_model = await self.semantic_service.get_semantic_model(dataset_id)
        available_metrics = await self.analytics_service.get_available_metrics(dataset_id)

        return dataset, parquet_path, semantic_model, available_metrics

    async def get_dataset_insights(self, dataset_id: str) -> DatasetInsightsSummary:
        """
        Computes executive business insights, Pareto concentration, and growth drivers.
        """
        _, parquet_path, semantic_model, available_metrics = await self._get_dataset_context(dataset_id)

        return business_insights_engine.compute_insights(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            semantic_model=semantic_model,
            available_metrics=available_metrics,
        )

    async def get_dataset_anomalies(self, dataset_id: str) -> AnomalyReportResponse:
        """
        Detects statistical anomalies across time-series metrics and decomposes root causes.
        """
        _, parquet_path, semantic_model, _ = await self._get_dataset_context(dataset_id)

        return anomaly_engine.detect_anomalies(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            semantic_model=semantic_model,
        )
