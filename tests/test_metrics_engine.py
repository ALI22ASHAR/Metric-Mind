import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_available_and_summary_calculation(client: AsyncClient) -> None:
    """
    Test Phase 6: Deterministic KPI Engine capability analysis and exact metric calculations.
    """
    # 2 Laptops @ $1200 ($800 cp) = $2400 rev, $1600 cost, $800 profit
    # 5 Mice @ $25 ($10 cp)       = $125 rev, $50 cost, $75 profit
    # 1 Desk @ $450 ($200 cp)     = $450 rev, $200 cost, $250 profit
    # Totals: Revenue = $2,975.00, Cost = $1,850.00, Profit = $1,125.00, Margin = 37.82%, Units = 8, Orders = 3, AOV = $991.67
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,2,1200.0,800.0,Chicago,USA\n"
        b"1002,2024-01-16,Mouse,Electronics,5,25.0,10.0,New York,USA\n"
        b"1003,2024-01-17,Desk,Furniture,1,450.0,200.0,Dallas,USA\n"
    )

    files = {"file": ("sales_kpi.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Fetch available metrics
    avail_res = await client.get(f"/api/v1/datasets/{dataset_id}/metrics/available")
    assert avail_res.status_code == 200
    avail_data = avail_res.json()
    metric_ids = [m["id"] for m in avail_data]
    assert "total_revenue" in metric_ids
    assert "total_cost" in metric_ids
    assert "total_profit" in metric_ids
    assert "profit_margin" in metric_ids
    assert "units_sold" in metric_ids
    assert "total_orders" in metric_ids
    assert "average_order_value" in metric_ids

    # 2. Fetch computed KPI summary
    summary_res = await client.get(f"/api/v1/datasets/{dataset_id}/metrics/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    metrics = summary["metrics"]

    assert metrics["total_revenue"]["value"] == 2975.0
    assert metrics["total_revenue"]["formatted_value"] == "$2,975.00"

    assert metrics["total_cost"]["value"] == 1850.0
    assert metrics["total_cost"]["formatted_value"] == "$1,850.00"

    assert metrics["total_profit"]["value"] == 1125.0
    assert metrics["total_profit"]["formatted_value"] == "$1,125.00"

    assert round(metrics["profit_margin"]["value"], 2) == 37.82
    assert "37.82%" in metrics["profit_margin"]["formatted_value"]

    assert metrics["units_sold"]["value"] == 8.0
    assert metrics["total_orders"]["value"] == 3.0
    assert round(metrics["average_order_value"]["value"], 2) == 991.67
