import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duckdb_breakdown_and_filtering(client: AsyncClient) -> None:
    """
    Test Phase 7: DuckDB OLAP breakdowns by Category and City with dynamic filtering and sorting.
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,2,1200.0,800.0,Chicago,USA\n"
        b"1002,2024-01-16,Mouse,Electronics,5,25.0,10.0,Chicago,USA\n"
        b"1003,2024-01-17,Desk,Furniture,1,450.0,200.0,Dallas,USA\n"
    )

    files = {"file": ("sales_duckdb.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Breakdown by Category (Electronics vs Furniture)
    breakdown_payload = {
        "dimension": "Category",
        "metrics": ["total_revenue", "total_profit"],
        "sort_by": "total_revenue",
        "ascending": False,
    }
    res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/breakdown",
        json=breakdown_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["dimension"] == "Category"
    assert data["total_distinct_groups"] == 2
    assert len(data["rows"]) == 2

    # Electronics: 2*1200 + 5*25 = $2525 rev, $875 profit
    electronics_row = next(r for r in data["rows"] if r["dimension_value"] == "Electronics")
    assert electronics_row["total_revenue"] == 2525.0
    assert electronics_row["total_profit"] == 875.0

    # Furniture: 1*450 = $450 rev, $250 profit
    furniture_row = next(r for r in data["rows"] if r["dimension_value"] == "Furniture")
    assert furniture_row["total_revenue"] == 450.0
    assert furniture_row["total_profit"] == 250.0

    # 2. Filtered Breakdown: City = 'Chicago'
    filtered_payload = {
        "dimension": "Category",
        "metrics": ["total_revenue"],
        "filters": [
            {"column": "City", "operator": "eq", "value": "Chicago"}
        ],
    }
    filter_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/breakdown",
        json=filtered_payload,
    )
    assert filter_res.status_code == 200
    filter_data = filter_res.json()
    assert len(filter_data["rows"]) == 1
    assert filter_data["rows"][0]["dimension_value"] == "Electronics"
    assert filter_data["rows"][0]["total_revenue"] == 2525.0


@pytest.mark.asyncio
async def test_duckdb_raw_query_safety(client: AsyncClient) -> None:
    """
    Test Phase 7: Safe read-only SQL execution and blocking unsafe DDL/DML.
    """
    csv_content = b"id,val\n1,100\n2,200"
    files = {"file": ("simple_query.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # Valid SELECT
    query_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/query",
        json={"query": "SELECT SUM(val) AS total_val, COUNT(*) AS row_cnt FROM data"},
    )
    assert query_res.status_code == 200
    data = query_res.json()
    assert int(data["rows"][0]["total_val"]) == 300
    assert int(data["rows"][0]["row_cnt"]) == 2

    # Blocked Unsafe Query
    unsafe_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/query",
        json={"query": "DROP TABLE data"},
    )
    assert unsafe_res.status_code == 400
    assert "Only read-only SELECT queries are permitted" in unsafe_res.json()["detail"]

    unknown_column_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/query",
        json={"query": "SELECT missing_business_column FROM data"},
    )
    assert unknown_column_res.status_code == 400
    assert "Unknown dataset column" in unknown_column_res.json()["detail"]
