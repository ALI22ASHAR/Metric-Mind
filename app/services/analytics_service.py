import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.duckdb_engine import duckdb_engine
from app.ai.query_guardrails import query_guardrail
from app.analytics.metric_registry import metric_capability_analyzer
from app.analytics.timeseries import timeseries_engine
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.analytics import (
    BreakdownRequest,
    BreakdownResponse,
    RawQueryRequest,
    RawQueryResponse,
)
from app.schemas.metrics import (
    DatasetMetricsSummary,
    MetricDefinition,
    MetricResult,
)
from app.schemas.timeseries import TimeSeriesRequest, TimeSeriesResponse
from app.services.semantic_service import SemanticService

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Business service orchestrating KPI calculations, DuckDB analytical breakdowns, and time-series growth.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.semantic_service = SemanticService(db)

    async def _get_dataset_and_parquet(self, dataset_id: str):
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
                detail=f"Dataset '{dataset_id}' does not have a processed data file.",
            )

        semantic_model = await self.semantic_service.get_semantic_model(dataset_id)
        return dataset, parquet_path, semantic_model

    async def get_available_metrics(self, dataset_id: str) -> List[MetricDefinition]:
        """
        Lists all KPIs that can be computed from the dataset's semantic mappings.
        """
        _, _, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        return metric_capability_analyzer.get_computable_metrics(semantic_model)

    async def get_metrics_summary(
        self,
        dataset_id: str,
        filters: Optional[List[DimensionFilter]] = None,
    ) -> DatasetMetricsSummary:
        """
        Calculates all computable KPIs for the dataset with optional dimensional filtering.
        """
        _, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        computable = metric_capability_analyzer.get_computable_metrics(semantic_model)
        raw_values = duckdb_engine.compute_kpi_summary(parquet_path, semantic_model, filters=filters)

        results: Dict[str, MetricResult] = {}
        for m in computable:
            val = raw_values.get(m.id)
            formatted = metric_capability_analyzer.format_metric_value(val, m)
            results[m.id] = MetricResult(
                metric_id=m.id,
                name=m.name,
                label=m.label,
                value=val,
                formatted_value=formatted,
                metric_type=m.metric_type,
                unit=m.unit,
            )

        return DatasetMetricsSummary(
            dataset_id=dataset_id,
            total_computable_metrics=len(computable),
            computable_metrics=computable,
            metrics=results,
        )


    async def compute_breakdown(
        self,
        dataset_id: str,
        request: BreakdownRequest,
    ) -> BreakdownResponse:
        """
        Aggregates metrics grouped by a dimension column.
        """
        _, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        return duckdb_engine.compute_breakdown(
            parquet_path=parquet_path,
            dimension=request.dimension,
            metric_ids=request.metrics,
            semantic_model=semantic_model,
            filters=request.filters,
            limit=request.limit,
            sort_by=request.sort_by,
            ascending=request.ascending,
        )

    async def compute_timeseries(
        self,
        dataset_id: str,
        request: TimeSeriesRequest,
        quality_context: Optional[Dict] = None,
    ) -> TimeSeriesResponse:
        """
        Computes time-series trend points and period-over-period growth rates.
        """
        _, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        return timeseries_engine.compute_timeseries(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            semantic_model=semantic_model,
            metrics=request.metrics,
            granularity=request.granularity,
            filters=request.filters,
            quality_context=quality_context,
        )

    async def execute_raw_query(
        self,
        dataset_id: str,
        request: RawQueryRequest,
    ) -> RawQueryResponse:
        """
        Executes a read-only analytical SQL query against the dataset Parquet file.
        """
        _, parquet_path, _ = await self._get_dataset_and_parquet(dataset_id)
        import polars as pl
        valid_columns = list(pl.read_parquet_schema(parquet_path).keys())
        is_valid, executable_sql, error = query_guardrail.validate_and_rewrite_sql(
            raw_sql=request.query,
            parquet_path=parquet_path,
            valid_columns=valid_columns,
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
        return duckdb_engine.execute_safe_query(parquet_path, executable_sql)

    async def compute_kpi_multi_breakdown(
        self,
        dataset_id: str,
        metric_id: str,
    ) -> Dict[str, Any]:
        """
        Computes dynamic multi-dimensional breakdowns for a specific KPI across all discovered dimensions.
        """
        import polars as pl
        _, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        
        # Discover all categorical columns directly from Parquet schema
        discovered_categorical: List[str] = []
        try:
            schema = pl.read_parquet_schema(parquet_path)
            for col_name, dtype in schema.items():
                if dtype in (pl.Utf8, pl.String, pl.Categorical):
                    discovered_categorical.append(col_name)
        except Exception as err:
            logger.warning("Failed to read parquet schema: %s", err)

        employee_name = semantic_model.employee_name_column or next(
            (column for column in discovered_categorical
             if column.lower() in {"employee_name", "employee_name_full", "full_name", "name"}),
            None,
        )
        candidate_dims = [
            employee_name,
            semantic_model.category_column,
            semantic_model.product_column,
        ] + (semantic_model.dimensions or []) + discovered_categorical
        # Deduplicate while preserving order
        dims = list(dict.fromkeys(d for d in candidate_dims if d))[:6]

        breakdowns = {}
        for dim in dims:
            try:
                bd = duckdb_engine.compute_breakdown(
                    parquet_path=parquet_path,
                    dimension=dim,
                    metric_ids=[metric_id],
                    semantic_model=semantic_model,
                    limit=8,
                    sort_by=metric_id,
                    ascending=False,
                )
                rows = bd.rows
                total_val = sum(r.get(metric_id, 0) or 0 for r in rows)
                formatted_rows = []
                for r in rows:
                    val = r.get(metric_id, 0) or 0
                    share = round((val / total_val * 100.0), 1) if total_val > 0 else 0.0
                    metric_def = next(
                        (m for m in metric_capability_analyzer.get_computable_metrics(semantic_model) if m.id == metric_id),
                        None,
                    )
                    formatted_rows.append({
                        "dimension_value": str(r.get("dimension_value", "Unknown")),
                        "value": round(val, 2),
                        "formatted_value": metric_capability_analyzer.format_metric_value(val, metric_def) if metric_def else str(round(val, 2)),
                        "metric_type": metric_def.metric_type.value if metric_def else "count",
                        "share_percentage": share,
                    })
                if formatted_rows:
                    breakdowns[dim] = formatted_rows
            except Exception as exc:
                logger.warning("KPI breakdown failed for dimension %s: %s", dim, exc)

        return {
            "dataset_id": dataset_id,
            "metric_id": metric_id,
            "breakdowns": breakdowns,
        }

    async def compute_geo_breakdown(
        self,
        dataset_id: str,
        metric_id: str = "total_revenue",
        filters: Optional[List[DimensionFilter]] = None,
    ):
        """
        Computes geographic metric aggregates across countries/regions.
        """
        from app.analytics.geo_engine import geo_engine
        import polars as pl
        dataset, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        
        try:
            schema = pl.read_parquet_schema(parquet_path)
            columns = list(schema.keys())
        except Exception:
            columns = [semantic_model.category_column] + (semantic_model.dimensions or [])

        return geo_engine.compute_geo_breakdown(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            semantic_model=semantic_model,
            columns=columns,
            metric_id=metric_id,
            filters=filters,
        )

    async def register_custom_metric(
        self,
        dataset_id: str,
        request: Any,
    ) -> MetricDefinition:
        """
        Validates and registers a user-defined custom formula KPI.
        """
        from app.analytics.formula_engine import formula_engine
        import polars as pl
        _, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        
        schema = pl.read_parquet_schema(parquet_path)
        available_cols = list(schema.keys())

        val_res = formula_engine.validate_and_compile(request.formula, available_cols)
        if not val_res.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=val_res.error_message or "Invalid formula expression.",
            )

        fmt = "{:,.2f}" if request.format_type == "number" else "{:,.0f}" if request.format_type == "integer" else "{:.2f}%" if request.format_type == "percentage" else "${:,.2f}"

        metric_def = MetricDefinition(
            id=request.name.lower().replace(" ", "_"),
            name=request.name.lower().replace(" ", "_"),
            label=request.label,
            description=request.description or f"Custom Metric: {request.formula}",
            sql_template=val_res.sql_template,
            format_spec=fmt,
            category="custom",
        )

        metric_capability_analyzer.register_custom_metric(dataset_id, metric_def)
        return metric_def

    async def get_custom_metrics(self, dataset_id: str) -> List[MetricDefinition]:
        """
        Retrieves all registered custom metrics for a dataset.
        """
        return metric_capability_analyzer.get_custom_metrics_for_dataset(dataset_id)

    async def get_dimension_values(self, dataset_id: str, dimension: str) -> List[str]:
        """
        Retrieves distinct categorical values for a dimension (e.g. Category, Product).
        """
        _, parquet_path, semantic_model = await self._get_dataset_and_parquet(dataset_id)
        bd = duckdb_engine.compute_breakdown(
            parquet_path=parquet_path,
            dimension=dimension,
            metric_ids=["total_records"],
            semantic_model=semantic_model,
            limit=100,
        )
        return [str(r.get("dimension_value")) for r in bd.rows if r.get("dimension_value") is not None]



