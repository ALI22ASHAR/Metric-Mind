from typing import Dict, List, Optional
from app.analytics.duckdb_engine import duckdb_engine
from app.schemas.benchmark import DatasetBenchmarkResponse, MetricBenchmarkDiff
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import SemanticModelSchema


class BenchmarkEngine:
    """
    Computes comparative performance benchmarks between two distinct datasets or reporting periods.
    """

    @classmethod
    def compare_datasets(
        cls,
        base_dataset_id: str,
        base_parquet: str,
        base_semantic: SemanticModelSchema,
        target_dataset_id: str,
        target_parquet: str,
        target_semantic: SemanticModelSchema,
        metrics: List[MetricDefinition],
    ) -> DatasetBenchmarkResponse:
        """
        Calculates metric deltas between base and target datasets.
        """
        diffs: List[MetricBenchmarkDiff] = []
        eval_metrics = [m for m in metrics if m.is_computable][:5]

        for m in eval_metrics:
            sql_base = f"SELECT {m.sql_template} AS val FROM '{base_parquet}'"
            sql_target = f"SELECT {m.sql_template} AS val FROM '{target_parquet}'"

            try:
                r_base = duckdb_engine.execute_safe_query(base_parquet, sql_base).rows[0].get("val") or 0.0
                r_target = duckdb_engine.execute_safe_query(target_parquet, sql_target).rows[0].get("val") or 0.0

                b_val = float(r_base)
                t_val = float(r_target)
                delta = t_val - b_val
                pct = ((delta / b_val) * 100.0) if b_val > 0 else 0.0

                diffs.append(
                    MetricBenchmarkDiff(
                        metric_id=m.id,
                        label=m.label,
                        base_dataset_value=round(b_val, 2),
                        target_dataset_value=round(t_val, 2),
                        delta_value=round(delta, 2),
                        delta_percentage=round(pct, 1),
                        is_positive_growth=delta >= 0,
                    )
                )
            except Exception:
                continue

        summary = (
            f"Benchmark analysis across {len(diffs)} core KPIs between baseline '{base_dataset_id}' "
            f"and target '{target_dataset_id}' shows {sum(1 for d in diffs if d.is_positive_growth)} positive indicators."
        )

        return DatasetBenchmarkResponse(
            base_dataset_id=base_dataset_id,
            target_dataset_id=target_dataset_id,
            metric_comparisons=diffs,
            overall_summary=summary,
        )


benchmark_engine = BenchmarkEngine()
