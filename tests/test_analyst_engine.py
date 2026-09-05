from app.ai.analyst_engine import analyst_engine
from app.schemas.metrics import MetricDefinition
from app.schemas.semantic import SemanticModelSchema, BusinessConcept


def metric(metric_id: str, sql_template: str) -> MetricDefinition:
    return MetricDefinition(
        id=metric_id,
        name=metric_id,
        label=metric_id.replace("_", " ").title(),
        description="Test metric",
        sql_template=sql_template,
    )


def test_engine_compiles_registered_metric_by_dimension() -> None:
    semantic = SemanticModelSchema(
        dataset_id="ds_test",
        mappings={"category_column": "category"},
        dimensions=["category"],
    )
    plan = analyst_engine.build_plan(
        user_query="What are the top categories by profit margin?",
        columns=["category", "revenue", "profit"],
        semantic_model=semantic,
        available_metrics=[metric("profit_margin", "SUM(profit) / NULLIF(SUM(revenue), 0) * 100")],
    )

    assert plan.intent == "rank"
    assert plan.target_metric == "profit_margin"
    assert plan.target_dimension == "category"
    assert "SUM(profit)" in plan.sql_query
    assert "GROUP BY \"category\"" in plan.sql_query


def test_engine_lists_dimension_values_without_metric_intent() -> None:
    semantic = SemanticModelSchema(
        dataset_id="ds_test",
        mappings={"city_column": "city"},
        dimensions=["city"],
    )
    plan = analyst_engine.build_plan(
        user_query="Which cities are included?",
        columns=["city", "value"],
        semantic_model=semantic,
        available_metrics=[metric("total_records", "COUNT(*)")],
    )

    assert plan.intent == "list_distinct"
    assert plan.target_dimension == "city"
    assert "COUNT(*)" in plan.sql_query


def test_engine_compiles_value_comparison_from_profile_samples() -> None:
    semantic = SemanticModelSchema(
        dataset_id="ds_test",
        mappings={"country_column": "country"},
        dimensions=["country"],
    )
    plan = analyst_engine.build_plan(
        user_query="Compare USA and Canada revenue",
        columns=["country", "revenue"],
        semantic_model=semantic,
        available_metrics=[metric("total_revenue", "SUM(revenue)")],
        sample_values={"country": ["USA", "Canada"]},
    )

    assert plan.intent == "compare"
    assert plan.target_dimension == "country"
    assert '"country" IN (\'Canada\', \'USA\')' in plan.sql_query


# ---------------------------------------------------------------------------
# Regression: HR dataset dimension detection
# ---------------------------------------------------------------------------


def _hr_semantic() -> SemanticModelSchema:
    """Build a representative HR semantic model covering the column list from
    the user's screenshot."""
    return SemanticModelSchema(
        dataset_id="ds_hr",
        domain="human_resources",
        dataset_type="hr_workforce",
        mappings={
            BusinessConcept.EMPLOYEE_ID: "EmployeeID",
            BusinessConcept.DEPARTMENT: "Department",
            BusinessConcept.JOB_TITLE: "JobTitle",
            BusinessConcept.HIRE_DATE: "HireDate",
            BusinessConcept.SALARY: "AnnualSalaryUSD",
            BusinessConcept.EDUCATION: "EducationLevel",
            BusinessConcept.PERFORMANCE_RATING: "PerformanceRating",
            BusinessConcept.STATUS: "EmploymentStatus",
        },
        dimensions=[
            "Department", "JobTitle", "EmploymentStatus", "EducationLevel",
            "Country", "City", "WorkMode", "MaritalStatus", "SalaryBand",
        ],
        measures=["Age", "TenureYears", "TotalExperienceYears", "AnnualSalaryUSD", "PerformanceRating"],
        time_dimensions=["DateOfBirth", "HireDate", "ExitDate"],
        identifiers=["EmployeeID", "Email"],
    )


def _hr_columns() -> list[str]:
    return [
        "EmployeeID", "FullName", "Gender", "DateOfBirth", "Age", "Department",
        "JobTitle", "HireDate", "ExitDate", "EmploymentStatus", "TenureYears",
        "TotalExperienceYears", "EducationLevel", "AnnualSalaryUSD", "SalaryBand",
        "PerformanceRating", "Country", "City", "WorkMode", "MaritalStatus",
        "Email", "HireYear", "IsActive",
    ]


def _hr_metrics() -> list[MetricDefinition]:
    return [
        metric("total_employees", "COUNT(*)"),
        metric("average_salary", "AVG(\"AnnualSalaryUSD\")"),
        metric("avg_performance_rating", "AVG(\"PerformanceRating\")"),
    ]


def test_engine_detects_education_dimension_via_concept_mapping() -> None:
    """Regression for the screenshot bug: 'Highest completed education of the
    employees?' should group by EducationLevel, not return a single count."""
    plan = analyst_engine.build_plan(
        user_query="Highest completed education of the employees?",
        columns=_hr_columns(),
        semantic_model=_hr_semantic(),
        available_metrics=_hr_metrics(),
    )
    assert plan.intent == "rank"
    assert plan.target_dimension == "EducationLevel"
    assert "GROUP BY \"EducationLevel\"" in plan.sql_query
    assert "ORDER BY total_employees DESC" in plan.sql_query


def test_engine_detects_education_dimension_via_column_token_matching() -> None:
    """Even WITHOUT the EDUCATION concept mapping, the column name 'EducationLevel'
    should still be detected because 'education' is a token of the column name."""
    semantic = SemanticModelSchema(
        dataset_id="ds_hr_unmapped",
        domain="human_resources",
        dataset_type="hr_workforce",
        mappings={},  # No concept mapping for education
        dimensions=["EducationLevel", "Department"],
    )
    plan = analyst_engine.build_plan(
        user_query="What is the highest education level?",
        columns=["EmployeeID", "EducationLevel", "Department"],
        semantic_model=semantic,
        available_metrics=[metric("total_employees", "COUNT(*)")],
    )
    assert plan.target_dimension == "EducationLevel"


def test_engine_routes_top_n_to_breakdown_by_dim() -> None:
    """'Top 5 departments by salary' must group by Department and rank by salary."""
    plan = analyst_engine.build_plan(
        user_query="Top 5 departments by salary",
        columns=_hr_columns(),
        semantic_model=_hr_semantic(),
        available_metrics=_hr_metrics(),
    )
    assert plan.intent in ("rank", "breakdown")
    assert plan.target_dimension == "Department"
    assert plan.target_metric == "average_salary"
    assert "LIMIT 5" in plan.sql_query
    assert "ORDER BY average_salary DESC" in plan.sql_query


def test_engine_handles_camelcase_column_token_matching() -> None:
    """AnnualSalaryUSD column should be detected when user says 'salary'."""
    plan = analyst_engine.build_plan(
        user_query="Average salary by department",
        columns=_hr_columns(),
        semantic_model=_hr_semantic(),
        available_metrics=_hr_metrics(),
    )
    assert plan.target_metric == "average_salary"
    assert plan.target_dimension == "Department"
    assert "AVG(\"AnnualSalaryUSD\")" in plan.sql_query


def test_engine_detects_performance_rating() -> None:
    plan = analyst_engine.build_plan(
        user_query="Average performance by department",
        columns=_hr_columns(),
        semantic_model=_hr_semantic(),
        available_metrics=_hr_metrics(),
    )
    assert plan.target_metric == "avg_performance_rating"
    assert plan.target_dimension == "Department"


def test_engine_detects_gender_when_mapped() -> None:
    semantic = _hr_semantic()
    semantic.mappings[BusinessConcept.GENDER] = "Gender"
    semantic.dimensions.insert(0, "Gender")
    plan = analyst_engine.build_plan(
        user_query="How many employees by gender?",
        columns=_hr_columns(),
        semantic_model=semantic,
        available_metrics=_hr_metrics(),
    )
    assert plan.target_dimension == "Gender"
    assert "GROUP BY \"Gender\"" in plan.sql_query


def test_engine_falls_back_to_count_when_no_dimension_detected() -> None:
    """If the user asks a pure aggregate question with no dimension keyword,
    the engine should still return the metric (not break)."""
    plan = analyst_engine.build_plan(
        user_query="How many employees do we have?",
        columns=_hr_columns(),
        semantic_model=_hr_semantic(),
        available_metrics=_hr_metrics(),
    )
    # No dimension detected → aggregate intent
    assert plan.intent == "aggregate"
    assert plan.target_metric == "total_employees"

