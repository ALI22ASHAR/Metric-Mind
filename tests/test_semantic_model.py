import io
import pytest
from httpx import AsyncClient

from app.schemas.semantic import BusinessConcept


@pytest.mark.asyncio
async def test_semantic_model_standard_sales(client: AsyncClient) -> None:
    """
    Test semantic model generation on standard sales dataset headers.
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,2,1200.0,800.0,Chicago,USA\n"
        b"1002,2024-01-16,Mouse,Electronics,5,25.0,10.0,New York,USA\n"
    )

    files = {"file": ("sales_standard.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # Fetch semantic model
    res = await client.get(f"/api/v1/datasets/{dataset_id}/semantic-model")
    assert res.status_code == 200
    data = res.json()

    assert data["dataset_id"] == dataset_id
    assert data["domain"] in ["sales", "ecommerce"]

    mappings = data["mappings"]
    assert mappings.get(BusinessConcept.ORDER_ID) == "Order_ID"
    assert mappings.get(BusinessConcept.DATE) == "Order_Date"
    assert mappings.get(BusinessConcept.PRODUCT) == "Product"
    assert mappings.get(BusinessConcept.CATEGORY) == "Category"
    assert mappings.get(BusinessConcept.QUANTITY) == "Quantity"
    assert mappings.get(BusinessConcept.SALE_PRICE) == "Sale_Price"
    assert mappings.get(BusinessConcept.COST_PRICE) == "Cost_Price"
    assert mappings.get(BusinessConcept.CITY) == "City"
    assert mappings.get(BusinessConcept.COUNTRY) == "Country"

    # Verify measures & dimensions classifications
    assert "Quantity" in data["measures"]
    assert "Sale_Price" in data["measures"]
    assert "Category" in data["dimensions"]
    assert "Order_Date" in data["time_dimensions"]


@pytest.mark.asyncio
async def test_semantic_model_abbreviated_headers(client: AsyncClient) -> None:
    """
    Test semantic model mapping with abbreviated headers (date, item, qty, sp, cp, region).
    """
    csv_content = (
        b"order_id,date,item,qty,sp,cp,region\n"
        b"2001,2024-02-01,Keyboard,10,45.0,20.0,North\n"
        b"2002,2024-02-02,Monitor,2,300.0,180.0,South\n"
    )

    files = {"file": ("sales_abbrev.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    res = await client.get(f"/api/v1/datasets/{dataset_id}/semantic-model")
    assert res.status_code == 200
    data = res.json()

    mappings = data["mappings"]
    assert mappings.get(BusinessConcept.ORDER_ID) == "order_id"
    assert mappings.get(BusinessConcept.DATE) == "date"
    assert mappings.get(BusinessConcept.PRODUCT) == "item"
    assert mappings.get(BusinessConcept.QUANTITY) == "qty"
    assert mappings.get(BusinessConcept.SALE_PRICE) == "sp"
    assert mappings.get(BusinessConcept.COST_PRICE) == "cp"
    assert mappings.get(BusinessConcept.REGION) == "region"


@pytest.mark.asyncio
async def test_update_semantic_model_success(client: AsyncClient) -> None:
    """
    Test manual/AI update of semantic model concept mappings.
    """
    csv_content = b"tx_id,day,goods,units,val\n1,2024-01-01,Apple,5,10.0"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    update_payload = {
        "domain": "retail",
        "dataset_type": "grocery_retail",
        "mappings": {
            "order_id_column": "tx_id",
            "date_column": "day",
            "product_column": "goods",
            "quantity_column": "units",
            "sale_price_column": "val",
        },
    }

    put_res = await client.put(
        f"/api/v1/datasets/{dataset_id}/semantic-model",
        json=update_payload,
    )
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["domain"] == "retail"
    assert data["mappings"]["product_column"] == "goods"
    assert data["confidence_scores"]["product_column"] == 1.0


@pytest.mark.asyncio
async def test_update_semantic_model_rejects_invalid_column(client: AsyncClient) -> None:
    """
    Test that updating a semantic model with a non-existent column returns 400 Bad Request.
    """
    csv_content = b"id,sales\n1,100"
    files = {"file": ("simple.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    invalid_payload = {
        "mappings": {
            "product_column": "nonexistent_column_xyz",
        },
    }

    put_res = await client.put(
        f"/api/v1/datasets/{dataset_id}/semantic-model",
        json=invalid_payload,
    )
    assert put_res.status_code == 400
    assert "Invalid column 'nonexistent_column_xyz'" in put_res.json()["detail"]
