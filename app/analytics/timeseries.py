import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import duckdb
import polars as pl
from fastapi import HTTPException, status

from app.analytics.duckdb_engine import duckdb_engine
from app.analytics.metric_registry import metric_capability_analyzer
from app.schemas.analytics import DimensionFilter
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import BusinessConcept, SemanticModelSchema
from app.schemas.timeseries import (
    ConfidenceFactor,
    PeriodOverPeriodGrowth,
    TimeSeriesGranularity,
    TimeSeriesPoint,
    TimeSeriesResponse,
)

logger = logging.getLogger(__name__)


def _compute_data_quality_score(
    metric: MetricDefinition,
    quality_context: Optional[Dict[str, Any]],
) -> tuple[Optional[float], Optional[str], List[ConfidenceFactor]]:
    """
    Derive a 0-100 confidence score for a metric from dataset-level quality signals.

    Factors weighted:
      - Row count (sample size)        30%
      - Average null percentage        35%
      - Quality warning severity       20%
      - Period depth (>=2 periods)     15%

    Returns (score, label, factors). Returns (None, None, []) if no context supplied.
    """
    if not quality_context:
        return None, None, []

    factors: List[ConfidenceFactor] = []
    row_count = int(quality_context.get("row_count") or 0)
    null_pct = float(quality_context.get("avg_null_percentage") or 0.0)
    warning_count = int(quality_context.get("quality_warnings_count") or 0)
    critical_count = int(quality_context.get("critical_warnings_count") or 0)
    has_periods = bool(quality_context.get("has_periods", True))

    # 1. Row count score (0-100)
    if row_count >= 10_000:
        row_score = 100.0
    elif row_count >= 1_000:
        row_score = 85.0
    elif row_count >= 200:
        row_score = 70.0
    elif row_count >= 50:
        row_score = 50.0
    elif row_count > 0:
        row_score = 30.0
    else:
        row_score = 0.0
    factors.append(ConfidenceFactor(
        label="Sample size",
        score=row_score,
        detail=f"{row_count:,} rows" if row_count else "No data",
    ))

    # 2. Null percentage score (lower is better)
    if null_pct <= 1.0:
        null_score = 100.0
    elif null_pct <= 5.0:
        null_score = 90.0
    elif null_pct <= 15.0:
        null_score = 70.0
    elif null_pct <= 30.0:
        null_score = 50.0
    else:
        null_score = 25.0
    factors.append(ConfidenceFactor(
        label="Data completeness",
        score=null_score,
        detail=f"Avg {null_pct:.1f}% nulls" if null_pct else "Complete",
    ))

    # 3. Quality warnings score (deductions)
    warn_score = max(0.0, 100.0 - 12.0 * warning_count - 25.0 * critical_count)
    factors.append(ConfidenceFactor(
        label="Data quality",
        score=warn_score,
        detail=(
            f"{warning_count} warning(s)" if warning_count
            else "No warnings"
        ),
    ))

    # 4. Period depth — without >=2 periods we can't show a real trend
    period_score = 100.0 if has_periods else 25.0
    factors.append(ConfidenceFactor(
        label="Trend depth",
        score=period_score,
        detail="Multi-period history" if has_periods else "Single period only",
    ))

    # Weighted average using the weights above
    weighted = (
        row_score * 0.30
        + null_score * 0.35
        + warn_score * 0.20
        + period_score * 0.15
    )
    score = round(min(100.0, max(0.0, weighted)), 1)

    if score >= 80:
        label = "High confidence"
    elif score >= 60:
        label = "Moderate confidence"
    elif score >= 40:
        label = "Limited confidence"
    else:
        label = "Low confidence"

    return score, label, factors


def _generate_headline_insight(
    metric: MetricDefinition,
    growth: PeriodOverPeriodGrowth,
    parquet_path: str,
    semantic_model: SemanticModelSchema,
    date_col: str,
) -> Optional[str]:
    """
    Generate a deterministic one-sentence narrative describing what drove the
    period-over-period change. We compute the top dimensional delta in DuckDB
    (no LLM call) so the headline is always fast and reliable.

    Returns a sentence like: "Driven by a +14.2% lift in Engineering; Sales flat."
    """
    if growth.growth_percentage is None or abs(growth.growth_percentage) < 0.5:
        # No meaningful change — surface a stability insight instead.
        return f"{metric.label} remained essentially flat versus the prior period."

    # Pick the most likely explanatory dimension from the semantic model.
    dim = (
        semantic_model.category_column
        or semantic_model.product_column
        or semantic_model.department_column
        or (semantic_model.dimensions[0] if semantic_model.dimensions else None)
    )
    if not dim:
        return None

    try:
        normalized_path = Path(parquet_path).as_posix()

        # sql_template is something like SUM(col1 * col2) — extract the inner
        # expression so we can use it in a conditional SUM without double-aggregating.
        raw_expr = metric.sql_template.strip()
        if raw_expr.startswith("SUM(") and raw_expr.endswith(")"):
            # Strip the outer SUM(...) wrapper safely — only for depth-1 wrappers.
            inner_expr = raw_expr[4:-1]
        else:
            inner_expr = raw_expr

        con = duckdb_engine.get_connection()
        try:
            # Compute per-dimension value for the current (most recent) period
            # versus the immediately prior equal-length window.
            # Uses a single query with COUNT(CASE WHEN ...) so no CTE overhead.
            sql = f"""
                WITH bounds AS (
                    SELECT
                        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {date_col}::DATE) AS q3,
                        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {date_col}::DATE) AS q1,
                        MIN({date_col}::DATE) AS min_d,
                        MAX({date_col}::DATE) AS max_d
                    FROM '{normalized_path}'
                    WHERE {date_col} IS NOT NULL
                ),
                windowed AS (
                    SELECT
                        "{dim}" AS segment,
                        COALESCE(SUM(CASE WHEN {date_col}::DATE >= (SELECT q3 FROM bounds) THEN {inner_expr} END), 0) AS curr_val,
                        COALESCE(SUM(CASE WHEN {date_col}::DATE < (SELECT q3 FROM bounds) AND {date_col}::DATE >= (SELECT q1 FROM bounds) THEN {inner_expr} END), 0) AS prior_val
                    FROM '{normalized_path}'
                    WHERE {date_col} IS NOT NULL AND "{dim}" IS NOT NULL
                    GROUP BY 1
                )
                SELECT
                    segment,
                    curr_val,
                    prior_val,
                    CASE
                        WHEN prior_val = 0 OR prior_val IS NULL THEN NULL
                        ELSE ROUND(((curr_val - prior_val) / NULLIF(prior_val, 0)) * 100.0, 1)
                    END AS pct_delta
                FROM windowed
                WHERE curr_val != 0 OR prior_val != 0
                ORDER BY ABS(curr_val - prior_val) DESC
                LIMIT 3
            """
            df = con.execute(sql).pl()
        finally:
            con.close()

        if df.height == 0:
            return None

        rows = df.to_dicts()
        primary = rows[0]
        primary_pct = primary.get("pct_delta")
        if primary_pct is None:
            return None

        direction = "lift" if primary_pct >= 0 else "decline"
        primary_name = str(primary.get("segment") or "the leading segment")

        # Build secondary signal if any.
        secondary_clause = ""
        for r in rows[1:]:
            r_pct = r.get("pct_delta")
            if r_pct is not None and abs(r_pct) >= 1.0:
                sign_word = "up" if r_pct >= 0 else "down"
                secondary_clause = (
                    f"; {r.get('segment')} {sign_word} {abs(r_pct):.1f}%"
                )
                break

        return f"Driven by a {direction} of {abs(primary_pct):.1f}% in {primary_name}{secondary_clause}."

    except Exception as exc:
        logger.debug("headline insight generation failed: %s", exc)
        return None


class TimeSeriesEngine:
    """
    Computes time-series aggregations, rolling averages, and period-over-period growth rates.
    """

    @classmethod
    def auto_detect_granularity(
        cls,
        parquet_path: str,
        date_col: str,
    ) -> TimeSeriesGranularity:
        """
        Determines the optimal time interval based on the dataset's date range.
        """
        normalized_path = Path(parquet_path).as_posix()
        con = duckdb_engine.get_connection()
        try:
            sql = f"""
                SELECT 
                    MIN({date_col}::DATE) AS min_date,
                    MAX({date_col}::DATE) AS max_date,
                    MAX({date_col}::DATE) - MIN({date_col}::DATE) AS date_diff_days
                FROM '{normalized_path}'
                WHERE {date_col} IS NOT NULL
            """
            res = con.execute(sql).pl()
            if res.height == 0 or res[0, 2] is None:
                return TimeSeriesGranularity.MONTH

            diff_days = int(res[0, 2])
            if diff_days > 730:
                return TimeSeriesGranularity.QUARTER
            elif diff_days > 90:
                return TimeSeriesGranularity.MONTH
            elif diff_days > 28:
                return TimeSeriesGranularity.WEEK
            else:
                return TimeSeriesGranularity.DAY
        except Exception:
            return TimeSeriesGranularity.MONTH
        finally:
            con.close()

    @classmethod
    def compute_timeseries(
        cls,
        dataset_id: str,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        metrics: List[str],
        granularity: Optional[TimeSeriesGranularity] = None,
        filters: Optional[List[DimensionFilter]] = None,
        quality_context: Optional[Dict[str, Any]] = None,
        metric_definitions: Optional[Dict[str, MetricDefinition]] = None,
    ) -> TimeSeriesResponse:
        """
        Executes time-series aggregation query and calculates MoM/QoQ/YoY growth rates.
        """
        start_time = time.perf_counter()
        normalized_path = Path(parquet_path).as_posix()

        # Identify date column
        date_col = semantic_model.date_column
        if not date_col and semantic_model.time_dimensions:
            date_col = semantic_model.time_dimensions[0]

        if not date_col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No date or time column identified in dataset semantic model for time-series analysis.",
            )

        # Select granularity
        gran = granularity or cls.auto_detect_granularity(parquet_path, date_col)

        # Collect metrics
        all_computable = {m.id: m for m in metric_capability_analyzer.get_computable_metrics(semantic_model)}
        active_metrics: List[MetricDefinition] = [all_computable[m] for m in metrics if m in all_computable]
        if not active_metrics:
            active_metrics = list(all_computable.values())[:2]

        where_clause, params = duckdb_engine.build_where_clause(filters)
        date_where = f"{date_col} IS NOT NULL"
        if where_clause:
            full_where = f"{where_clause} AND {date_where}"
        else:
            full_where = f"WHERE {date_where}"

        # Build DuckDB time trunc expression
        duckdb_interval = gran.value
        select_parts = [
            f"strftime(date_trunc('{duckdb_interval}', {date_col}::TIMESTAMP), '%Y-%m-%d') AS period_start",
        ]
        for m in active_metrics:
            select_parts.append(f"{m.sql_template} AS {m.id}")

        sql = f"""
            SELECT {', '.join(select_parts)}
            FROM '{normalized_path}'
            {full_where}
            GROUP BY 1
            ORDER BY 1 ASC
        """

        con = duckdb_engine.get_connection()
        try:
            df = con.execute(sql, params).pl()
            points: List[TimeSeriesPoint] = []

            for row in df.to_dicts():
                p_start = str(row["period_start"])
                if gran == TimeSeriesGranularity.YEAR:
                    period_label = p_start[:4]
                elif gran == TimeSeriesGranularity.QUARTER:
                    month = int(p_start[5:7])
                    period_label = f"Q{((month - 1) // 3) + 1} {p_start[:4]}"
                elif gran == TimeSeriesGranularity.MONTH:
                    period_label = f"{p_start[:4]}-{p_start[5:7]}"
                else:
                    period_label = p_start
                values: Dict[str, Optional[float]] = {}
                formatted: Dict[str, str] = {}

                for m in active_metrics:
                    val = row.get(m.id)
                    float_val = float(val) if val is not None else None
                    values[m.id] = float_val
                    formatted[m.id] = metric_capability_analyzer.format_metric_value(float_val, m)

                points.append(
                    TimeSeriesPoint(
                        period_start=p_start,
                        period_label=period_label,
                        values=values,
                        formatted_values=formatted,
                    )
                )

            # Compute Period-over-Period Growth Summary for the latest two periods
            growth_summary: Dict[str, PeriodOverPeriodGrowth] = {}
            if len(points) >= 2:
                prior_pt = points[-2]
                curr_pt = points[-1]

                # Augment quality context with the period-depth signal.
                period_qc = dict(quality_context or {})
                period_qc.setdefault("has_periods", True)

                for m in active_metrics:
                    p_val = prior_pt.values.get(m.id) or 0.0
                    c_val = curr_pt.values.get(m.id) or 0.0
                    abs_change = round(c_val - p_val, 2)
                    pct_change = round((abs_change / p_val * 100.0), 2) if p_val != 0 else None

                    trend = "flat"
                    if abs_change > 0:
                        trend = "up"
                    elif abs_change < 0:
                        trend = "down"

                    # Confidence + headline insight
                    dq_score, conf_label, conf_factors = _compute_data_quality_score(m, period_qc)

                    growth_obj = PeriodOverPeriodGrowth(
                        metric_id=m.id,
                        current_period=curr_pt.period_start,
                        prior_period=prior_pt.period_start,
                        current_value=round(c_val, 2),
                        prior_value=round(p_val, 2),
                        absolute_change=abs_change,
                        growth_percentage=pct_change,
                        trend=trend,
                        data_quality_score=dq_score,
                        confidence_label=conf_label,
                        confidence_factors=conf_factors,
                        headline_insight=None,
                    )
                    growth_summary[m.id] = growth_obj

                # Re-run headline now that we have the full growth object so
                # the generator has trend context.
                if date_col:
                    for m_id, growth_obj in growth_summary.items():
                        m_def = next((mm for mm in active_metrics if mm.id == m_id), None)
                        if not m_def:
                            continue
                        new_headline = _generate_headline_insight(
                            metric=m_def,
                            growth=growth_obj,
                            parquet_path=parquet_path,
                            semantic_model=semantic_model,
                            date_col=date_col,
                        )
                        if new_headline:
                            growth_obj.headline_insight = new_headline
            else:
                # Single period: surface a "limited history" signal even without growth.
                period_qc = dict(quality_context or {})
                period_qc["has_periods"] = False
                last_pt = points[-1] if points else None
                for m in active_metrics:
                    dq_score, conf_label, conf_factors = _compute_data_quality_score(m, period_qc)
                    growth_summary[m.id] = PeriodOverPeriodGrowth(
                        metric_id=m.id,
                        current_period=last_pt.period_start if last_pt else "",
                        prior_period="",
                        current_value=float(last_pt.values.get(m.id) or 0.0) if last_pt else 0.0,
                        prior_value=0.0,
                        absolute_change=0.0,
                        growth_percentage=None,
                        trend="flat",
                        data_quality_score=dq_score,
                        confidence_label=conf_label or "Limited history",
                        confidence_factors=conf_factors,
                        headline_insight="Insufficient history for trend comparison — at least 2 periods of data are required.",
                    )

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return TimeSeriesResponse(
                dataset_id=dataset_id,
                date_column=date_col,
                granularity=gran,
                metrics=[m.id for m in active_metrics],
                points=points,
                growth_summary=growth_summary,
                execution_time_ms=elapsed_ms,
            )
        finally:
            con.close()


timeseries_engine = TimeSeriesEngine()
