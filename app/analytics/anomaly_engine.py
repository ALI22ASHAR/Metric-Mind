import logging
import math
import uuid
from typing import List, Optional

from app.analytics.duckdb_engine import duckdb_engine
from app.analytics.timeseries import timeseries_engine
from app.schemas.anomalies import (
    AnomalyReportResponse,
    AnomalySeverity,
    AnomalyType,
    DetectedAnomaly,
    DimensionContribution,
)
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)


def generate_anomaly_id() -> str:
    return f"anom_{uuid.uuid4().hex[:12]}"


class AnomalyEngine:
    """
    Statistical time-series anomaly detection and root cause decomposition engine.
    """

    @classmethod
    def detect_anomalies(
        cls,
        dataset_id: str,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        metrics: Optional[List[str]] = None,
    ) -> AnomalyReportResponse:
        """
        Evaluates temporal trends for statistical anomalies and performs root cause drill-down.
        """
        anomalies: List[DetectedAnomaly] = []
        date_col = semantic_model.date_column
        if not date_col:
            return AnomalyReportResponse(dataset_id=dataset_id, total_anomalies=0, anomalies=[])

        active_metrics = metrics or ["total_revenue", "units_sold"]

        try:
            # 1. Fetch chronological time series points
            ts_res = timeseries_engine.compute_timeseries(
                dataset_id=dataset_id,
                parquet_path=parquet_path,
                semantic_model=semantic_model,
                metrics=active_metrics,
            )
            points = ts_res.points
            if len(points) < 2:
                return AnomalyReportResponse(dataset_id=dataset_id, total_anomalies=0, anomalies=[])

            for metric in active_metrics:
                values = [p.values.get(metric, 0) or 0 for p in points]
                if not any(values):
                    continue

                mean_val = sum(values) / len(values)
                variance = sum((x - mean_val) ** 2 for x in values) / len(values)
                std_dev = math.sqrt(variance) if variance > 0 else 1.0

                for i in range(1, len(points)):
                    curr_val = values[i]
                    prior_val = values[i - 1]
                    period_str = points[i].period_start
                    prior_period = points[i - 1].period_start

                    delta = curr_val - prior_val
                    pct_change = ((curr_val - prior_val) / prior_val * 100.0) if prior_val > 0 else 0.0
                    z_score = abs(curr_val - mean_val) / std_dev if std_dev > 0 else 0.0

                    # Anomaly trigger criteria: > 30% drop, > 50% surge, or Z-score > 1.8
                    is_anomaly = abs(pct_change) >= 30.0 or z_score >= 1.8

                    if is_anomaly:
                        anom_type = AnomalyType.SPIKE if delta > 0 else AnomalyType.DROP
                        severity = (
                            AnomalySeverity.CRITICAL
                            if abs(pct_change) >= 50.0 or z_score >= 2.5
                            else AnomalySeverity.WARNING
                            if abs(pct_change) >= 30.0 or z_score >= 1.8
                            else AnomalySeverity.INFO
                        )

                        # Phase 23: Root Cause Decomposition
                        root_causes, explanation = cls._decompose_root_causes(
                            parquet_path=parquet_path,
                            semantic_model=semantic_model,
                            metric=metric,
                            period=period_str,
                            prior_period=prior_period,
                            delta=delta,
                            pct_change=pct_change,
                        )

                        anomalies.append(
                            DetectedAnomaly(
                                id=generate_anomaly_id(),
                                metric=metric,
                                period=period_str,
                                actual_value=round(curr_val, 2),
                                expected_value=round(mean_val, 2),
                                deviation_percentage=round(pct_change, 1),
                                z_score=round(z_score, 2),
                                severity=severity,
                                anomaly_type=anom_type,
                                root_causes=root_causes,
                                explanation=explanation,
                            )
                        )
        except Exception as exc:
            logger.warning("Anomaly detection error: %s", exc)

        return AnomalyReportResponse(
            dataset_id=dataset_id,
            total_anomalies=len(anomalies),
            anomalies=anomalies,
        )

    @classmethod
    def _decompose_root_causes(
        cls,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        metric: str,
        period: str,
        prior_period: str,
        delta: float,
        pct_change: float,
    ) -> tuple[List[DimensionContribution], str]:
        """
        Drills down into categorical dimensions to identify which segments drove the anomaly.
        """
        root_causes: List[DimensionContribution] = []
        dim = semantic_model.category_column or semantic_model.product_column or (semantic_model.dimensions[0] if semantic_model.dimensions else None)
        date_col = semantic_model.date_column

        if not dim or not date_col:
            sign = "increased" if delta > 0 else "decreased"
            return (
                [],
                f"{metric.replace('_', ' ').title()} {sign} by {abs(pct_change):.1f}% compared to prior period.",
            )

        try:
            # Query breakdown by dimension for current and prior periods
            sql_prior = f"""
                SELECT {dim} AS dimension_value, SUM(Quantity * Sale_Price) AS val
                FROM '{parquet_path}'
                WHERE strftime({date_col}, '%Y-%m') = '{prior_period[:7]}'
                GROUP BY {dim}
            """
            sql_curr = f"""
                SELECT {dim} AS dimension_value, SUM(Quantity * Sale_Price) AS val
                FROM '{parquet_path}'
                WHERE strftime({date_col}, '%Y-%m') = '{period[:7]}'
                GROUP BY {dim}
            """

            prior_rows = {r["dimension_value"]: r["val"] for r in duckdb_engine.execute_safe_query(parquet_path, sql_prior).rows}
            curr_rows = {r["dimension_value"]: r["val"] for r in duckdb_engine.execute_safe_query(parquet_path, sql_curr).rows}

            all_keys = set(prior_rows.keys()).union(set(curr_rows.keys()))
            abs_delta = abs(delta) if abs(delta) > 0 else 1.0

            for k in all_keys:
                p_v = prior_rows.get(k, 0.0) or 0.0
                c_v = curr_rows.get(k, 0.0) or 0.0
                d = c_v - p_v
                contrib_pct = round((abs(d) / abs_delta) * 100.0, 1)

                if contrib_pct >= 10.0:
                    root_causes.append(
                        DimensionContribution(
                            dimension=dim,
                            value=str(k),
                            prior_value=round(p_v, 2),
                            current_value=round(c_v, 2),
                            delta=round(d, 2),
                            contribution_percentage=min(100.0, contrib_pct),
                        )
                    )

            root_causes.sort(key=lambda x: x.contribution_percentage, reverse=True)
            top_drivers = root_causes[:2]

            if top_drivers:
                main = top_drivers[0]
                sign = "increase" if delta > 0 else "drop"
                explanation = f"Metric {sign} of {abs(pct_change):.1f}% in {period[:7]} was primarily driven by '{main.value}' in {dim} ({main.contribution_percentage}% contribution)."
            else:
                sign = "increased" if delta > 0 else "decreased"
                explanation = f"{metric.replace('_', ' ').title()} {sign} by {abs(pct_change):.1f}% evenly across segments."

            return root_causes, explanation

        except Exception as exc:
            logger.warning("Root cause decomposition failed: %s", exc)
            sign = "increased" if delta > 0 else "decreased"
            return (
                [],
                f"{metric.replace('_', ' ').title()} {sign} by {abs(pct_change):.1f}%.",
            )


anomaly_engine = AnomalyEngine()
