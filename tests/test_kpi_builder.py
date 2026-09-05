import io
import pytest
from httpx import AsyncClient

from app.schemas.dashboard import WidgetType
from app.schemas.kpi_builder import (
    CustomKpiSpec,
    KpiAggregationType,
    KpiCondition,
    KpiFormatType,
)


@pytest.mark.asyncio
async def test_kpi_builder_flight_dataset(client: AsyncClient) -> None:
    """
    Test Self-Service KPI Builder on airline flights dataset:
    - Average of continuous column (DelayMinutes)
    - Rate of boolean column (IsDelayed == True)
    - Group by categorical dimension (Airline) -> Bar chart recommendation
    - Preview API endpoint
    - Adding custom widget to dashboard and verifying persistence
    - Removing widget from dashboard
    """
    flight_csv = (
        b"FlightNumber,Airline,Route,DelayMinutes,IsDelayed,IsCancelled,Passengers,Capacity,LoadFactor,Month\n"
        b"AA100,American,JFK-LAX,15.0,true,false,150,180,0.83,Jan\n"
        b"AA101,American,JFK-LAX,0.0,false,false,170,180,0.94,Jan\n"
        b"DL200,Delta,ATL-ORD,45.0,true,false,190,200,0.95,Jan\n"
        b"DL201,Delta,ATL-ORD,30.0,true,false,180,200,0.90,Feb\n"
        b"UA300,United,SFO-DEN,0.0,false,false,120,150,0.80,Feb\n"
        b"UA301,United,SFO-DEN,10.0,true,false,140,150,0.93,Feb\n"
    )

    files = {"file": ("airline_flights_dataset.csv", io.BytesIO(flight_csv), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Preview Average Delay Minutes (Scalar KPI card)
    avg_delay_spec = {
        "label": "Average Delay Minutes",
        "column": "DelayMinutes",
        "aggregation": "avg",
        "output_type": "auto",
        "format_type": "duration",
        "unit": "min",
    }
    preview_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/dashboards/kpis/preview",
        json=avg_delay_spec,
    )
    assert preview_res.status_code == 200, f"Error: {preview_res.json()}"
    p_data = preview_res.json()
    assert p_data["resolved_widget_type"] == WidgetType.KPI_CARD.value
    # Avg delay of (15 + 0 + 45 + 30 + 0 + 10) / 6 = 100 / 6 = 16.67
    assert abs(p_data["scalar_value"] - 16.67) < 0.1
    assert "min" in p_data["formatted_value"]

    # 2. Preview Delay Rate by Airline (Grouped Bar chart)
    delay_rate_spec = {
        "label": "Flight Delay Rate by Airline",
        "column": "IsDelayed",
        "aggregation": "rate",
        "condition": {"operator": "==", "value": True},
        "dimension": "Airline",
        "output_type": "auto",
        "format_type": "percentage",
    }
    rate_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/dashboards/kpis/preview",
        json=delay_rate_spec,
    )
    assert rate_res.status_code == 200
    r_data = rate_res.json()
    # 3 airlines -> distinct_count <= 5 -> PIE_CHART or BAR_CHART
    assert r_data["resolved_widget_type"] in (WidgetType.PIE_CHART.value, WidgetType.BAR_CHART.value)
    assert r_data["rows"] is not None
    assert len(r_data["rows"]) == 3
    # Delta: 2 out of 2 delayed = 100%
    delta_row = next(r for r in r_data["rows"] if r["dimension_value"] == "Delta")
    assert delta_row["metric_value"] == 100.0

    # 3. Add Custom Widget to the Default Dashboard
    dash_res = await client.get(f"/api/v1/datasets/{dataset_id}/dashboards/default")
    assert dash_res.status_code == 200
    dash_id = dash_res.json()["spec"]["id"]
    initial_widget_count = len(dash_res.json()["spec"]["widgets"])

    add_res = await client.post(
        f"/api/v1/dashboards/{dash_id}/widgets",
        json=delay_rate_spec,
    )
    assert add_res.status_code == 201
    updated_dash = add_res.json()
    assert len(updated_dash["spec"]["widgets"]) == initial_widget_count + 1

    # Check that new widget exists and is hydrated with live data
    new_widget = updated_dash["spec"]["widgets"][-1]
    assert new_widget["title"] == "Flight Delay Rate by Airline"
    assert new_widget["id"] in updated_dash["data"]
    assert "rows" in updated_dash["data"][new_widget["id"]]

    # 4. Remove the Widget
    del_res = await client.delete(f"/api/v1/dashboards/{dash_id}/widgets/{new_widget['id']}")
    assert del_res.status_code == 200
    final_dash = del_res.json()
    assert len(final_dash["spec"]["widgets"]) == initial_widget_count
