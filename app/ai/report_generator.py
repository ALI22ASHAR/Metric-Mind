import logging
from typing import Any, Dict, List, Optional

from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.anomalies import AnomalyReportResponse
from app.schemas.insights import DatasetInsightsSummary
from app.schemas.metrics import MetricResult
from app.schemas.quality import DataQualityReport
from app.schemas.report import ExecutiveReportResponse, ReportSection
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)


class ExecutiveReportGenerator:
    """
    Synthesizes comprehensive executive intelligence reports compiling summaries,
    KPI scorecards, category dynamics, anomaly risks, and strategic next steps.
    """

    @classmethod
    def generate_report(
        cls,
        dataset_id: str,
        domain: str,
        quality_report: Optional[DataQualityReport],
        semantic_model: SemanticModelSchema,
        kpi_results: Any,
        insights_summary: Optional[DatasetInsightsSummary],
        anomalies_summary: Optional[AnomalyReportResponse],
        ai_understanding: Optional[AIDatasetUnderstanding],
    ) -> ExecutiveReportResponse:
        """
        Builds the executive markdown document and structured response.
        """
        report_domain = {
            "human_resources": "Human Resources",
            "saas_subscription": "SaaS Subscription",
            "logistics_supply_chain": "Logistics & Supply Chain",
        }.get(domain, domain.replace("_", " ").title())
        title = f"Executive Intelligence Brief: {report_domain} Performance Report"
        q_score = (
            getattr(quality_report, "quality_score", None)
            or getattr(quality_report, "overall_quality_score", None)
            or 100.0
        )

        # Section 1: Executive Summary
        biz_summary = getattr(ai_understanding, "business_summary", None)
        summary_text = (
            biz_summary
            if biz_summary
            else f"Automated analytical synthesis for dataset {dataset_id} across primary computed business metrics."
        )

        sections: List[ReportSection] = []
        if isinstance(kpi_results, dict):
            kpi_list = list(kpi_results.values())
        elif isinstance(kpi_results, list):
            kpi_list = kpi_results
        else:
            kpi_list = []

        if domain == "human_resources":
            hr_metric_order = {
                "total_employees": 0,
                "active_employees": 1,
                "active_departments": 2,
                "workforce_locations": 3,
                "average_age": 4,
                "average_salary": 5,
                "turnover_rate": 6,
                "average_tenure": 7,
                "avg_performance_rating": 8,
                "hires_over_time": 9,
                "hire_rate": 10,
            }
            kpi_list = sorted(
                [k for k in kpi_list if (getattr(k, "name", None) or k.get("name")) in hr_metric_order],
                key=lambda k: hr_metric_order[getattr(k, "name", None) or k.get("name")],
            )

        # 1. Performance Overview
        kpi_bullets = []
        for k in kpi_list[:6]:
            name = getattr(k, "name", None) or (k.get("name") if isinstance(k, dict) else "Metric")
            label = getattr(k, "label", None) or (k.get("label") if isinstance(k, dict) else None)
            val = getattr(k, "formatted_value", None) or (k.get("formatted_value") if isinstance(k, dict) else str(getattr(k, "value", "")))
            kpi_bullets.append(f"**{label or str(name).replace('_', ' ').title()}**: {val}")

        sections.append(
            ReportSection(
                title="1. Executive KPI Scorecard",
                content="Core operational and financial metrics calculated deterministically from source records.",
                bullet_points=kpi_bullets,
            )
        )

        # 2. Automated Strategic Insights
        if insights_summary and insights_summary.insights:
            ins_bullets = [
                f"**{i.title}**: {i.description} ({i.recommendation or 'Monitor closely'})"
                for i in insights_summary.insights[:4]
            ]
            sections.append(
                ReportSection(
                    title=(
                        "2. Workforce Drivers & Concentration"
                        if domain == "human_resources"
                        else "2. Key Market Drivers & Concentration"
                    ),
                    content=(
                        "Automated workforce analysis evaluating headcount concentration, departmental distribution, and talent risks."
                        if domain == "human_resources"
                        else "Automated segment analysis evaluating revenue concentration, dominant categories, and margin risks."
                    ),
                    bullet_points=ins_bullets,
                )
            )

        # 3. Operational Anomalies & Risks
        if anomalies_summary and anomalies_summary.anomalies:
            anom_bullets = [
                f"**{a.metric.replace('_', ' ').title()} ({a.period})**: {a.explanation} [Severity: {a.severity.upper()}]"
                for a in anomalies_summary.anomalies[:3]
            ]
            sections.append(
                ReportSection(
                    title=(
                        "3. Workforce Risk Radar & Operational Anomalies"
                        if domain == "human_resources"
                        else "3. Risk Radar & Operational Anomalies"
                    ),
                    content=(
                        "Statistical variance analysis flagging unusual hiring activity, headcount changes, and workforce metric shifts."
                        if domain == "human_resources"
                        else "Statistical variance analysis flagging unexpected demand spikes, revenue dips, or margin compression."
                    ),
                    bullet_points=anom_bullets,
                )
            )

        # Strategic Recommendations
        if domain == "human_resources":
            recommendations = [
                "Review headcount concentration by department and align hiring plans with workforce demand.",
                "Monitor turnover and inactive-employee segments to prioritize retention actions.",
                "Track hiring velocity and workforce locations monthly to identify staffing gaps early.",
            ]
        else:
            recommendations = [
                "Protect high-margin revenue drivers through dedicated account management.",
                "Address margin compression in underperforming segments via renegotiated supplier pricing.",
                "Establish automated alerts for statistical revenue variance exceeding +/-30%.",
            ]

        # Assemble Full Markdown Document
        md_lines = [
            f"# {title}",
            f"*Generated by MetricMind Automated BI Platform for Dataset `{dataset_id}`*",
            "",
            "## Executive Summary",
            summary_text,
            "",
            f"**Dataset Health & Reliability Score**: {q_score:.1f}/100",
            "",
        ]

        for sec in sections:
            md_lines.append(f"## {sec.title}")
            md_lines.append(sec.content)
            md_lines.append("")
            if sec.bullet_points:
                for b in sec.bullet_points:
                    md_lines.append(f"* {b}")
                md_lines.append("")

        md_lines.append("## 4. Strategic Recommendations")
        for r in recommendations:
            md_lines.append(f"1. {r}")
        md_lines.append("")

        full_md = "\n".join(md_lines)

        return ExecutiveReportResponse(
            dataset_id=dataset_id,
            title=title,
            executive_summary=summary_text,
            domain=domain,
            quality_score=q_score,
            sections=sections,
            strategic_recommendations=recommendations,
            markdown_content=full_md,
        )


executive_report_generator = ExecutiveReportGenerator()
