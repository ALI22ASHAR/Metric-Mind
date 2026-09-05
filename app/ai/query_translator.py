import logging
import re
from typing import Any, Dict, List, Optional

from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.ai.analyst_engine import analyst_engine
from app.schemas.chat import AnalyticalQueryPlan, ChatMessage
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)


class TextToQueryAgent:
    """
    Translates natural-language business questions into validated, structured DuckDB SQL queries.
    """

    @classmethod
    def get_fallback_query_plan(
        cls,
        user_query: str,
        columns: List[str],
        semantic_model: SemanticModelSchema,
        available_metrics: List[MetricDefinition],
        conversation_history: Optional[List[ChatMessage]] = None,
        sample_values: Optional[Dict[str, List[Any]]] = None,
    ) -> AnalyticalQueryPlan:
        """
        Deterministic heuristic query planner for offline or fallback environments.
        """
        return analyst_engine.build_plan(
            user_query=user_query,
            columns=columns,
            semantic_model=semantic_model,
            available_metrics=available_metrics,
            conversation_history=conversation_history,
            sample_values=sample_values,
        )

        # Legacy planner retained below for reference during migration.
        lower_q = user_query.lower()
        history_text = " ".join(
            message.content.lower()
            for message in (conversation_history or [])[-4:]
            if message.content
        )
        metric_search_text = f"{lower_q} {history_text}"
        date_col = semantic_model.date_column
        category_col = semantic_model.category_column or semantic_model.product_column or (semantic_model.dimensions[0] if semantic_model.dimensions else None)
        # Select a registered metric so every domain uses its own formulas.
        metric_aliases = {
            "total_revenue": ["revenue", "sales", "selling", "amount", "money"],
            "total_profit": ["profit", "earnings"],
            "profit_margin": ["margin", "profitability"],
            "total_cost": ["cost", "cogs", "expense"],
            "units_sold": ["units", "quantity", "volume", "sold"],
            "total_orders": ["orders", "transactions", "records", "count"],
            "average_order_value": ["average order", "aov", "order value"],
            "discount_rate": ["discount rate", "discount percentage"],
            "total_mrr": ["mrr", "recurring revenue", "arr"],
            "churn_rate": ["churn", "cancelled", "cancellation"],
            "total_employees": ["employees", "headcount", "workforce", "staff"],
            "average_salary": ["salary", "compensation", "pay"],
            "total_shipments": ["shipments", "deliveries", "packages"],
            "average_weight": ["weight", "heavy", "light"],
            "total_patients": ["patients", "patient count"],
            "active_diagnoses": ["diagnoses", "diagnosis", "conditions"],
        }
        available_by_id = {metric.id: metric for metric in available_metrics}
        metric_name = "total_records"
        selected_metric = available_by_id.get(metric_name)
        for metric_id, aliases in metric_aliases.items():
            if metric_id in available_by_id and any(alias in metric_search_text for alias in aliases):
                metric_name = metric_id
                selected_metric = available_by_id[metric_id]
                break
        if selected_metric is None and available_metrics:
            selected_metric = available_metrics[0]
            metric_name = selected_metric.id
        metric_expr = selected_metric.sql_template if selected_metric else "COUNT(*)"

        # Time-series trend question
        if date_col and any(w in lower_q for w in ["month", "trend", "over time", "quarter", "timeline", "daily", "growth"]):
            sql = f"SELECT strftime({date_col}, '%Y-%m') AS month, {metric_expr} AS {metric_name} FROM data GROUP BY 1 ORDER BY 1 ASC"
            return AnalyticalQueryPlan(
                thought_process=f"Aggregate {metric_name} chronologically by month using {date_col}.",
                intent="trend",
                target_metric=metric_name,
                target_dimension=date_col,
                sql_query=sql,
                recommended_chart_type="line_chart",
            )

        # Categorical ranking question (top N)
        limit_match = re.search(r"\btop\s+(\d+)\b", lower_q)
        top_n = int(limit_match.group(1)) if limit_match else 5

        # Check if a specific dimension is mentioned in query (support plurals & semantic synonyms)
        dim_keywords = {
            "department": ["department", "departments", "dept", "depts", "division", "divisions", "team", "teams", "unit", "units"],
            "employee": ["employee", "employees", "staff", "worker", "workers", "headcount", "personnel", "people"],
            "job_title": ["title", "titles", "role", "roles", "position", "positions", "job", "jobs", "occupation"],
            "country": ["country", "countries", "nation", "nations", "region", "regions", "territory", "territories", "geography", "geo", "market", "area"],
            "region": ["region", "regions", "country", "countries", "territory", "territories", "market", "area", "geo"],
            "category": ["category", "categories", "segment", "segments", "type", "types", "group"],
            "product": ["product", "products", "item", "items", "sku", "skus", "goods", "merchandise"],
            "city": ["city", "cities", "town", "location", "locations", "office", "offices"],
            "state": ["state", "states", "province", "provinces"],
            "customer": ["customer", "customers", "client", "buyer"],
        }

        target_dim = None
        # Pass 1: Direct column match
        for col in columns:
            col_l = col.lower()
            if col == date_col:
                continue
            if col_l in lower_q:
                target_dim = col
                break

        # Pass 2: Semantic keyword mapping
        if not target_dim:
            for base_key, synonyms in dim_keywords.items():
                if any(syn in lower_q for syn in synonyms):
                    for col in columns:
                        if col == date_col:
                            continue
                        col_l = col.lower()
                        if base_key in col_l or any(s in col_l for s in synonyms):
                            target_dim = col
                            break
                if target_dim:
                    break

        # If question is asking "which / what / list [dimension] are included"
        is_list_question = any(w in lower_q for w in ["which", "what", "list", "show all", "include", "present", "have", "tell me"])
        if target_dim and is_list_question and not any(w in lower_q for w in ["revenue", "sales", "profit", "margin", "cost"]):
            sql = f'SELECT "{target_dim}", COUNT(*) AS count FROM data GROUP BY "{target_dim}" ORDER BY count DESC LIMIT 15'
            return AnalyticalQueryPlan(
                thought_process=f"Identify and list all distinct {target_dim} segments in the dataset.",
                intent="list_distinct",
                target_metric="count",
                target_dimension=target_dim,
                sql_query=sql,
                recommended_chart_type="bar_chart",
            )

        if target_dim:
            sql = f'SELECT "{target_dim}", {metric_expr} AS {metric_name} FROM data GROUP BY "{target_dim}" ORDER BY {metric_name} DESC LIMIT {top_n}'
            return AnalyticalQueryPlan(
                thought_process=f"Group by {target_dim} and rank top {top_n} by {metric_name}.",
                intent="rank",
                target_metric=metric_name,
                target_dimension=target_dim,
                sql_query=sql,
                recommended_chart_type="bar_chart",
            )

        if category_col:
            sql = f'SELECT "{category_col}", {metric_expr} AS {metric_name} FROM data GROUP BY "{category_col}" ORDER BY {metric_name} DESC LIMIT {top_n}'
            return AnalyticalQueryPlan(
                thought_process=f"Group by primary category {category_col} and rank top {top_n} by {metric_name}.",
                intent="rank",
                target_metric=metric_name,
                target_dimension=category_col,
                sql_query=sql,
                recommended_chart_type="bar_chart",
            )

        # Fallback to general KPI summary
        sql = f"SELECT {metric_expr} AS {metric_name} FROM data"
        return AnalyticalQueryPlan(
            thought_process=f"Calculate overall aggregated {metric_name}.",
            intent="aggregate",
            target_metric=metric_name,
            target_dimension=None,
            sql_query=sql,
            recommended_chart_type="kpi_card",
        )

    @classmethod
    async def translate_question(
        cls,
        user_query: str,
        columns: List[str],
        column_types: Dict[str, str],
        semantic_model: SemanticModelSchema,
        available_metrics: List[MetricDefinition],
        sample_values: Optional[Dict[str, List[Any]]] = None,
        conversation_history: Optional[List[ChatMessage]] = None,
        provider: Optional[BaseLLMProvider] = None,
    ) -> AnalyticalQueryPlan:
        """
        Translates a natural-language query into a structured AnalyticalQueryPlan with executable DuckDB SQL.
        """
        return analyst_engine.build_plan(
            user_query=user_query,
            columns=columns,
            semantic_model=semantic_model,
            available_metrics=available_metrics,
            conversation_history=conversation_history,
            sample_values=sample_values,
        )

        # Legacy direct text-to-SQL path retained below during migration.
        llm = provider or get_llm_provider()

        schema_lines = []
        for col in columns:
            ctype = column_types.get(col, "VARCHAR")
            samples = sample_values.get(col, []) if sample_values else []
            samples_str = f", Examples: {samples[:3]}" if samples else ""
            schema_lines.append(f"- Column: '{col}' (Type: {ctype}{samples_str})")

        metrics_lines = []
        for m in available_metrics:
            metrics_lines.append(f"- Metric '{m.id}' ({m.label}): {m.sql_template}")

        history_lines = []
        if conversation_history:
            for msg in conversation_history[-4:]:
                history_lines.append(f"{msg.role.value.upper()}: {msg.content}")

        prompt = f"""
Dataset Table Name: 'data'
Columns in Dataset:
{chr(10).join(schema_lines)}

Calculable Business Metric Formulas:
{chr(10).join(metrics_lines)}

Domain: {semantic_model.domain}
Semantic Mappings: {semantic_model.mappings}

Available backend analytical capabilities:
- Metrics summary calculates only the registered KPIs listed above.
- Breakdown groups registered metrics by a valid dataset dimension.
- Time-series calculates trends and period-over-period growth when a date column exists.
- Geo-breakdown calculates geographic metric distribution when location data exists.
- Insights and anomalies calculate concentration, risk, and unusual changes.
Use only supplied metrics, columns, and values. Do not invent endpoint results or unsupported calculations.

Recent Conversation:
{chr(10).join(history_lines) if history_lines else "None"}

User Question: "{user_query}"

Generate a DuckDB SQL query to answer this business question accurately and deterministically.
"""

        system_prompt = """You are an elite Data Analyst and SQL Engineer for DuckDB.
Generate safe, optimal DuckDB SQL using ONLY the columns provided. The table name is always 'data'.
Choose the best recommended chart type ('kpi_card', 'bar_chart', 'line_chart', 'pie_chart', 'table', 'none').
Never use DROP, DELETE, INSERT, or ALTER. Output strictly valid JSON conforming to AnalyticalQueryPlan."""

        try:
            plan: AnalyticalQueryPlan = await llm.generate_structured(
                prompt=prompt,
                system_prompt=system_prompt,
                response_schema=AnalyticalQueryPlan,
            )
            if plan.sql_query and plan.sql_query.strip():
                return plan
        except Exception as exc:
            logger.warning("AI Text-to-SQL translation failed: %s. Using deterministic fallback.", exc)

        return cls.get_fallback_query_plan(
            user_query,
            columns,
            semantic_model,
            available_metrics,
            conversation_history=conversation_history,
        )


text_to_query_agent = TextToQueryAgent()
