import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.metrics import MetricDefinition

logger = logging.getLogger(__name__)

# Fallback deterministic priority hierarchy
DEFAULT_KPI_PRIORITY = [
    "total_revenue",
    "total_profit",
    "profit_margin",
    "average_order_value",
    "total_orders",
    "avg_profit_per_order",
    "max_order_value",
    "units_sold",
    "units_per_order",
    "discount_rate",
    "active_products",
    "total_cost",
    "average_unit_price",
    "total_discount",
]

DOMAIN_KPI_PRIORITY = {
    "human_resources": [
        "total_employees",
        "active_departments",
        "average_age",
        "workforce_locations",
        "active_employees",
        "turnover_rate",
        "average_salary",
        "average_tenure",
        "avg_performance_rating",
        "hires_over_time",
        "hire_rate",
    ],
    "saas_subscription": [
        "total_mrr",
        "total_users",
        "active_plans",
        "churn_rate",
    ],
    "logistics_supply_chain": [
        "total_shipments",
        "average_weight",
        "active_carriers",
        "on_time_delivery_rate",
    ],
    "healthcare": [
        "total_patients",
        "total_admissions",
        "active_diagnoses",
        "average_length_of_stay",
    ],
    "sales": DEFAULT_KPI_PRIORITY,
}


class KpiRecommendationItem(BaseModel):
    metric_id: str
    rank: int
    rationale: str


class KpiRecommendationsResult(BaseModel):
    selected_kpis: List[KpiRecommendationItem] = Field(
        default_factory=list,
        description="Top 4-6 prioritized business KPIs",
    )


class KpiRecommendationAgent:
    """
    Agent that selects the top 4-6 highest impact KPIs for executive dashboard summary cards.
    """

    @classmethod
    def get_fallback_kpis(
        cls,
        available_metrics: List[MetricDefinition],
        limit: int = 4,
        domain: str = "generic_analytics",
    ) -> List[MetricDefinition]:
        """
        Deterministic fallback selector if LLM is unavailable or offline.
        """
        metrics_by_id = {m.id: m for m in available_metrics}
        selected: List[MetricDefinition] = []

        priority = DOMAIN_KPI_PRIORITY.get(domain, DEFAULT_KPI_PRIORITY)
        for kpi_id in priority:
            if kpi_id in metrics_by_id:
                selected.append(metrics_by_id[kpi_id])
            if len(selected) >= limit:
                break

        # If less than limit, add remaining available metrics
        for m in available_metrics:
            if m not in selected and len(selected) < limit:
                selected.append(m)

        return selected

    @classmethod
    async def recommend_kpis(
        cls,
        domain: str,
        available_metrics: List[MetricDefinition],
        ai_understanding: Optional[AIDatasetUnderstanding] = None,
        provider: Optional[BaseLLMProvider] = None,
        limit: int = 4,
    ) -> List[MetricDefinition]:
        """
        Selects and prioritizes the top 4-6 KPIs for executive display.
        """
        if not available_metrics:
            return []

        if len(available_metrics) <= limit:
            return available_metrics

        llm = provider or get_llm_provider()
        avail_dict = {m.id: m for m in available_metrics}

        prompt = f"""
Dataset Domain: {domain}
Available Computable KPIs:
"""
        for m in available_metrics:
            prompt += f"- ID: '{m.id}', Name: '{m.label}', Formula: {m.sql_template}\n"

        if ai_understanding and ai_understanding.business_summary:
            prompt += f"\nBusiness Summary: {ai_understanding.business_summary}\n"

        prompt += f"\nSelect the top {limit} most critical KPIs for executive business monitoring in rank order."

        system_prompt = """You are an expert BI Architect. Select the top 4 to 6 most insightful and actionable business KPIs from the provided computable list. Only use metric IDs that exist in the input."""

        try:
            res: KpiRecommendationsResult = await llm.generate_structured(
                prompt=prompt,
                system_prompt=system_prompt,
                response_schema=KpiRecommendationsResult,
            )

            selected_metrics: List[MetricDefinition] = []
            for item in res.selected_kpis:
                if item.metric_id in avail_dict and avail_dict[item.metric_id] not in selected_metrics:
                    selected_metrics.append(avail_dict[item.metric_id])

            if len(selected_metrics) >= 2:
                return selected_metrics[:limit]
        except Exception as exc:
            logger.warning("AI KPI recommendation failed: %s. Using deterministic fallback.", exc)

        return cls.get_fallback_kpis(available_metrics, limit=limit, domain=domain)


kpi_recommendation_agent = KpiRecommendationAgent()
