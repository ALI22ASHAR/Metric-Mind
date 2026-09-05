import logging
import uuid
from pathlib import Path
from typing import List, Optional

from app.analytics.duckdb_engine import duckdb_engine
from app.schemas.insights import BusinessInsight, DatasetInsightsSummary, InsightType
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)


def generate_insight_id() -> str:
    return f"ins_{uuid.uuid4().hex[:12]}"


class BusinessInsightsEngine:
    """
    Computes automated deterministic executive business insights, Pareto concentrations,
    and performance driver summaries using DuckDB.
    """

    @classmethod
    def compute_insights(
        cls,
        dataset_id: str,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        available_metrics: List[MetricDefinition],
    ) -> DatasetInsightsSummary:
        """
        Generates structured, actionable business insights.
        """
        insights: List[BusinessInsight] = []
        candidate_dims = [
            d for d in [semantic_model.category_column, semantic_model.product_column] + semantic_model.dimensions if d
        ]
        # Deduplicate while preserving order
        unique_dims = list(dict.fromkeys(candidate_dims))
        avail_ids = [m.id for m in available_metrics]

        # 1. Pareto Concentration & Top Driver Analysis (80/20 rule)
        if "total_revenue" in avail_ids:
            for dim in unique_dims:
                try:
                    bd = duckdb_engine.compute_breakdown(
                        parquet_path=parquet_path,
                        dimension=dim,
                        metric_ids=["total_revenue"],
                        semantic_model=semantic_model,
                        limit=100,
                        sort_by="total_revenue",
                        ascending=False,
                    )
                    rows = bd.rows
                    total_rev = sum(r.get("total_revenue", 0) for r in rows)

                    if total_rev > 0 and len(rows) >= 2:
                        top_count = max(1, int(len(rows) * 0.2))
                        top_rev = sum(r.get("total_revenue", 0) for r in rows[:top_count])
                        concentration_pct = round((top_rev / total_rev) * 100.0, 1)

                        top_names = ", ".join([str(r.get("dimension_value")) for r in rows[:top_count]])
                        insights.append(
                            BusinessInsight(
                                id=generate_insight_id(),
                                type=InsightType.CONCENTRATION,
                                title=f"Revenue Concentration: Top {top_count} {dim}s Generate {concentration_pct}% of Sales",
                                description=f"The top {top_count} of {len(rows)} {dim}s ({top_names}) account for ${top_rev:,.2f} out of ${total_rev:,.2f} total revenue.",
                                metric="total_revenue",
                                dimension=dim,
                                impact_score=85.0 if concentration_pct > 70 else 65.0,
                                recommendation=f"Prioritize supply chain availability and VIP relationship management for {top_names}.",
                            )
                        )

                        # Top Driver Insight
                        best_item = rows[0]
                        best_name = best_item.get("dimension_value")
                        best_rev = best_item.get("total_revenue", 0)
                        best_share = round((best_rev / total_rev) * 100.0, 1)

                        insights.append(
                            BusinessInsight(
                                id=generate_insight_id(),
                                type=InsightType.GROWTH_DRIVER,
                                title=f"Dominant Segment: '{best_name}' Captures {best_share}% Market Share in {dim}",
                                description=f"'{best_name}' is the single largest performance driver in {dim} with ${best_rev:,.2f} in total revenue.",
                                metric="total_revenue",
                                dimension=dim,
                                impact_score=80.0,
                                recommendation=f"Assess potential cross-selling opportunities expanding from {best_name}.",
                            )
                        )
                        break  # Found best multi-item dimension
                except Exception as exc:
                    logger.warning("Pareto insight calculation skipped for %s: %s", dim, exc)

        # 2. Profitability & Margin Risk Analysis
        if "profit_margin" in avail_ids and "total_profit" in avail_ids:
            for dim in unique_dims:
                try:
                    bd_margin = duckdb_engine.compute_breakdown(
                        parquet_path=parquet_path,
                        dimension=dim,
                        metric_ids=["total_revenue", "total_profit", "profit_margin"],
                        semantic_model=semantic_model,
                        limit=20,
                        sort_by="profit_margin",
                        ascending=True,
                    )
                    low_margin_rows = [r for r in bd_margin.rows if r.get("profit_margin") is not None]
                    if low_margin_rows:
                        lowest = low_margin_rows[0]
                        low_name = lowest.get("dimension_value")
                        low_margin = lowest.get("profit_margin", 0)

                        if low_margin < 20.0:
                            insights.append(
                                BusinessInsight(
                                    id=generate_insight_id(),
                                    type=InsightType.RISK,
                                    title=f"Margin Compression Alert: '{low_name}' Operating at {low_margin:.1f}% Margin in {dim}",
                                    description=f"'{low_name}' exhibits low profitability with a margin of {low_margin:.1f}% (${lowest.get('total_profit', 0):,.2f} profit from ${lowest.get('total_revenue', 0):,.2f} revenue).",
                                    metric="profit_margin",
                                    dimension=dim,
                                    impact_score=75.0,
                                    recommendation=f"Review pricing structures, discounting, and vendor COGS for {low_name}.",
                                )
                            )
                            break
                except Exception as exc:
                    logger.warning("Margin risk insight skipped for %s: %s", dim, exc)

        # 3. Baseline Summary Insight if empty
        if not insights:
            insights.append(
                BusinessInsight(
                    id=generate_insight_id(),
                    type=InsightType.SUMMARY,
                    title="Automated Analytics Active",
                    description="Dataset successfully normalized into columnar format. Real-time deterministic aggregations are enabled.",
                    metric="record_count",
                    dimension=unique_dims[0] if unique_dims else None,
                    impact_score=50.0,
                    recommendation="Explore dimension drill-downs and natural-language queries in the AI Analyst drawer.",
                )
            )

        return DatasetInsightsSummary(
            dataset_id=dataset_id,
            total_insights=len(insights),
            insights=insights,
        )


business_insights_engine = BusinessInsightsEngine()
