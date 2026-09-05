import io
import pytest
from httpx import AsyncClient

from app.analytics.formula_engine import formula_engine
from app.analytics.geo_engine import geo_engine
from app.schemas.semantic import SemanticModelSchema


def test_formula_engine_validation():
    available_cols = ["Total_Revenue", "Total_Cost", "Quantity", "Category"]
    
    # 1. Valid mathematical formula
    res = formula_engine.validate_and_compile("(Total_Revenue - Total_Cost) / Total_Revenue * 100", available_cols)
    assert res.is_valid is True
    assert "SUM" in res.sql_template
    assert len(res.referenced_columns) == 2

    # 2. Invalid column
    res_inv = formula_engine.validate_and_compile("Unknown_Col * 2", available_cols)
    assert res_inv.is_valid is False
    assert "does not exist" in res_inv.error_message

    # 3. Forbidden SQL injection keyword
    res_bad = formula_engine.validate_and_compile("Total_Revenue; DROP TABLE users", available_cols)
    assert res_bad.is_valid is False
    assert "Forbidden keyword" in res_bad.error_message


def test_geo_engine_detection():
    cols = ["Order_ID", "Sales", "Region", "Category"]
    semantic = SemanticModelSchema(
        dataset_id="test_ds",
        domain="sales",
        category_column="Category",
        dimensions=["Region"],
        numeric_measures=["Sales"],
    )
    geo_col = geo_engine.identify_geo_column(cols, semantic)
    assert geo_col == "Region"


@pytest.mark.asyncio
async def test_geo_and_custom_metric_endpoints(client: AsyncClient):
    csv_content = b"Order_ID,Product,Region,Category,Quantity,Sale_Price\n1001,Laptop,North America,Tech,2,1200\n1002,Mouse,Europe,Tech,5,25\n1003,Desk,Europe,Furniture,1,450"
    files = {"file": ("sales_geo_test.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Test Geographic breakdown endpoint
    geo_res = await client.get(f"/api/v1/datasets/{dataset_id}/analytics/geo-breakdown?metric=total_revenue")
    assert geo_res.status_code == 200
    geo_json = geo_res.json()
    assert geo_json["has_geographic_data"] is True
    assert len(geo_json["features"]) >= 1

    # 2. Test Custom Metric registration
    custom_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/metrics/custom",
        json={
            "name": "sales_per_order",
            "label": "Sales Per Order",
            "formula": "Sale_Price * Quantity",
            "format_type": "currency",
        },
    )
    assert custom_res.status_code == 201
    assert custom_res.json()["name"] == "sales_per_order"

    # 3. Test List Custom Metrics
    list_res = await client.get(f"/api/v1/datasets/{dataset_id}/metrics/custom")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Test PDF Export Endpoint
    pdf_res = await client.get(f"/api/v1/datasets/{dataset_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
