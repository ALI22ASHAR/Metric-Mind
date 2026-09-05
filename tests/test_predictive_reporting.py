import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_forecasting_and_scenarios(client: AsyncClient) -> None:
    """
    Test Phase 26 (Forecasting) & Phase 27 (Scenario Simulation).
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City\n"
        b"1,2024-01-01,Laptop,Electronics,2,1000.0,600.0,New York\n"
        b"2,2024-02-01,Laptop,Electronics,3,1000.0,600.0,New York\n"
        b"3,2024-03-01,Laptop,Electronics,4,1000.0,600.0,New York\n"
    )

    files = {"file": ("forecast_sales.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Test Forecasting (Phase 26)
    fc_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/forecast",
        json={"metric": "total_revenue", "periods_ahead": 3},
    )
    assert fc_res.status_code == 200
    fc_data = fc_res.json()
    assert len(fc_data["forecast"]) == 3
    assert fc_data["forecast"][0]["predicted_value"] > 0
    assert fc_data["forecast"][0]["upper_bound_95"] >= fc_data["forecast"][0]["predicted_value"]

    # 2. Test Scenario Simulation (Phase 27)
    # Simulate +10% price, -5% cost, +20% volume
    sc_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/scenario",
        json={"price_change_pct": 10.0, "cost_change_pct": -5.0, "volume_change_pct": 20.0},
    )
    assert sc_res.status_code == 200
    sc_data = sc_res.json()
    assert len(sc_data["impacts"]) == 3
    # Baseline revenue was (2+3+4)*1000 = 9000
    # Simulated revenue = 9 * 1.2 * 1100 = 11,880 (+32%)
    rev_impact = next(i for i in sc_data["impacts"] if i["metric_id"] == "total_revenue")
    assert rev_impact["simulated_value"] > rev_impact["baseline_value"]
    assert "profit" in sc_data["executive_takeaway"].lower()


@pytest.mark.asyncio
async def test_executive_report_and_copilot_and_benchmark(client: AsyncClient) -> None:
    """
    Test Phase 28 (Executive Report), Phase 29 (Dashboard Copilot), and Phase 30 (Benchmarking).
    """
    csv_1 = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City\n"
        b"1,2024-01-01,Phone,Electronics,5,500.0,300.0,Chicago\n"
        b"2,2024-02-01,Phone,Electronics,6,500.0,300.0,Chicago\n"
    )
    csv_2 = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City\n"
        b"1,2024-01-01,Phone,Electronics,10,500.0,300.0,Chicago\n"
        b"2,2024-02-01,Phone,Electronics,12,500.0,300.0,Chicago\n"
    )

    f1 = {"file": ("ds1.csv", io.BytesIO(csv_1), "text/csv")}
    u1 = await client.post("/api/v1/datasets/upload", files=f1)
    ds1_id = u1.json()["dataset_id"]

    f2 = {"file": ("ds2.csv", io.BytesIO(csv_2), "text/csv")}
    u2 = await client.post("/api/v1/datasets/upload", files=f2)
    ds2_id = u2.json()["dataset_id"]

    # 1. Test Executive Report (Phase 28)
    rep_res = await client.get(f"/api/v1/datasets/{ds1_id}/report")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert len(rep_data["sections"]) >= 1
    assert len(rep_data["strategic_recommendations"]) >= 1
    assert "# Executive Intelligence Brief" in rep_data["markdown_content"]

    # 2. Test Dashboard Copilot (Phase 29)
    # Generate default dashboard first
    dash_res = await client.get(f"/api/v1/datasets/{ds1_id}/dashboards/default")
    assert dash_res.status_code == 200
    dash_id = dash_res.json()["spec"]["id"]

    copilot_res = await client.post(
        f"/api/v1/dashboards/{dash_id}/copilot",
        json={"command": "Rename title to Q1 Midwest Performance"},
    )
    assert copilot_res.status_code == 200
    c_data = copilot_res.json()
    assert "Q1 Midwest Performance" in c_data["modified_spec"]["title"]

    # 3. Test Benchmarking (Phase 30)
    bench_res = await client.post(
        f"/api/v1/datasets/{ds1_id}/benchmark",
        json={"target_dataset_id": ds2_id},
    )
    assert bench_res.status_code == 200
    b_data = bench_res.json()
    assert len(b_data["metric_comparisons"]) >= 1
    # ds2 sold more quantity (22 vs 11), so delta percentage should be +100%
    qty_diff = next(m for m in b_data["metric_comparisons"] if m["metric_id"] == "units_sold" or m["metric_id"] == "total_revenue")
    assert qty_diff["is_positive_growth"] is True
