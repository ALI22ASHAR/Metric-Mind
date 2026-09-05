import logging
from typing import Optional
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.duckdb_engine import duckdb_engine
from app.db.session import get_db
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardDataResponse,
    DashboardUpdate,
)
from app.schemas.kpi_builder import CustomKpiSpec, KpiPreviewResponse
from app.services.dashboard_service import DashboardService
from app.api.v1.dependencies import require_dashboard_access, require_dataset_access

logger = logging.getLogger(__name__)

# Router for dataset-specific dashboard operations
dataset_dashboards_router = APIRouter(prefix="/datasets/{dataset_id}/dashboards", tags=["Dashboards"], dependencies=[Depends(require_dataset_access)])

# Router for direct dashboard operations
dashboards_router = APIRouter(prefix="/dashboards", tags=["Dashboards"], dependencies=[Depends(require_dashboard_access)])


@dataset_dashboards_router.post(
    "/kpis/preview",
    response_model=KpiPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview a custom KPI specification",
    description="Evaluates dynamic aggregation across Parquet data and returns preview values, breakdown rows, and suggested visual type.",
)
async def preview_custom_kpi(
    dataset_id: str,
    payload: CustomKpiSpec = Body(...),
    db: AsyncSession = Depends(get_db),
) -> KpiPreviewResponse:
    """
    Evaluates dynamic aggregation for a custom KPI specification.
    """
    service = DashboardService(db)
    _, parquet_path, semantic_model, _, _, _ = await service._get_dataset_context(dataset_id)
    return duckdb_engine.compute_custom_kpi(parquet_path, payload, semantic_model)


@dataset_dashboards_router.post(
    "/generate",
    response_model=DashboardDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new AI-planned business dashboard",
    description="Uses the AI dashboard planner to design visual widgets, persists the specification, and hydrates live analytical data via DuckDB.",
)
async def generate_dashboard(
    dataset_id: str,
    payload: Optional[DashboardCreate] = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> DashboardDataResponse:
    """
    Generate an AI-planned dashboard for a dataset.
    """
    title = payload.title if payload else None
    theme = payload.theme if payload else "dark"
    service = DashboardService(db)
    return await service.generate_dashboard(dataset_id=dataset_id, title=title, theme=theme)


@dataset_dashboards_router.get(
    "/default",
    response_model=DashboardDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the primary default dashboard for a dataset",
    description="Retrieves the primary auto-generated dashboard specification along with live evaluated widget data.",
)
async def get_default_dashboard(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> DashboardDataResponse:
    """
    Fetch the default dashboard for a dataset.
    """
    service = DashboardService(db)
    return await service.get_default_dashboard(dataset_id)


@dashboards_router.get(
    "/{dashboard_id}",
    response_model=DashboardDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard by ID with live data hydration",
    description="Returns the declarative dashboard specification with freshly calculated numbers, charts, and table rows.",
)
async def get_dashboard_by_id(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
) -> DashboardDataResponse:
    """
    Fetch a specific dashboard with hydrated live data.
    """
    service = DashboardService(db)
    return await service.get_dashboard(dashboard_id)


@dashboards_router.put(
    "/{dashboard_id}",
    response_model=DashboardDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Update dashboard specification",
    description="Updates dashboard layout, widget configuration, or global filters and re-evaluates live data.",
)
async def update_dashboard(
    dashboard_id: str,
    payload: DashboardUpdate = Body(..., description="Dashboard modifications"),
    db: AsyncSession = Depends(get_db),
) -> DashboardDataResponse:
    """
    Update an existing dashboard.
    """
    service = DashboardService(db)
    return await service.update_dashboard(dashboard_id, payload)


@dashboards_router.delete(
    "/{dashboard_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a dashboard",
    description="Deletes a dashboard specification from the database.",
)
async def delete_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Deletes a dashboard.
    """
    service = DashboardService(db)
    await service.delete_dashboard(dashboard_id)
    return {"dashboard_id": dashboard_id, "deleted": True, "message": "Dashboard deleted successfully."}


@dashboards_router.post(
    "/{dashboard_id}/widgets",
    response_model=DashboardDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a custom KPI widget to a dashboard",
    description="Instantiates and appends a new visual widget based on custom KPI spec and re-hydrates dashboard.",
)
async def add_custom_widget(
    dashboard_id: str,
    payload: CustomKpiSpec = Body(..., description="Custom KPI specification"),
    db: AsyncSession = Depends(get_db),
) -> DashboardDataResponse:
    """
    Adds a custom KPI widget to the dashboard.
    """
    service = DashboardService(db)
    return await service.add_custom_widget(dashboard_id, payload)


@dashboards_router.delete(
    "/{dashboard_id}/widgets/{widget_id}",
    response_model=DashboardDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove a widget from a dashboard",
    description="Removes a visual widget from the dashboard layout and re-hydrates.",
)
async def remove_widget(
    dashboard_id: str,
    widget_id: str,
    db: AsyncSession = Depends(get_db),
) -> DashboardDataResponse:
    """
    Removes a widget from the dashboard.
    """
    service = DashboardService(db)
    return await service.remove_widget(dashboard_id, widget_id)

