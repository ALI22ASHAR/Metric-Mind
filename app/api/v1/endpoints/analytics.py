import logging
from typing import Any, List
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import (
    BreakdownRequest,
    BreakdownResponse,
    RawQueryRequest,
    RawQueryResponse,
)
from app.schemas.metrics import DatasetMetricsSummary, MetricDefinition
from app.schemas.timeseries import TimeSeriesRequest, TimeSeriesResponse
from app.services.analytics_service import AnalyticsService
from app.api.v1.dependencies import require_dataset_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Analytics & KPIs"], dependencies=[Depends(require_dataset_access)])


@router.get(
    "/metrics/available",
    response_model=List[MetricDefinition],
    status_code=status.HTTP_200_OK,
    summary="List computable business metrics",
    description="Returns all KPIs that can be deterministically calculated based on the dataset's semantic mappings.",
)
async def get_available_metrics(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[MetricDefinition]:
    """
    List computable metrics for a dataset.
    """
    service = AnalyticsService(db)
    return await service.get_available_metrics(dataset_id)


@router.get(
    "/metrics/summary",
    response_model=DatasetMetricsSummary,
    status_code=status.HTTP_200_OK,
    summary="Get calculated KPI summary values",
    description="Computes all available business metrics (Total Revenue, Cost, Profit, Margin, Units, Orders, AOV) in DuckDB.",
)
async def get_metrics_summary(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> DatasetMetricsSummary:
    """
    Calculates executive KPI summary values.
    """
    service = AnalyticsService(db)
    return await service.get_metrics_summary(dataset_id)


@router.post(
    "/metrics/summary",
    response_model=DatasetMetricsSummary,
    status_code=status.HTTP_200_OK,
    summary="Get calculated KPI summary values with filters",
    description="Computes all available business metrics with dimensional filtering in DuckDB.",
)
async def get_filtered_metrics_summary(
    dataset_id: str,
    filters: List[Any] = Body(default=[]),
    db: AsyncSession = Depends(get_db),
) -> DatasetMetricsSummary:
    from app.schemas.analytics import DimensionFilter
    parsed_filters = [DimensionFilter(**f) if isinstance(f, dict) else f for f in filters]
    service = AnalyticsService(db)
    return await service.get_metrics_summary(dataset_id, filters=parsed_filters)



@router.get(
    "/analytics/kpi-breakdown",
    status_code=status.HTTP_200_OK,
    summary="Get multi-dimensional breakdown for a KPI",
    description="Returns top ranked breakdowns across all discovered categorical dimensions (Country, Category, Product, etc.) for a single KPI.",
)
async def get_kpi_breakdown(
    dataset_id: str,
    metric: str = "total_revenue",
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.compute_kpi_multi_breakdown(dataset_id, metric)


@router.post(
    "/analytics/breakdown",
    response_model=BreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute multi-dimensional KPI breakdown",
    description="Groups requested metrics by a categorical dimension (e.g. Category, City, Region) with filtering and sorting in DuckDB.",
)
async def compute_breakdown(
    dataset_id: str,
    request: BreakdownRequest = Body(..., description="Breakdown parameters"),
    db: AsyncSession = Depends(get_db),
) -> BreakdownResponse:
    """
    Computes dimensional aggregation breakdown.
    """
    service = AnalyticsService(db)
    return await service.compute_breakdown(dataset_id, request)


@router.post(
    "/analytics/timeseries",
    response_model=TimeSeriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute time-series trends and growth rates",
    description="Aggregates metrics chronologically across day/week/month/quarter/year intervals and computes MoM, QoQ, YoY growth rates.",
)
async def compute_timeseries(
    dataset_id: str,
    request: TimeSeriesRequest = Body(..., description="Time-series parameters"),
    db: AsyncSession = Depends(get_db),
) -> TimeSeriesResponse:
    """
    Computes time-series trend points and period-over-period growth.
    """
    service = AnalyticsService(db)
    return await service.compute_timeseries(dataset_id, request)


@router.post(
    "/analytics/query",
    response_model=RawQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute safe read-only SQL query in DuckDB",
    description="Runs a read-only analytical SQL query against the dataset's clean Parquet file.",
)
async def execute_query(
    dataset_id: str,
    request: RawQueryRequest = Body(..., description="SQL query"),
    db: AsyncSession = Depends(get_db),
) -> RawQueryResponse:
    """
    Executes a raw read-only SQL analytical query.
    """
    service = AnalyticsService(db)
    return await service.execute_raw_query(dataset_id, request)


@router.get(
    "/analytics/geo-breakdown",
    status_code=status.HTTP_200_OK,
    summary="Get geographic metrics distribution for map visualization",
    description="Returns regional and country performance with normalized coordinate centers and share percentages.",
)
async def get_geo_breakdown(
    dataset_id: str,
    metric: str = "total_revenue",
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.compute_geo_breakdown(dataset_id, metric)


@router.post(
    "/analytics/geo-breakdown",
    status_code=status.HTTP_200_OK,
    summary="Get geographic metrics distribution with filters",
)
async def get_filtered_geo_breakdown(
    dataset_id: str,
    metric: str = "total_revenue",
    filters: List[Any] = Body(default=[]),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.analytics import DimensionFilter
    parsed_filters = [DimensionFilter(**f) if isinstance(f, dict) else f for f in filters]
    service = AnalyticsService(db)
    return await service.compute_geo_breakdown(dataset_id, metric, filters=parsed_filters)



@router.post(
    "/metrics/custom",
    response_model=MetricDefinition,
    status_code=status.HTTP_201_CREATED,
    summary="Register user-defined custom formula metric",
    description="Validates mathematical formula and registers a new computable custom KPI.",
)
async def create_custom_metric(
    dataset_id: str,
    request: Any = Body(...),
    db: AsyncSession = Depends(get_db),
) -> MetricDefinition:
    from app.analytics.formula_engine import CustomMetricRequest
    metric_req = CustomMetricRequest(**request) if isinstance(request, dict) else request
    service = AnalyticsService(db)
    return await service.register_custom_metric(dataset_id, metric_req)


@router.get(
    "/metrics/custom",
    response_model=List[MetricDefinition],
    status_code=status.HTTP_200_OK,
    summary="List custom metrics for dataset",
)
async def list_custom_metrics(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[MetricDefinition]:
    service = AnalyticsService(db)
    return await service.get_custom_metrics(dataset_id)


@router.get(
    "/analytics/dimensions/{dimension}/values",
    response_model=List[str],
    status_code=status.HTTP_200_OK,
    summary="Get distinct categorical dimension values",
    description="Returns distinct values for a dimension column to populate dropdown filters.",
)
async def get_dimension_values(
    dataset_id: str,
    dimension: str,
    db: AsyncSession = Depends(get_db),
) -> List[str]:
    service = AnalyticsService(db)
    return await service.get_dimension_values(dataset_id, dimension)


