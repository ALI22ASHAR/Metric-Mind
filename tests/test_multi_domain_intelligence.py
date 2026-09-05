import io
import pytest
from httpx import AsyncClient

from app.ai.dashboard_planner import ai_dashboard_planner
from app.analytics.metric_registry import metric_capability_analyzer
from app.analytics.semantic_heuristics import semantic_model_builder
from app.schemas.profile import ColumnProfile, ColumnRole, ColumnType
from app.ai.report_generator import executive_report_generator


def test_hr_semantic_domain_detection():
    columns_info = [
        ColumnProfile(name="Employee_ID", detected_type=ColumnType.CATEGORICAL, role=ColumnRole.ID, null_count=0, unique_count=100, sample_values=["E001", "E002"]),
        ColumnProfile(name="Department", detected_type=ColumnType.CATEGORICAL, role=ColumnRole.DIMENSION, null_count=0, unique_count=8, sample_values=["Engineering", "Sales"]),
        ColumnProfile(name="Job_Title", detected_type=ColumnType.CATEGORICAL, role=ColumnRole.DIMENSION, null_count=0, unique_count=15, sample_values=["Software Engineer", "Account Exec"]),
        ColumnProfile(name="Hire_Date", detected_type=ColumnType.DATE, role=ColumnRole.TIME_DIMENSION, null_count=0, unique_count=90, sample_values=["2020-01-15", "2021-03-20"]),
        ColumnProfile(name="Annual_Salary", detected_type=ColumnType.NUMERIC, role=ColumnRole.MEASURE, null_count=0, unique_count=50, sample_values=[95000, 120000]),
        ColumnProfile(name="City", detected_type=ColumnType.CATEGORICAL, role=ColumnRole.DIMENSION, null_count=0, unique_count=5, sample_values=["New York", "San Francisco"]),
    ]

    semantic = semantic_model_builder.build_semantic_model("ds_hr_test", columns_info)
    assert semantic.domain == "human_resources"
    assert semantic.dataset_type == "hr_workforce"
    assert "department_column" in semantic.mappings
    assert "hire_date_column" in semantic.mappings

    # Test Metric Capability
    metrics = metric_capability_analyzer.get_computable_metrics(semantic)
    metric_ids = [m.id for m in metrics]
    assert "total_employees" in metric_ids
    assert "active_departments" in metric_ids
    assert "average_salary" in metric_ids

    # Test Dashboard Planning
    spec = ai_dashboard_planner.plan_dashboard("ds_hr_test", semantic, metrics)
    assert "Human Resources" in spec.title or "Workforce" in spec.title
    # Verify at least 3-4 KPI cards generated
    kpi_widgets = [w for w in spec.widgets if w.type.value == "kpi_card"]
    assert len(kpi_widgets) >= 3

    report = executive_report_generator.generate_report(
        dataset_id="ds_hr_test",
        domain="human_resources",
        quality_report=None,
        semantic_model=semantic,
        kpi_results={"total_employees": {"name": "total_employees", "label": "Total Headcount", "formatted_value": "100"}},
        insights_summary=None,
        anomalies_summary=None,
        ai_understanding=None,
    )
    assert report.title == "Executive Intelligence Brief: Human Resources Performance Report"
    assert "**Total Headcount**: 100" in report.markdown_content
    top_metric_ids = {metric for widget in kpi_widgets for metric in widget.metrics}
    detail_tables = [w for w in spec.widgets if w.type.value == "table"]
    assert detail_tables
    assert top_metric_ids.isdisjoint(set(detail_tables[0].metrics))


@pytest.mark.asyncio
async def test_hr_dataset_upload_end_to_end(client: AsyncClient):
    hr_csv = (
        b"Employee_ID,Employee_Name,Department,Job_Title,Hire_Date,Salary,Age,City\n"
        b"E101,Ada Stone,Engineering,Software Engineer,2018-05-12,125000,31,San Francisco\n"
        b"E102,Sam Lee,Engineering,Engineering Manager,2017-03-01,165000,42,San Francisco\n"
        b"E103,Jordan Cole,Sales,Account Executive,2019-11-20,95000,29,New York\n"
        b"E104,Alex Morgan,Customer Support,Support Specialist,2021-08-15,65000,36,Austin\n"
        b"E105,Riley Chen,Marketing,Growth Marketer,2020-02-10,105000,27,New York\n"
    )
    files = {"file": ("hr_employees_dataset.csv", io.BytesIO(hr_csv), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # Retrieve Default Dashboard
    dash_res = await client.get(f"/api/v1/datasets/{dataset_id}/dashboards/default")
    assert dash_res.status_code == 200
    dash_json = dash_res.json()
    spec = dash_json["spec"]

    assert "Human Resources" in spec["title"] or "Workforce" in spec["title"]
    kpi_widgets = [w for w in spec["widgets"] if w["type"] == "kpi_card"]
    assert len(kpi_widgets) >= 3
    assert {widget["metric_id"] for widget in kpi_widgets[:4]} == {
        "total_employees", "active_departments", "average_age", "workforce_locations"
    }
    filter_columns = {dashboard_filter["column"] for dashboard_filter in spec["filters"]}
    assert {"Department", "Job_Title", "City"}.issubset(filter_columns)

    # Check that KPI values are computed correctly
    data = dash_json["data"]
    total_emp_widget = [w for w in kpi_widgets if "total_employees" in w["metrics"]][0]
    emp_val = data[total_emp_widget["id"]]["value"]
    assert emp_val == 5
    assert data[total_emp_widget["id"]]["formatted_value"] == "5"

    # Regression: a time-series trend widget must be present and must use
    # the HireDate (not Order_Date which doesn't exist on HR datasets).
    line_widgets = [w for w in spec["widgets"] if w["type"] == "line_chart"]
    assert len(line_widgets) >= 1, "HR dashboard must include a workforce trend line chart"
    trend = line_widgets[0]
    # The trend must use hires_over_time so the line actually shows hiring velocity.
    assert "hires_over_time" in trend["metrics"], (
        f"HR trend should use hires_over_time, got {trend['metrics']}"
    )
    trend_filters = trend["options"]["filter_dimensions"]
    assert {filter["label"] for filter in trend_filters} >= {"Department", "Job Title"}
    assert all(filter["column"] not in {"Category", "Product", "Country"} for filter in trend_filters)
    # And the chart must have actually rendered with data points.
    trend_data = data.get(trend["id"], {})
    assert len(trend_data.get("points", [])) >= 1, "HR trend must have at least 1 data point"

    breakdown_res = await client.get(
        f"/api/v1/datasets/{dataset_id}/analytics/kpi-breakdown?metric=total_employees"
    )
    assert breakdown_res.status_code == 200
    breakdowns = breakdown_res.json()["breakdowns"]
    employee_name_dim = next(key for key in breakdowns if key.lower() == "employee_name")
    assert breakdowns[employee_name_dim][0]["formatted_value"] == "1"
    assert "$" not in breakdowns[employee_name_dim][0]["formatted_value"]
