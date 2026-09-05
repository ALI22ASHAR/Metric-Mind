import json
import logging
import time
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.dashboard_planner import ai_dashboard_planner
from app.analytics.duckdb_engine import duckdb_engine
from app.analytics.metric_registry import metric_capability_analyzer
from app.analytics.timeseries import timeseries_engine
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dashboard import (
    DashboardDataResponse,
    DashboardSpec,
    DashboardUpdate,
    GridPosition,
    WidgetConfig,
    WidgetType,
)
from app.schemas.kpi_builder import CustomKpiSpec
from app.schemas.profile import WarningSeverity
from app.schemas.semantic import SemanticModelSchema
from app.schemas.timeseries import TimeSeriesGranularity
from app.services.ai_dataset_service import AIDatasetService
from app.services.analytics_service import AnalyticsService
from app.services.profiler_service import ProfilerService
from app.services.semantic_service import SemanticService

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Business service layer orchestrating AI dashboard planning, PostgreSQL persistence,
    and live analytical data hydration via DuckDB.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.dashboard_repo = DashboardRepository(db)
        self.semantic_service = SemanticService(db)
        self.ai_service = AIDatasetService(db)
        self.analytics_service = AnalyticsService(db)
        self.profiler_service = ProfilerService(db)

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
        try:
            ai_understanding = await self.ai_service.get_understanding(dataset_id)
        except Exception:
            ai_understanding = None

        # Pull profiler quality signals for the confidence score.
        try:
            profile = await self.profiler_service.get_dataset_profile(dataset_id)
            quality_warnings_count = len(profile.quality_warnings)
            critical_warnings_count = sum(
                1 for w in profile.quality_warnings if w.severity == WarningSeverity.CRITICAL
            )
            # Average null percentage across all columns
            if profile.columns_info:
                avg_null_pct = sum(c.null_percentage for c in profile.columns_info) / len(profile.columns_info)
            else:
                avg_null_pct = 0.0
            quality_context = {
                "row_count": profile.summary.row_count,
                "avg_null_percentage": avg_null_pct,
                "quality_warnings_count": quality_warnings_count,
                "critical_warnings_count": critical_warnings_count,
            }
        except Exception:
            quality_context = None

        return dataset, parquet_path, semantic_model, available_metrics, ai_understanding, quality_context

    def hydrate_dashboard(
        self,
        spec: DashboardSpec,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        quality_context: Optional[Dict[str, Any]] = None,
    ) -> DashboardDataResponse:
        """
        Executes live DuckDB analytical queries for every widget in the dashboard specification.
        """
        start_time = time.perf_counter()
        widget_data: Dict[str, Any] = {}

        # 1. Pre-fetch KPI summary for KPI cards
        kpi_summary = duckdb_engine.compute_kpi_summary(parquet_path, semantic_model)
        computable_map = {m.id: m for m in metric_capability_analyzer.get_computable_metrics(semantic_model)}

        for widget in spec.widgets:
            w_id = widget.id
            w_type = widget.type

            try:
                # 0. Handle user-defined self-service Custom KPIs
                custom_kpi_dict = widget.options.get("custom_kpi") if widget.options else None
                if custom_kpi_dict:
                    c_spec = CustomKpiSpec.model_validate(custom_kpi_dict)
                    c_res = duckdb_engine.compute_custom_kpi(parquet_path, c_spec, semantic_model)
                    if w_type == WidgetType.KPI_CARD:
                        widget_data[w_id] = {
                            "metric_id": w_id,
                            "value": c_res.scalar_value,
                            "formatted_value": c_res.formatted_value,
                            "sparkline": c_res.sparkline,
                            "headline_insight": f"Custom metric: {c_spec.aggregation.upper()} of {c_spec.column}",
                            "confidence_label": "User Custom KPI",
                            "data_quality_score": 100,
                        }
                    elif w_type in (WidgetType.LINE_CHART, WidgetType.AREA_CHART):
                        points = []
                        if c_res.rows:
                            points = [
                                {"period_label": r["dimension_value"], "period_start": r["dimension_value"], "values": {w_id: r["metric_value"]}}
                                for r in c_res.rows
                            ]
                        widget_data[w_id] = {
                            "points": points,
                            "growth_summary": {},
                            "granularity": "custom",
                        }
                    else:
                        widget_data[w_id] = {
                            "dimension": c_spec.dimension or "category",
                            "metrics": [w_id],
                            "rows": [
                                {"dimension_value": r["dimension_value"], w_id: r["metric_value"], "formatted_values": {w_id: r["formatted_value"]}}
                                for r in (c_res.rows or [])
                            ],
                            "total_distinct_groups": len(c_res.rows or []),
                        }
                    continue

                if w_type == WidgetType.KPI_CARD:
                    m_id = widget.metric_id or (widget.metrics[0] if widget.metrics else "total_revenue")
                    val = kpi_summary.get(m_id)
                    m_def = computable_map.get(m_id)
                    formatted = metric_capability_analyzer.format_metric_value(val, m_def) if m_def else str(val)
                    kpi_data = {
                        "metric_id": m_id,
                        "value": val,
                        "formatted_value": formatted,
                    }
                    if semantic_model.date_column:
                        try:
                            trend = timeseries_engine.compute_timeseries(
                                dataset_id=spec.dataset_id,
                                parquet_path=parquet_path,
                                semantic_model=semantic_model,
                                metrics=[m_id],
                                quality_context=quality_context,
                            )
                            growth = trend.growth_summary.get(m_id)
                            kpi_data["sparkline"] = [p.values.get(m_id) for p in trend.points[-8:]]
                            if growth:
                                kpi_data.update({
                                    "prior_value": growth.prior_value,
                                    "prior_formatted_value": metric_capability_analyzer.format_metric_value(growth.prior_value, m_def) if (m_def and growth.prior_value is not None) else None,
                                    "growth_percentage": growth.growth_percentage,
                                    "trend": growth.trend,
                                    "current_period": growth.current_period,
                                    "prior_period": growth.prior_period,
                                    "data_quality_score": growth.data_quality_score,
                                    "confidence_label": growth.confidence_label,
                                    "confidence_factors": [f.model_dump() for f in (growth.confidence_factors or [])],
                                    "headline_insight": growth.headline_insight,
                                })
                        except Exception as trend_exc:
                            logger.debug("KPI trend unavailable for %s: %s", m_id, trend_exc)
                    widget_data[w_id] = kpi_data

                elif w_type in (WidgetType.LINE_CHART, WidgetType.AREA_CHART):
                    gran_enum = (
                        TimeSeriesGranularity(widget.granularity)
                        if widget.granularity in [g.value for g in TimeSeriesGranularity]
                        else None
                    )
                    ts_res = timeseries_engine.compute_timeseries(
                        dataset_id=spec.dataset_id,
                        parquet_path=parquet_path,
                        semantic_model=semantic_model,
                        metrics=widget.metrics,
                        granularity=gran_enum,
                    )
                    widget_data[w_id] = {
                        "points": [p.model_dump() for p in ts_res.points],
                        "growth_summary": {k: v.model_dump() for k, v in ts_res.growth_summary.items()},
                        "granularity": ts_res.granularity.value,
                    }

                elif w_type in (WidgetType.BAR_CHART, WidgetType.PIE_CHART, WidgetType.TABLE):
                    dim = widget.dimension or (semantic_model.dimensions[0] if semantic_model.dimensions else "col")
                    limit = widget.options.get("top_n", 20) if w_type != WidgetType.TABLE else widget.options.get("page_size", 20)
                    bd_res = duckdb_engine.compute_breakdown(
                        parquet_path=parquet_path,
                        dimension=dim,
                        metric_ids=widget.metrics,
                        semantic_model=semantic_model,
                        limit=limit,
                    )
                    widget_data[w_id] = {
                        "dimension": bd_res.dimension,
                        "metrics": bd_res.metrics,
                        "rows": bd_res.rows,
                        "total_distinct_groups": bd_res.total_distinct_groups,
                    }
            except Exception as exc:
                logger.warning("Hydration error for widget '%s' (%s): %s", w_id, w_type, exc)
                widget_data[w_id] = {"error": str(exc)}

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return DashboardDataResponse(
            spec=spec,
            data=widget_data,
            execution_time_ms=elapsed_ms,
        )

    async def generate_dashboard(
        self,
        dataset_id: str,
        title: Optional[str] = None,
        theme: str = "dark",
    ) -> DashboardDataResponse:
        """
        Plans, persists, and hydrates a new AI-generated dashboard specification.
        """
        _, parquet_path, semantic_model, available_metrics, ai_understanding, quality_context = await self._get_dataset_context(dataset_id)

        # 1. Plan dashboard layout
        spec = ai_dashboard_planner.plan_dashboard(
            dataset_id=dataset_id,
            semantic_model=semantic_model,
            available_metrics=available_metrics,
            ai_understanding=ai_understanding,
            title=title,
            theme=theme,
        )

        # 2. Persist in database
        await self.dashboard_repo.save_dashboard(dataset_id, spec, is_default=True)
        logger.info("Generated and saved dashboard '%s' for dataset '%s'", spec.id, dataset_id)

        # 3. Hydrate live data
        return self.hydrate_dashboard(spec, parquet_path, semantic_model, quality_context=quality_context)

    async def get_dashboard(self, dashboard_id: str) -> DashboardDataResponse:
        """
        Retrieves a dashboard by ID and hydrates its live analytical data.
        """
        record = await self.dashboard_repo.get_by_id(dashboard_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard '{dashboard_id}' not found.",
            )

        spec = DashboardSpec.model_validate(json.loads(record.spec_json))
        _, parquet_path, semantic_model, _, _, quality_context = await self._get_dataset_context(record.dataset_id)

        return self.hydrate_dashboard(spec, parquet_path, semantic_model, quality_context=quality_context)

    async def get_default_dashboard(self, dataset_id: str) -> DashboardDataResponse:
        """
        Retrieves the primary default dashboard for a dataset or generates one on-demand.
        """
        record = await self.dashboard_repo.get_default_by_dataset_id(dataset_id)
        if record:
            spec = DashboardSpec.model_validate(json.loads(record.spec_json))
            _, parquet_path, semantic_model, _, _, quality_context = await self._get_dataset_context(dataset_id)
            return self.hydrate_dashboard(spec, parquet_path, semantic_model, quality_context=quality_context)

        # Generate on demand
        return await self.generate_dashboard(dataset_id)

    async def update_dashboard(
        self,
        dashboard_id: str,
        update_data: DashboardUpdate,
    ) -> DashboardDataResponse:
        """
        Updates dashboard properties, layout, or filters and returns re-hydrated dashboard.
        """
        record = await self.dashboard_repo.get_by_id(dashboard_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard '{dashboard_id}' not found.",
            )

        spec = DashboardSpec.model_validate(json.loads(record.spec_json))

        if update_data.title is not None:
            spec.title = update_data.title
        if update_data.subtitle is not None:
            spec.subtitle = update_data.subtitle
        if update_data.theme is not None:
            spec.theme = update_data.theme
        if update_data.widgets is not None:
            spec.widgets = update_data.widgets
        if update_data.filters is not None:
            spec.filters = update_data.filters

        await self.dashboard_repo.save_dashboard(record.dataset_id, spec)
        _, parquet_path, semantic_model, _, _, quality_context = await self._get_dataset_context(record.dataset_id)

        return self.hydrate_dashboard(spec, parquet_path, semantic_model, quality_context=quality_context)

    async def delete_dashboard(self, dashboard_id: str) -> bool:
        """Deletes a dashboard."""
        deleted = await self.dashboard_repo.delete(dashboard_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard '{dashboard_id}' not found.",
            )
        return True

    async def add_custom_widget(
        self,
        dashboard_id: str,
        custom_spec: CustomKpiSpec,
    ) -> DashboardDataResponse:
        """
        Adds a new custom KPI widget to the dashboard specification and persists it.
        """
        record = await self.dashboard_repo.get_by_id(dashboard_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard '{dashboard_id}' not found.",
            )

        spec = DashboardSpec.model_validate(json.loads(record.spec_json))
        _, parquet_path, semantic_model, _, _, quality_context = await self._get_dataset_context(record.dataset_id)

        # 1. Preview/evaluate custom KPI to resolve widget type
        preview = duckdb_engine.compute_custom_kpi(parquet_path, custom_spec, semantic_model)
        resolved_type = preview.resolved_widget_type

        # 2. Build new WidgetConfig
        import uuid
        new_w_id = f"w_custom_{uuid.uuid4().hex[:8]}"

        if resolved_type == WidgetType.KPI_CARD:
            col_w, col_h = 3, 4
        elif resolved_type == WidgetType.TABLE:
            col_w, col_h = 12, 6
        else:
            col_w, col_h = 6, 5

        widget_cfg = WidgetConfig(
            id=new_w_id,
            type=resolved_type,
            title=custom_spec.label,
            description=f"{custom_spec.aggregation.upper()} of {custom_spec.column}" + (f" by {custom_spec.dimension}" if custom_spec.dimension else ""),
            metric_id=new_w_id if resolved_type == WidgetType.KPI_CARD else None,
            dimension=custom_spec.dimension,
            metrics=[new_w_id],
            position=GridPosition(x=0, y=99, w=col_w, h=col_h),
            options={"custom_kpi": custom_spec.model_dump()},
        )

        spec.widgets.append(widget_cfg)
        await self.dashboard_repo.save_dashboard(record.dataset_id, spec)
        return self.hydrate_dashboard(spec, parquet_path, semantic_model, quality_context=quality_context)

    async def remove_widget(
        self,
        dashboard_id: str,
        widget_id: str,
    ) -> DashboardDataResponse:
        """
        Removes a widget from the dashboard and persists the updated specification.
        """
        record = await self.dashboard_repo.get_by_id(dashboard_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard '{dashboard_id}' not found.",
            )

        spec = DashboardSpec.model_validate(json.loads(record.spec_json))
        orig_count = len(spec.widgets)
        spec.widgets = [w for w in spec.widgets if w.id != widget_id]
        if len(spec.widgets) == orig_count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Widget '{widget_id}' not found in dashboard.",
            )

        await self.dashboard_repo.save_dashboard(record.dataset_id, spec)
        _, parquet_path, semantic_model, _, _, quality_context = await self._get_dataset_context(record.dataset_id)
        return self.hydrate_dashboard(spec, parquet_path, semantic_model, quality_context=quality_context)
