import io
import pytest
from httpx import AsyncClient

from app.schemas.dashboard import WidgetType


@pytest.mark.asyncio
async def test_ai_dashboard_generation_on_upload(client: AsyncClient) -> None:
    """
    Test Phases 9, 10, 11, 12: Automatic AI Dashboard planning, persistence,
    and sub-second live data hydration across all widget types upon upload.
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,2,1200.0,800.0,Chicago,USA\n"
        b"1002,2024-01-16,Mouse,Electronics,5,25.0,10.0,New York,USA\n"
        b"1003,2024-02-17,Desk,Furniture,1,450.0,200.0,Dallas,USA\n"
    )

    files = {"file": ("sales_dashboard.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Fetch default generated dashboard
    res = await client.get(f"/api/v1/datasets/{dataset_id}/dashboards/default")
    assert res.status_code == 200
    dashboard = res.json()

    spec = dashboard["spec"]
    data = dashboard["data"]

    assert spec["dataset_id"] == dataset_id
    assert len(spec["widgets"]) >= 6
    assert len(spec["filters"]) >= 1

    # Verify widget types
    widget_types = [w["type"] for w in spec["widgets"]]
    assert WidgetType.KPI_CARD.value in widget_types
    assert WidgetType.LINE_CHART.value in widget_types
    assert WidgetType.BAR_CHART.value in widget_types
    assert WidgetType.PIE_CHART.value in widget_types
    assert WidgetType.TABLE.value in widget_types

    # 2. Verify Live Hydrated Data
    for widget in spec["widgets"]:
        w_id = widget["id"]
        w_type = widget["type"]
        assert w_id in data, f"Widget '{w_id}' missing hydrated data"
        w_data = data[w_id]

        if w_type == WidgetType.KPI_CARD.value:
            assert "value" in w_data
            assert "formatted_value" in w_data
            assert w_data["value"] is not None

        elif w_type == WidgetType.LINE_CHART.value:
            assert "points" in w_data
            assert len(w_data["points"]) >= 1
            assert "period_start" in w_data["points"][0]

        elif w_type == WidgetType.BAR_CHART.value:
            assert "rows" in w_data
            assert len(w_data["rows"]) >= 1
            assert "dimension_value" in w_data["rows"][0]

        elif w_type == WidgetType.PIE_CHART.value:
            assert "rows" in w_data
            assert len(w_data["rows"]) >= 1

        elif w_type == WidgetType.TABLE.value:
            assert "rows" in w_data
            assert len(w_data["rows"]) >= 1


@pytest.mark.asyncio
async def test_dashboard_crud_endpoints(client: AsyncClient) -> None:
    """
    Test generating custom dashboards, fetching by ID, updating theme/title, and deleting.
    """
    csv_content = b"id,item,val\n1,Apples,10\n2,Oranges,20"
    files = {"file": ("simple_dash.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Generate custom dashboard
    gen_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/dashboards/generate",
        json={"title": "Custom Grocery Dashboard", "theme": "dark"},
    )
    assert gen_res.status_code == 201
    custom_dash = gen_res.json()
    dash_id = custom_dash["spec"]["id"]
    assert custom_dash["spec"]["title"] == "Custom Grocery Dashboard"

    # 2. Get dashboard by ID
    get_res = await client.get(f"/api/v1/dashboards/{dash_id}")
    assert get_res.status_code == 200
    assert get_res.json()["spec"]["id"] == dash_id

    # 3. Update dashboard
    put_res = await client.put(
        f"/api/v1/dashboards/{dash_id}",
        json={"title": "Updated Dashboard Title", "theme": "light"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["spec"]["title"] == "Updated Dashboard Title"
    assert put_res.json()["spec"]["theme"] == "light"

    # 4. Delete dashboard
    del_res = await client.delete(f"/api/v1/dashboards/{dash_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 5. Confirm 404 after deletion
    get_after_del = await client.get(f"/api/v1/dashboards/{dash_id}")
    assert get_after_del.status_code == 404
