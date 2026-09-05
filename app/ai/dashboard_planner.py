import logging
import uuid
from typing import List, Optional
from app.ai.kpi_agent import kpi_recommendation_agent
from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.dashboard import (
    DashboardFilterConfig,
    DashboardSpec,
    GridPosition,
    WidgetConfig,
    WidgetType,
)
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import BusinessConcept, SemanticModelSchema

logger = logging.getLogger(__name__)


def generate_dashboard_id() -> str:
    return f"dsh_{uuid.uuid4().hex[:12]}"


class AIDashboardPlanner:
    """
    Synthesizes semantic metadata, AI understanding, and KPIs into a balanced, professional 12-column dashboard layout.
    """

    @classmethod
    def plan_dashboard(
        cls,
        dataset_id: str,
        semantic_model: SemanticModelSchema,
        available_metrics: List[MetricDefinition],
        ai_understanding: Optional[AIDatasetUnderstanding] = None,
        title: Optional[str] = None,
        theme: str = "dark",
    ) -> DashboardSpec:
        """
        Constructs a complete DashboardSpec with KPI cards, temporal line charts, dimensional breakdowns,
        donut charts, and tables.
        """
        dashboard_id = generate_dashboard_id()
        domain = semantic_model.domain or (ai_understanding.domain if ai_understanding else "generic_analytics")

        # Contextual Domain Dashboard Titles
        if domain == "human_resources":
            domain_title = "Human Resources & Workforce Dashboard"
            domain_subtitle = "Comprehensive employee headcount, departmental distribution, and hiring analytics"
            trend_title = "Workforce Growth / Hiring Trajectory Over Time"
            bar_title_prefix = "Headcount Distribution by"
            donut_title_prefix = "Workforce Share by"
            table_title_suffix = "Workforce Detail"
        elif domain == "saas_subscription":
            domain_title = "SaaS & Subscription Intelligence Dashboard"
            domain_subtitle = "Subscriber growth, recurring revenue (MRR), and retention analytics"
            trend_title = "Subscriber Growth Trajectory Over Time"
            bar_title_prefix = "Subscribers by"
            donut_title_prefix = "Tier Distribution by"
            table_title_suffix = "Subscription Matrix"
        elif domain == "logistics_supply_chain":
            domain_title = "Logistics & Supply Chain Operations Dashboard"
            domain_subtitle = "Shipment tracking, delivery volume, and carrier operations"
            trend_title = "Shipment Volume Over Time"
            bar_title_prefix = "Shipments by"
            donut_title_prefix = "Carrier Share by"
            table_title_suffix = "Operations Matrix"
        elif domain == "healthcare":
            domain_title = "Healthcare & Clinical Intelligence Dashboard"
            domain_subtitle = "Patient admission volume, clinical diagnoses, and healthcare operations"
            trend_title = "Patient Admissions Over Time"
            bar_title_prefix = "Patients by"
            donut_title_prefix = "Patient Share by"
            table_title_suffix = "Clinical Performance Matrix"
        elif domain == "sales":
            domain_title = "Sales & Revenue Intelligence Dashboard"
            domain_subtitle = "Real-time sales performance, revenue analytics, and KPI tracking"
            trend_title = "Revenue & Performance Over Time"
            bar_title_prefix = "Performance by"
            donut_title_prefix = "Market Share by"
            table_title_suffix = "Performance Matrix"
        else:
            domain_title = "Executive Intelligence Dashboard"
            domain_subtitle = "Real-time business performance analytics and dimensional breakdown"
            trend_title = "Activity & Volume Over Time"
            bar_title_prefix = "Volume by"
            donut_title_prefix = "Distribution by"
            table_title_suffix = "Analytics Matrix"

        default_title = title or domain_title
        subtitle = (
            ai_understanding.business_summary[:120] + "..."
            if ai_understanding and len(ai_understanding.business_summary) > 120
            else domain_subtitle
        )

        widgets: List[WidgetConfig] = []
        filters: List[DashboardFilterConfig] = []

        # 1. Select top 4 KPI Cards for Row 0
        top_kpis = kpi_recommendation_agent.get_fallback_kpis(
            available_metrics,
            limit=4,
            domain=domain,
        )
        num_kpis = max(len(top_kpis), 1)
        kpi_card_width = 3 if num_kpis == 4 else 4 if num_kpis == 3 else 6 if num_kpis == 2 else 3

        for idx, kpi in enumerate(top_kpis):
            widgets.append(
                WidgetConfig(
                    id=f"kpi_{kpi.id}_{idx+1}",
                    type=WidgetType.KPI_CARD,
                    title=kpi.label,
                    description=kpi.description,
                    metric_id=kpi.id,
                    metrics=[kpi.id],
                    position=GridPosition(x=(idx % 4) * kpi_card_width, y=0, w=kpi_card_width, h=2),
                    options={"format": kpi.format_spec, "unit": kpi.unit},
                )
            )

        # 2. Dimensions and Time identification
        date_col = semantic_model.date_column or (semantic_model.time_dimensions[0] if semantic_model.time_dimensions else None)
        categorical_dims = [
            d for d in semantic_model.dimensions
            if d not in semantic_model.identifiers and d != date_col
        ]

        if domain == "human_resources":
            primary_dim = semantic_model.mappings.get(BusinessConcept.DEPARTMENT) or (categorical_dims[0] if categorical_dims else None)
        else:
            primary_dim = (
                semantic_model.category_column
                or semantic_model.mappings.get(BusinessConcept.DEPARTMENT)
                or semantic_model.product_column
                or (categorical_dims[0] if categorical_dims else None)
            )
        secondary_dim = (
            semantic_model.region_column
            or semantic_model.mappings.get(BusinessConcept.CITY)
            or semantic_model.mappings.get(BusinessConcept.STATE)
            or (categorical_dims[1] if len(categorical_dims) > 1 else None)
        )

        top_metric_ids = [m.id for m in top_kpis[:2]] if top_kpis else ["total_records"]
        rev_or_primary_metric = top_metric_ids[0] if top_metric_ids else "total_records"

        # For HR datasets, the time-series chart should track HIRES, not headcount.
        # Headcount is a static snapshot; hires is the actual flow over time.
        trend_metric_ids = top_metric_ids
        if domain == "human_resources" and "hires_over_time" in [m.id for m in available_metrics]:
            trend_metric_ids = ["hires_over_time"]
        elif domain == "saas_subscription" and "total_users" in [m.id for m in available_metrics]:
            trend_metric_ids = ["total_users"]
        elif domain == "logistics_supply_chain" and "total_shipments" in [m.id for m in available_metrics]:
            trend_metric_ids = ["total_shipments"]
        elif domain == "healthcare" and "total_patients" in [m.id for m in available_metrics]:
            trend_metric_ids = ["total_patients"]

        if domain == "human_resources":
            hr_filter_concepts = [
                (BusinessConcept.DEPARTMENT, "Department"),
                (BusinessConcept.JOB_TITLE, "Job Title"),
                (BusinessConcept.STATUS, "Employment Status"),
                (BusinessConcept.GENDER, "Gender"),
                (BusinessConcept.EDUCATION, "Education Level"),
                (BusinessConcept.SALARY_BAND, "Salary Band"),
            ]
            time_filter_dimensions = [
                {"column": semantic_model.mappings[concept], "label": label}
                for concept, label in hr_filter_concepts
                if semantic_model.mappings.get(concept)
            ]
        else:
            time_filter_dimensions = [
                {"column": "Category", "label": "Category"},
                {"column": "Product", "label": "Product"},
                {"column": "Country", "label": "Country / Region"},
            ]

        current_y = 2

        # 3. Row 1: Time-Series Trend + Primary Breakdown
        if date_col:
            widgets.append(
                WidgetConfig(
                    id="widget_revenue_trend",
                    type=WidgetType.LINE_CHART,
                    title=trend_title,
                    description="Chronological performance trend with growth trajectory",
                    metrics=trend_metric_ids,
                    granularity="month",
                    position=GridPosition(x=0, y=current_y, w=8, h=5),
                    options={
                        "show_legend": True,
                        "smooth_curve": True,
                        "filter_dimensions": time_filter_dimensions,
                    },
                )
            )
            if primary_dim:
                widgets.append(
                    WidgetConfig(
                        id=f"widget_bar_{primary_dim.lower()}",
                        type=WidgetType.BAR_CHART,
                        title=f"{bar_title_prefix} {primary_dim}",
                        description=f"Breakdown of {rev_or_primary_metric.replace('_', ' ').title()} across {primary_dim}",
                        dimension=primary_dim,
                        metrics=[rev_or_primary_metric],
                        position=GridPosition(x=8, y=current_y, w=4, h=5),
                        options={"orientation": "vertical", "top_n": 10},
                    )
                )
            else:
                widgets.append(
                    WidgetConfig(
                        id="widget_area_trend",
                        type=WidgetType.AREA_CHART,
                        title="Volume Trend",
                        metrics=trend_metric_ids[-1:],
                        granularity="month",
                        position=GridPosition(x=8, y=current_y, w=4, h=5),
                    )
                )
            current_y += 5
        elif primary_dim:
            widgets.append(
                WidgetConfig(
                    id=f"widget_bar_{primary_dim.lower()}",
                    type=WidgetType.BAR_CHART,
                    title=f"{bar_title_prefix} {primary_dim}",
                    dimension=primary_dim,
                    metrics=top_metric_ids,
                    position=GridPosition(x=0, y=current_y, w=6, h=5),
                )
            )
            if secondary_dim:
                widgets.append(
                    WidgetConfig(
                        id=f"widget_bar_{secondary_dim.lower()}",
                        type=WidgetType.BAR_CHART,
                        title=f"{bar_title_prefix} {secondary_dim}",
                        dimension=secondary_dim,
                        metrics=[rev_or_primary_metric],
                        position=GridPosition(x=6, y=current_y, w=6, h=5),
                    )
                )
            current_y += 5

        # 4. Row 2: Secondary Share (Pie/Donut) + Detailed Table
        share_dim = secondary_dim or primary_dim
        if share_dim:
            widgets.append(
                WidgetConfig(
                    id=f"widget_pie_{share_dim.lower()}",
                    type=WidgetType.PIE_CHART,
                    title=f"{donut_title_prefix} {share_dim}",
                    description="Proportional segment contribution",
                    dimension=share_dim,
                    metrics=[rev_or_primary_metric],
                    position=GridPosition(x=0, y=current_y, w=4, h=5),
                    options={"donut": True},
                )
            )
            table_dim = primary_dim or share_dim
            widgets.append(
                WidgetConfig(
                    id=f"widget_table_{table_dim.lower()}",
                    type=WidgetType.TABLE,
                    title=f"Detailed {table_dim} {table_title_suffix}",
                    description="Comprehensive multi-metric breakdown",
                    dimension=table_dim,
                    metrics=(
                        [m.id for m in available_metrics
                         if m.id not in {k.id for k in top_kpis}
                         and m.id in {
                             "active_employees", "turnover_rate", "average_salary",
                             "average_tenure", "avg_performance_rating", "average_age",
                         }][:4]
                        if domain == "human_resources"
                        else [m.id for m in top_kpis]
                    ),
                    position=GridPosition(x=4, y=current_y, w=8, h=5),
                    options={"pagination": True, "page_size": 10},
                )
            )
            current_y += 5

        # 5. Global Filters
        if date_col:
            filters.append(
                DashboardFilterConfig(
                    id="filter_date_range",
                    column=date_col,
                    label="Date Range",
                    filter_type="date_range",
                )
            )
        filter_dimensions = [primary_dim, secondary_dim]
        if domain == "human_resources":
            filter_dimensions.extend(
                semantic_model.mappings.get(concept)
                for concept in (
                    BusinessConcept.JOB_TITLE,
                    BusinessConcept.STATUS,
                    BusinessConcept.GENDER,
                    BusinessConcept.EDUCATION,
                    BusinessConcept.SALARY_BAND,
                )
            )
        for dim in filter_dimensions:
            if dim and dim not in [f.column for f in filters]:
                filters.append(
                    DashboardFilterConfig(
                        id=f"filter_{dim.lower()}",
                        column=dim,
                        label=dim,
                        filter_type="select",
                    )
                )

        return DashboardSpec(
            id=dashboard_id,
            dataset_id=dataset_id,
            title=default_title,
            subtitle=subtitle,
            theme=theme,
            widgets=widgets,
            filters=filters,
            version=1,
        )


ai_dashboard_planner = AIDashboardPlanner()
