import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.copilot_agent import dashboard_copilot_agent, CopilotActionResponse
from app.ai.report_generator import executive_report_generator
from app.analytics.benchmark_engine import benchmark_engine
from app.analytics.forecasting_engine import forecasting_engine
from app.analytics.scenario_engine import scenario_simulation_engine
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.benchmark import DatasetBenchmarkResponse
from app.schemas.dashboard import DashboardSpec
from app.schemas.forecast import ForecastRequest, ForecastResponse
from app.schemas.report import ExecutiveReportResponse
from app.schemas.scenario import ScenarioSimulationRequest, ScenarioSimulationResponse
from app.services.ai_dataset_service import AIDatasetService
from app.services.analytics_service import AnalyticsService
from app.services.insights_service import InsightsService
from app.services.profiler_service import ProfilerService
from app.services.quality_service import QualityService
from app.services.semantic_service import SemanticService

logger = logging.getLogger(__name__)


class PredictiveService:
    """
    Coordinates time-series forecasting, what-if scenario simulations,
    executive report generation, and multi-dataset benchmarking.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.dashboard_repo = DashboardRepository(db)
        self.semantic_service = SemanticService(db)
        self.analytics_service = AnalyticsService(db)
        self.quality_service = QualityService(db)
        self.insights_service = InsightsService(db)
        self.ai_service = AIDatasetService(db)

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
        return dataset, parquet_path, semantic_model

    async def generate_forecast(
        self,
        dataset_id: str,
        request: ForecastRequest,
    ) -> ForecastResponse:
        """
        Calculates time-series projection with confidence bands.
        """
        _, parquet_path, semantic_model = await self._get_dataset_context(dataset_id)
        return forecasting_engine.generate_forecast(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            semantic_model=semantic_model,
            request=request,
        )

    async def simulate_scenario(
        self,
        dataset_id: str,
        request: ScenarioSimulationRequest,
    ) -> ScenarioSimulationResponse:
        """
        Simulates what-if pricing, volume, and cost changes.
        """
        _, parquet_path, semantic_model = await self._get_dataset_context(dataset_id)
        return scenario_simulation_engine.simulate_scenario(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            semantic_model=semantic_model,
            request=request,
        )

    async def generate_executive_report(self, dataset_id: str) -> ExecutiveReportResponse:
        """
        Synthesizes an end-to-end executive brief.
        """
        _, _, semantic_model = await self._get_dataset_context(dataset_id)
        metrics_summary = await self.analytics_service.get_metrics_summary(dataset_id)

        try:
            quality_report = await self.quality_service.get_quality_report(dataset_id)
        except Exception:
            quality_report = None

        try:
            insights_summary = await self.insights_service.get_dataset_insights(dataset_id)
        except Exception:
            insights_summary = None

        try:
            anomalies_summary = await self.insights_service.get_dataset_anomalies(dataset_id)
        except Exception:
            anomalies_summary = None

        try:
            ai_understanding = await self.ai_service.get_understanding(dataset_id)
        except Exception:
            ai_understanding = None

        return executive_report_generator.generate_report(
            dataset_id=dataset_id,
            domain=semantic_model.domain,
            quality_report=quality_report,
            semantic_model=semantic_model,
            kpi_results=metrics_summary.metrics,
            insights_summary=insights_summary,
            anomalies_summary=anomalies_summary,
            ai_understanding=ai_understanding,
        )

    async def benchmark_datasets(
        self,
        base_dataset_id: str,
        target_dataset_id: str,
    ) -> DatasetBenchmarkResponse:
        """
        Compares core KPI metrics between two datasets.
        """
        _, base_parquet, base_semantic = await self._get_dataset_context(base_dataset_id)
        _, target_parquet, target_semantic = await self._get_dataset_context(target_dataset_id)
        metrics = await self.analytics_service.get_available_metrics(base_dataset_id)

        return benchmark_engine.compare_datasets(
            base_dataset_id=base_dataset_id,
            base_parquet=base_parquet,
            base_semantic=base_semantic,
            target_dataset_id=target_dataset_id,
            target_parquet=target_parquet,
            target_semantic=target_semantic,
            metrics=metrics,
        )

    async def apply_copilot_command(
        self,
        dashboard_id: str,
        command: str,
    ) -> CopilotActionResponse:
        """
        Applies natural-language dashboard edits.
        """
        dash = await self.dashboard_repo.get_by_id(dashboard_id)
        if not dash:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard '{dashboard_id}' not found.",
            )

        current_spec = DashboardSpec.model_validate_json(dash.spec_json)
        res = dashboard_copilot_agent.apply_copilot_command(command, current_spec)

        dash.title = res.modified_spec.title
        dash.spec_json = res.modified_spec.model_dump_json()
        await self.dashboard_repo.update(dash)

        return res
