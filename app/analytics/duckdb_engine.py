import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb
import polars as pl
from fastapi import HTTPException, status

from app.analytics.metric_registry import metric_capability_analyzer
from app.schemas.analytics import (
    BreakdownResponse,
    DimensionFilter,
    FilterOperator,
    RawQueryResponse,
)
from app.schemas.dashboard import WidgetType
from app.schemas.kpi_builder import (
    CustomKpiSpec,
    KpiAggregationType,
    KpiFormatType,
    KpiPreviewResponse,
)
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)

UNSAFE_SQL_PATTERN = re.compile(
    r"\b(drop|delete|update|insert|alter|attach|copy|export|import|install|load|create|vacuum|call|pragma)\b",
    re.IGNORECASE,
)


class DuckDBEngine:
    """
    In-memory OLAP Analytical SQL Engine querying Apache Parquet representations directly.
    """

    @classmethod
    def get_connection(cls) -> duckdb.DuckDBPyConnection:
        """Create a transient in-memory DuckDB session."""
        return duckdb.connect(database=":memory:")

    @classmethod
    def build_where_clause(
        cls,
        filters: Optional[List[DimensionFilter]],
    ) -> Tuple[str, List[Any]]:
        """
        Constructs a parameterized SQL WHERE clause from filter specifications.
        """
        if not filters:
            return "", []

        clauses = []
        params = []

        for f in filters:
            col = re.sub(r"[^a-zA-Z0-9_]", "", f.column)
            op = f.operator
            val = f.value

            if op == FilterOperator.EQ:
                clauses.append(f"{col} = ?")
                params.append(val)
            elif op == FilterOperator.NEQ:
                clauses.append(f"{col} != ?")
                params.append(val)
            elif op == FilterOperator.IN:
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    placeholders = ", ".join(["?"] * len(val))
                    clauses.append(f"{col} IN ({placeholders})")
                    params.extend(val)
            elif op == FilterOperator.NOT_IN:
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    placeholders = ", ".join(["?"] * len(val))
                    clauses.append(f"{col} NOT IN ({placeholders})")
                    params.extend(val)
            elif op == FilterOperator.GT:
                clauses.append(f"{col} > ?")
                params.append(val)
            elif op == FilterOperator.GTE:
                clauses.append(f"{col} >= ?")
                params.append(val)
            elif op == FilterOperator.LT:
                clauses.append(f"{col} < ?")
                params.append(val)
            elif op == FilterOperator.LTE:
                clauses.append(f"{col} <= ?")
                params.append(val)
            elif op == FilterOperator.LIKE:
                clauses.append(f"{col} ILIKE ?")
                params.append(f"%{val}%")
            elif op == FilterOperator.BETWEEN:
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    clauses.append(f"{col} BETWEEN ? AND ?")
                    params.extend(val)

        if not clauses:
            return "", []

        return "WHERE " + " AND ".join(clauses), params

    @classmethod
    def compute_kpi_summary(
        cls,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        filters: Optional[List[DimensionFilter]] = None,
    ) -> Dict[str, Optional[float]]:
        """
        Computes all available standard business KPIs in a single parallelized SQL aggregation with optional filtering.
        """
        normalized_path = Path(parquet_path).as_posix()
        computable = metric_capability_analyzer.get_computable_metrics(semantic_model)
        if not computable:
            return {}

        where_clause, params = cls.build_where_clause(filters)
        select_parts = [f"{m.sql_template} AS {m.id}" for m in computable]
        sql = f"SELECT {', '.join(select_parts)} FROM '{normalized_path}' {where_clause}"

        con = cls.get_connection()
        try:
            res = con.execute(sql, params).pl()
            results: Dict[str, Optional[float]] = {}
            if res.height > 0:
                row = res.to_dicts()[0]
                for m in computable:
                    val = row.get(m.id)
                    results[m.id] = float(val) if val is not None else None
            return results
        finally:
            con.close()


    @classmethod
    def compute_breakdown(
        cls,
        parquet_path: str,
        dimension: str,
        metric_ids: List[str],
        semantic_model: SemanticModelSchema,
        filters: Optional[List[DimensionFilter]] = None,
        limit: int = 20,
        sort_by: Optional[str] = None,
        ascending: bool = False,
    ) -> BreakdownResponse:
        """
        Aggregates metrics grouped by a dimension column (e.g. Category, City, Region).
        """
        start_time = time.perf_counter()
        normalized_path = Path(parquet_path).as_posix()

        # Sanitize dimension column name
        dim_clean = dimension.replace('"', '').strip()

        # Get metric definitions
        all_computable = {m.id: m for m in metric_capability_analyzer.get_computable_metrics(semantic_model)}
        active_metrics: List[MetricDefinition] = []

        for m_id in metric_ids:
            if m_id in all_computable:
                active_metrics.append(all_computable[m_id])

        if not active_metrics:
            # Fallback to count / orders
            active_metrics.append(
                MetricDefinition(
                    id="count",
                    name="count",
                    label="Record Count",
                    description="Total records",
                    sql_template="COUNT(*)",
                    format_spec="{:,.0f}",
                )
            )

        where_clause, params = cls.build_where_clause(filters)

        select_parts = [f'"{dim_clean}" AS dimension_value', 'COUNT(*) AS _row_count']
        for m in active_metrics:
            select_parts.append(f"{m.sql_template} AS {m.id}")

        sort_col = sort_by if sort_by in [m.id for m in active_metrics] else active_metrics[0].id
        sort_direction = "ASC" if ascending else "DESC"

        sql = f"""
            SELECT {', '.join(select_parts)}
            FROM '{normalized_path}'
            {where_clause}
            GROUP BY "{dim_clean}"
            ORDER BY {sort_col} {sort_direction} NULLS LAST
            LIMIT {limit}
        """

        count_sql = f"""
            SELECT COUNT(DISTINCT {dim_clean}) AS total_groups
            FROM '{normalized_path}'
            {where_clause}
        """

        con = cls.get_connection()
        try:
            df = con.execute(sql, params).pl()
            total_groups_df = con.execute(count_sql, params).pl()
            total_groups = int(total_groups_df[0, 0]) if total_groups_df.height > 0 else 0

            rows = df.to_dicts()
            for row in rows:
                row["formatted_values"] = {
                    metric.id: metric_capability_analyzer.format_metric_value(row.get(metric.id), metric)
                    for metric in active_metrics
                }
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return BreakdownResponse(
                dimension=dimension,
                metrics=[m.id for m in active_metrics],
                rows=rows,
                total_distinct_groups=total_groups,
                execution_time_ms=elapsed_ms,
            )
        finally:
            con.close()

    @classmethod
    def execute_safe_query(
        cls,
        parquet_path: str,
        sql: str,
        params: Optional[List[Any]] = None,
    ) -> RawQueryResponse:
        """
        Executes an arbitrary read-only analytical SQL query against the dataset Parquet file.
        """
        start_time = time.perf_counter()
        normalized_path = Path(parquet_path).as_posix()

        # Security check: disallow DDL/DML/destructive operations
        if UNSAFE_SQL_PATTERN.search(sql):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query contains prohibited SQL statements. Only read-only SELECT queries are permitted.",
            )

        # Substitute generic table references (data, dataset, table) with Parquet path
        safe_sql = re.sub(
            r"\b(FROM|JOIN)\s+(data|dataset|sales|clean_data)\b",
            rf"\1 '{normalized_path}'",
            sql,
            flags=re.IGNORECASE,
        )

        # If no table reference was present, inject FROM 'path'
        if f"'{normalized_path}'" not in safe_sql:
            safe_sql = re.sub(
                r"\bFROM\s+([a-zA-Z0-9_]+)\b",
                rf"FROM '{normalized_path}'",
                safe_sql,
                flags=re.IGNORECASE,
            )

        con = cls.get_connection()
        try:
            # Bind columns and functions before execution so invalid AI-generated
            # SQL fails explicitly instead of producing a misleading fallback answer.
            con.execute(f"EXPLAIN {safe_sql}", params or [])
            df = con.execute(safe_sql, params or []).pl()
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return RawQueryResponse(
                columns=df.columns,
                rows=df.to_dicts(),
                row_count=df.height,
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            logger.error("DuckDB execution error: %s (SQL: %s)", exc, safe_sql)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SQL Execution Error: {str(exc)}",
            )
    @classmethod
    def format_kpi_value(
        cls,
        value: Optional[float],
        format_type: Optional[KpiFormatType] = None,
        unit: Optional[str] = None,
    ) -> str:
        if value is None:
            return "--"
        fmt = format_type or KpiFormatType.NUMBER
        if fmt == KpiFormatType.CURRENCY:
            return f"${value:,.2f}"
        elif fmt == KpiFormatType.PERCENTAGE:
            return f"{value:,.1f}%"
        elif fmt == KpiFormatType.DURATION:
            return f"{value:,.1f} {unit or 'min'}"
        else:
            if isinstance(value, float) and value.is_integer():
                formatted = f"{int(value):,}"
            else:
                formatted = f"{value:,.2f}" if abs(value) < 1000 else f"{value:,.1f}"
            return f"{formatted} {unit}".strip() if unit else formatted

    @classmethod
    def compute_custom_kpi(
        cls,
        parquet_path: str,
        spec: CustomKpiSpec,
        semantic_model: Optional[SemanticModelSchema] = None,
    ) -> KpiPreviewResponse:
        """
        Executes dynamic analytical calculation for a custom user-defined KPI specification.
        Supports SUM, AVG, COUNT, MIN, MAX, RATE, and PERCENT_OF_TOTAL with optional grouping.
        """
        start_time = time.perf_counter()
        normalized_path = Path(parquet_path).as_posix()
        con = cls.get_connection()

        try:
            schema_df = con.execute(f"DESCRIBE SELECT * FROM '{normalized_path}' LIMIT 1").pl()
            valid_cols = {row["column_name"]: str(row["column_type"]) for row in schema_df.to_dicts()}

            # Build case-insensitive and format-insensitive lookup
            col_lookup: Dict[str, str] = {}
            for c_real in valid_cols.keys():
                col_lookup[c_real.lower()] = c_real
                col_lookup[c_real.lower().replace("_", "")] = c_real
                col_lookup[c_real.lower().replace(" ", "")] = c_real

            col_name = spec.column
            if col_name != "*":
                norm_col = (
                    col_lookup.get(col_name.lower())
                    or col_lookup.get(col_name.lower().replace("_", ""))
                    or col_lookup.get(col_name.lower().replace(" ", ""))
                )
                if not norm_col:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Column '{col_name}' does not exist in dataset.",
                    )
                col_name = norm_col

            dim_name = spec.dimension
            if dim_name:
                norm_dim = (
                    col_lookup.get(dim_name.lower())
                    or col_lookup.get(dim_name.lower().replace("_", ""))
                    or col_lookup.get(dim_name.lower().replace(" ", ""))
                )
                if not norm_dim:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Grouping dimension '{dim_name}' does not exist in dataset.",
                    )
                dim_name = norm_dim

            col_sql = f'"{col_name}"' if col_name != "*" else "*"
            agg = spec.aggregation

            if agg == KpiAggregationType.RATE:
                cond = spec.condition
                if cond and cond.value is not None:
                    target_val = cond.value
                    if isinstance(target_val, bool):
                        cond_expr = f"{col_sql} = {'TRUE' if target_val else 'FALSE'}"
                    elif isinstance(target_val, (int, float)):
                        cond_expr = f"{col_sql} = {target_val}"
                    else:
                        val_str = str(target_val).replace("'", "''")
                        cond_expr = f"LOWER(CAST({col_sql} AS VARCHAR)) = LOWER('{val_str}')"
                else:
                    cond_expr = f"{col_sql} IS TRUE OR CAST({col_sql} AS VARCHAR) IN ('1', 'true', 'True', 'YES', 'yes')"
                measure_sql = f"ROUND(COUNT(CASE WHEN {cond_expr} THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2)"
                if not spec.format_type or spec.format_type == KpiFormatType.NUMBER:
                    spec.format_type = KpiFormatType.PERCENTAGE

            elif agg == KpiAggregationType.PERCENT_OF_TOTAL:
                measure_sql = f"ROUND(SUM(CAST({col_sql} AS DOUBLE)) * 100.0 / NULLIF(SUM(SUM(CAST({col_sql} AS DOUBLE))) OVER (), 0), 2)"
                if not spec.format_type or spec.format_type == KpiFormatType.NUMBER:
                    spec.format_type = KpiFormatType.PERCENTAGE

            elif agg == KpiAggregationType.COUNT:
                measure_sql = "COUNT(*)" if col_name == "*" else f"COUNT({col_sql})"

            elif agg == KpiAggregationType.AVG:
                measure_sql = f"ROUND(AVG(CAST({col_sql} AS DOUBLE)), 2)"

            elif agg == KpiAggregationType.SUM:
                measure_sql = f"ROUND(SUM(CAST({col_sql} AS DOUBLE)), 2)"

            elif agg == KpiAggregationType.MIN:
                measure_sql = f"MIN({col_sql})"

            elif agg == KpiAggregationType.MAX:
                measure_sql = f"MAX({col_sql})"

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported aggregation '{agg}'.",
                )

            dim_type = valid_cols.get(dim_name, "").upper() if dim_name else ""
            is_temporal_dim = False
            distinct_count = 0

            if dim_name:
                is_temporal_dim = any(t in dim_type for t in ("DATE", "TIME", "TIMESTAMP")) or any(
                    k in dim_name.lower() for k in ("date", "year", "month", "day", "week", "time")
                )
                cnt_df = con.execute(f'SELECT COUNT(DISTINCT "{dim_name}") AS cnt FROM \'{normalized_path}\'').pl()
                distinct_count = int(cnt_df[0, 0]) if cnt_df.height > 0 else 0

            resolved_widget_type = WidgetType.KPI_CARD
            suggested_reason = "Single summary indicator card"

            if not dim_name:
                resolved_widget_type = WidgetType.KPI_CARD
                suggested_reason = "Single KPI metric card (no grouping dimension selected)"
            elif is_temporal_dim:
                resolved_widget_type = WidgetType.LINE_CHART
                suggested_reason = f"Line chart (dimension '{dim_name}' represents chronological progression)"
            elif 1 < distinct_count <= 5:
                resolved_widget_type = WidgetType.PIE_CHART
                suggested_reason = f"Donut/Pie chart (dimension '{dim_name}' has low cardinality: {distinct_count} segments)"
            else:
                resolved_widget_type = WidgetType.BAR_CHART
                suggested_reason = f"Comparative Bar chart (dimension '{dim_name}' has {distinct_count} distinct categories)"

            if spec.output_type and spec.output_type != "auto":
                try:
                    resolved_widget_type = WidgetType(spec.output_type)
                    suggested_reason = f"User selected {resolved_widget_type.value.replace('_', ' ')}"
                except ValueError:
                    pass

            scalar_val: Optional[float] = None
            formatted_val: Optional[str] = None
            sparkline_points: Optional[List[Optional[float]]] = None
            rows_data: Optional[List[Dict[str, Any]]] = None

            if not dim_name or resolved_widget_type == WidgetType.KPI_CARD:
                scalar_sql = f"SELECT {measure_sql} AS metric_value FROM '{normalized_path}'"
                scalar_df = con.execute(scalar_sql).pl()
                if scalar_df.height > 0 and scalar_df[0, 0] is not None:
                    raw_v = scalar_df[0, 0]
                    scalar_val = float(raw_v) if isinstance(raw_v, (int, float)) else None
                formatted_val = cls.format_kpi_value(scalar_val, spec.format_type, spec.unit)

                date_col = semantic_model.date_column if semantic_model and semantic_model.date_column else None
                if not date_col:
                    for c_name, c_type in valid_cols.items():
                        if any(t in c_type.upper() for t in ("DATE", "TIMESTAMP")):
                            date_col = c_name
                            break

                if date_col and date_col in valid_cols:
                    try:
                        spark_sql = f"""
                            SELECT {measure_sql} AS val
                            FROM '{normalized_path}'
                            WHERE "{date_col}" IS NOT NULL
                            GROUP BY date_trunc('month', "{date_col}")
                            ORDER BY date_trunc('month', "{date_col}") ASC
                            LIMIT 8
                        """
                        sp_df = con.execute(spark_sql).pl()
                        sparkline_points = [float(v[0]) if v[0] is not None else None for v in sp_df.rows()]
                    except Exception as sp_exc:
                        logger.debug("Sparkline query failed: %s", sp_exc)

            if dim_name:
                limit_n = spec.limit or 15
                order_clause = (
                    f'ORDER BY "{dim_name}" ASC'
                    if is_temporal_dim and resolved_widget_type == WidgetType.LINE_CHART
                    else 'ORDER BY metric_value DESC NULLS LAST'
                )
                group_sql = f"""
                    SELECT "{dim_name}" AS dimension_value, {measure_sql} AS metric_value
                    FROM '{normalized_path}'
                    WHERE "{dim_name}" IS NOT NULL
                    GROUP BY "{dim_name}"
                    {order_clause}
                    LIMIT {limit_n}
                """
                group_df = con.execute(group_sql).pl()
                rows_data = []
                for r in group_df.to_dicts():
                    val = r.get("metric_value")
                    numeric_val = float(val) if isinstance(val, (int, float)) else 0.0
                    rows_data.append({
                        "dimension_value": str(r.get("dimension_value", "Unknown")),
                        "metric_value": numeric_val,
                        "formatted_value": cls.format_kpi_value(numeric_val, spec.format_type, spec.unit),
                    })

                if scalar_val is None and rows_data:
                    scalar_sql = f"SELECT {measure_sql} AS metric_value FROM '{normalized_path}'"
                    s_df = con.execute(scalar_sql).pl()
                    if s_df.height > 0 and s_df[0, 0] is not None:
                        scalar_val = float(s_df[0, 0])
                        formatted_val = cls.format_kpi_value(scalar_val, spec.format_type, spec.unit)

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return KpiPreviewResponse(
                spec=spec,
                resolved_widget_type=resolved_widget_type,
                suggested_visual_reason=suggested_reason,
                scalar_value=scalar_val,
                formatted_value=formatted_val,
                sparkline=sparkline_points,
                rows=rows_data,
                dimension=dim_name,
                execution_time_ms=elapsed_ms,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Error computing custom KPI: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to calculate KPI: {str(exc)}",
            )
        finally:
            con.close()


duckdb_engine = DuckDBEngine()

