import re
from typing import List, Optional

from app.schemas.chat import AnalyticalQueryPlan, ChatMessage
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import BusinessConcept, SemanticModelSchema


def _column_tokens(column_name: str) -> List[str]:
    """
    Split a CamelCase / snake_case column name into lowercase word tokens.
    Used to match natural-language question fragments like "education" to
    "EducationLevel", "salary" to "AnnualSalaryUSD", "performance" to
    "PerformanceRating", etc.
    """
    s = column_name.replace("_", " ").replace("-", " ")
    # Insert spaces before uppercase letters (CamelCase → Camel Case)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return [t.lower() for t in s.split() if t]


def _column_matches_question(column_name: str, question: str) -> bool:
    """
    True if any meaningful word token from `column_name` appears in `question`
    as a whole word. Skips generic stopwords like 'id', 'name', 'code', etc.
    """
    stopwords = {
        "id", "name", "code", "key", "date", "no", "num", "type",
        "value", "values", "field", "total",
    }
    for token in _column_tokens(column_name):
        if len(token) < 3 or token in stopwords:
            continue
        if re.search(rf"\b{re.escape(token)}\b", question):
            return True
        # Handle simple plural: "categories" → "category"
        if re.search(rf"\b{re.escape(token)}s?\b", question):
            return True
    return False


class AnalystEngine:
    """Deterministic intent parser and SQL compiler for the AI Analyst."""

    METRIC_ALIASES = {
        "total_revenue": ("revenue", "sales", "selling", "amount", "money"),
        "total_profit": ("profit", "earnings"),
        "profit_margin": ("margin", "profitability"),
        "total_cost": ("cost", "cogs", "expense"),
        "units_sold": ("units", "quantity", "volume", "sold"),
        "total_orders": ("orders", "transactions", "records", "count"),
        "average_order_value": ("average order", "aov", "order value"),
        "discount_rate": ("discount rate", "discount percentage"),
        "total_mrr": ("mrr", "recurring revenue", "arr"),
        "churn_rate": ("churn", "cancelled", "cancellation"),
        "total_employees": ("employees", "headcount", "workforce", "staff"),
        "average_salary": ("salary", "salaries", "compensation", "pay"),
        "total_shipments": ("shipments", "deliveries", "packages"),
        "average_weight": ("weight", "heavy", "light"),
        "total_patients": ("patients", "patient count"),
        "active_diagnoses": ("diagnoses", "diagnosis", "conditions"),
        "active_employees": ("active employees", "active staff"),
        "turnover_rate": ("turnover", "attrition", "exits"),
        "avg_performance_rating": ("performance rating", "performance score", "rating", "performance", "average performance"),
        "hires_over_time": ("hires", "hiring", "new hires"),
        "hire_rate": ("hire rate", "hiring rate"),
    }

    DIMENSION_ALIASES = {
        "department": ("department", "departments", "dept", "depts", "team", "teams", "division", "divisions", "unit", "units"),
        "job_title": ("job title", "job titles", "title", "titles", "role", "roles", "position", "positions", "job", "jobs", "occupation"),
        "category": ("category", "categories", "segment", "segments", "type", "types", "group"),
        "product": ("product", "products", "item", "items", "sku", "skus", "goods", "merchandise"),
        "city": ("city", "cities", "town", "location", "locations", "office", "offices"),
        "state": ("state", "states", "province", "provinces"),
        "country": ("country", "countries", "nation", "nations", "geography", "market"),
        "region": ("region", "regions", "territory", "territories", "area"),
        "customer": ("customer", "customers", "client", "clients", "buyer"),
        "carrier": ("carrier", "carriers", "courier", "delivery method"),
        "plan": ("plan", "plans", "tier", "tiers", "subscription"),
        "diagnosis": ("diagnosis", "diagnoses", "condition", "conditions"),
        "education": ("education", "qualification", "qualifications", "degree", "degrees", "completed education", "education level", "educationlevel"),
        "status": ("status", "employment status", "active status"),
        "gender": ("gender", "sex"),
        "work_mode": ("work mode", "workmode", "remote", "on-site", "hybrid"),
        "marital_status": ("marital", "marital status", "married"),
        "salary_band": ("salary band", "salaryband", "band", "pay band"),
        "performance_rating": ("performance rating", "performance", "rating", "ratings", "performance score"),
    }

    # Concepts whose mapped columns are always fair-game for dimension detection
    # — broader list than before so HR / SaaS / logistics columns are detected.
    _DIMENSION_CONCEPTS = (
        BusinessConcept.CITY, BusinessConcept.REGION, BusinessConcept.COUNTRY,
        BusinessConcept.STATE, BusinessConcept.DEPARTMENT, BusinessConcept.JOB_TITLE,
        BusinessConcept.CATEGORY, BusinessConcept.PRODUCT, BusinessConcept.CUSTOMER,
        BusinessConcept.EDUCATION, BusinessConcept.STATUS, BusinessConcept.GENDER,
        BusinessConcept.PERFORMANCE_RATING,
    )

    @classmethod
    def _metric(cls, question: str, available_metrics: List[MetricDefinition]) -> Optional[MetricDefinition]:
        available = {metric.id: metric for metric in available_metrics}
        for metric_id, aliases in cls.METRIC_ALIASES.items():
            if metric_id in available and any(alias in question for alias in aliases):
                return available[metric_id]
        return available.get("total_records") or (available_metrics[0] if available_metrics else None)

    @classmethod
    def _dimension(
        cls,
        question: str,
        columns: List[str],
        semantic_model: SemanticModelSchema,
        date_column: Optional[str],
        sample_values: Optional[dict[str, List[object]]] = None,
    ) -> Optional[str]:
        measure_columns = set(semantic_model.measures or [])
        # Identifier columns (e.g. EmployeeID, Email) should not be auto-picked
        # as grouping dimensions. "How many employees" mentions "employees" but
        # we don't want to group by EmployeeID — that's an aggregate question.
        identifier_columns = set(semantic_model.identifiers or [])
        # Columns that already appear in the concept-mapping step (employee_id,
        # customer_id, order_id…) likewise shouldn't be auto-picked from raw
        # column tokens: their presence in the question usually signals the
        # metric, not the dimension.
        concept_mapped_columns = set((semantic_model.mappings or {}).values())

        def _eligible_as_dimension(candidate: str) -> bool:
            return (
                candidate not in measure_columns
                and candidate not in identifier_columns
                and candidate not in concept_mapped_columns
                and candidate != date_column
            )

        # Pass 0: If the user mentions a literal sample value (e.g. "Engineering"),
        # that strongly implies the column is the dimension.
        for column, values in (sample_values or {}).items():
            if column != date_column and any(
                re.search(rf"\b{re.escape(str(value).lower())}\b", question)
                for value in values
                if value is not None
            ):
                return column

        # Pass 1: semantic concept → mapped column, matched by alias vocabulary.
        for concept in cls._DIMENSION_CONCEPTS:
            mapped = semantic_model.mappings.get(concept)
            if not mapped or mapped == date_column:
                continue
            aliases = cls.DIMENSION_ALIASES.get(concept.replace("_column", ""), ())
            if any(alias in question for alias in aliases):
                return mapped

        # Pass 2: Match by column name tokens against question.
        # Walks both semantic_model.dimensions AND the full column list, so even
        # an unmapped column (e.g. "EducationLevel" without concept mapping) can
        # still be detected as a dimension.
        dimension_candidates: List[str] = []
        seen = set()
        for candidate in list(semantic_model.dimensions or []) + list(columns):
            if candidate in seen or not _eligible_as_dimension(candidate):
                continue
            seen.add(candidate)
            if _column_matches_question(candidate, question):
                dimension_candidates.append(candidate)
        if dimension_candidates:
            return dimension_candidates[0]

        # Pass 3: alias-keyword fallback — if the question contains an alias
        # like "department", find any column whose name contains that alias.
        for key, aliases in cls.DIMENSION_ALIASES.items():
            if any(alias in question for alias in aliases):
                for column in columns:
                    if not _eligible_as_dimension(column):
                        continue
                    if key in column.lower() or any(alias in column.lower() for alias in aliases):
                        return column
        return None

    @classmethod
    def build_plan(
        cls,
        user_query: str,
        columns: List[str],
        semantic_model: SemanticModelSchema,
        available_metrics: List[MetricDefinition],
        conversation_history: Optional[List[ChatMessage]] = None,
        sample_values: Optional[dict[str, List[object]]] = None,
    ) -> AnalyticalQueryPlan:
        question = user_query.lower().strip()
        history = " ".join(message.content.lower() for message in (conversation_history or [])[-4:])
        search_text = f"{question} {history}"
        date_column = semantic_model.date_column or (semantic_model.time_dimensions[0] if semantic_model.time_dimensions else None)
        metric_words_present = any(
            alias in search_text
            for aliases in cls.METRIC_ALIASES.values()
            for alias in aliases
        )
        metric = cls._metric(search_text, available_metrics)
        metric_id = metric.id if metric else "total_records"
        metric_sql = metric.sql_template if metric else "COUNT(*)"
        dimension = cls._dimension(question, columns, semantic_model, date_column, sample_values)
        asks_for_list = any(word in question for word in ("which", "what", "list", "show all", "include"))
        asks_for_trend = date_column and any(word in question for word in ("trend", "over time", "monthly", "month", "weekly", "quarter", "daily", "growth"))
        asks_for_ranking = any(word in question for word in ("top", "highest", "best", "lowest", "worst", "leading", "rank"))
        filters = cls._value_filters(question, columns, semantic_model, sample_values or {})
        where_clause = cls._where_clause(filters)
        comparison = any(word in question for word in ("compare", "versus", " vs ", "against"))

        if asks_for_trend:
            sql = f"SELECT strftime(\"{date_column}\", '%Y-%m') AS month, {metric_sql} AS {metric_id} FROM data {where_clause} GROUP BY 1 ORDER BY 1 ASC"
            return AnalyticalQueryPlan(
                thought_process=f"Aggregate registered metric {metric_id} by month using {date_column}.",
                intent="trend", target_metric=metric_id, target_dimension=date_column,
                sql_query=sql, recommended_chart_type="line_chart",
            )
        if dimension and asks_for_list and not metric_words_present:
            sql = f'SELECT "{dimension}", COUNT(*) AS count FROM data {where_clause} GROUP BY "{dimension}" ORDER BY count DESC LIMIT 15'
            return AnalyticalQueryPlan(
                thought_process=f"List distinct values for {dimension}.", intent="list_distinct",
                target_metric=None, target_dimension=dimension, sql_query=sql,
                recommended_chart_type="bar_chart",
            )
        if dimension:
            limit_match = re.search(r"\btop\s+(\d+)\b", question)
            limit = min(int(limit_match.group(1)), 100) if limit_match else 5
            sql = f'SELECT "{dimension}", {metric_sql} AS {metric_id} FROM data {where_clause} GROUP BY "{dimension}" ORDER BY {metric_id} DESC LIMIT {limit}'
            return AnalyticalQueryPlan(
                thought_process=f"Group registered metric {metric_id} by {dimension} and rank the largest results.",
                intent="compare" if comparison else ("rank" if asks_for_ranking or dimension else "breakdown"),
                target_metric=metric_id, target_dimension=dimension, sql_query=sql,
                recommended_chart_type="bar_chart",
            )
        sql = f"SELECT {metric_sql} AS {metric_id} FROM data {where_clause}"
        return AnalyticalQueryPlan(
            thought_process=f"Calculate registered metric {metric_id} across the dataset.",
            intent="aggregate", target_metric=metric_id, target_dimension=None,
            sql_query=sql, recommended_chart_type="kpi_card",
        )

    @classmethod
    def _value_filters(cls, question: str, columns: List[str], semantic_model: SemanticModelSchema, sample_values: dict[str, List[object]]) -> List[tuple[str, str]]:
        filters: List[tuple[str, str]] = []
        candidate_columns = set(semantic_model.dimensions or []) | set(columns)
        for column in candidate_columns:
            if column in (semantic_model.measures or []) or column == semantic_model.date_column:
                continue
            values = sorted({str(value) for value in sample_values.get(column, []) if value is not None}, key=len, reverse=True)
            matches = [value for value in values if re.search(rf"\b{re.escape(value.lower())}\b", question)]
            filters.extend((column, value) for value in matches[:5])
        return filters

    @staticmethod
    def _where_clause(filters: List[tuple[str, str]]) -> str:
        grouped: dict[str, List[str]] = {}
        for column, value in filters:
            grouped.setdefault(column, []).append(value.replace("'", "''"))
        if not grouped:
            return ""
        return "WHERE " + " AND ".join(
            f'"{column}" IN ({", ".join(repr(value) for value in values)})'
            for column, values in grouped.items()
        )


analyst_engine = AnalystEngine()
