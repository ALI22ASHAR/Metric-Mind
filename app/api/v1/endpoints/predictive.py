import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.copilot_agent import CopilotActionResponse
from app.db.session import get_db
from app.schemas.benchmark import DatasetBenchmarkResponse
from app.schemas.forecast import ForecastRequest, ForecastResponse
from app.schemas.report import ExecutiveReportResponse
from app.schemas.scenario import ScenarioSimulationRequest, ScenarioSimulationResponse
from app.services.predictive_service import PredictiveService
from app.api.v1.dependencies import require_dataset_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Predictive Analytics & Executive Reporting"])


class BenchmarkRequest(BaseModel):
    target_dataset_id: str


class CopilotCommandRequest(BaseModel):
    command: str


@router.post(
    "/datasets/{dataset_id}/forecast",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate time-series forecast with confidence bands",
)
async def generate_forecast(
    dataset_id: str,
    request: ForecastRequest,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> ForecastResponse:
    """
    Project future metric values using exponential smoothing and linear trend models.
    """
    service = PredictiveService(db)
    return await service.generate_forecast(dataset_id, request)


@router.post(
    "/datasets/{dataset_id}/scenario",
    response_model=ScenarioSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate what-if financial scenarios",
)
async def simulate_scenario(
    dataset_id: str,
    request: ScenarioSimulationRequest,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> ScenarioSimulationResponse:
    """
    Evaluate the bottom-line financial impact of changing price, cost, and volume.
    """
    service = PredictiveService(db)
    return await service.simulate_scenario(dataset_id, request)


@router.get(
    "/datasets/{dataset_id}/report",
    response_model=ExecutiveReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate full executive intelligence narrative report",
)
async def generate_executive_report(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveReportResponse:
    """
    Produce a complete structured executive performance report in JSON and Markdown.
    """
    service = PredictiveService(db)
    return await service.generate_executive_report(dataset_id)


@router.post(
    "/datasets/{dataset_id}/benchmark",
    response_model=DatasetBenchmarkResponse,
    status_code=status.HTTP_200_OK,
    summary="Benchmark dataset against another dataset",
)
async def benchmark_datasets(
    dataset_id: str,
    request: BenchmarkRequest,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> DatasetBenchmarkResponse:
    """
    Compare core performance metrics between two datasets.
    """
    service = PredictiveService(db)
    return await service.benchmark_datasets(dataset_id, request.target_dataset_id)


@router.post(
    "/dashboards/{dashboard_id}/copilot",
    response_model=CopilotActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply natural language dashboard customization",
)
async def apply_copilot_command(
    dashboard_id: str,
    request: CopilotCommandRequest,
    db: AsyncSession = Depends(get_db),
) -> CopilotActionResponse:
    """
    Modify live dashboard specifications via conversational instructions.
    """
    service = PredictiveService(db)
    return await service.apply_copilot_command(dashboard_id, request.command)
