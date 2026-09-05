import io
import pytest
from httpx import AsyncClient

from app.ai.schema_agent import SchemaUnderstandingAgent
from app.schemas.ai_dataset import AIDatasetUnderstanding


@pytest.mark.asyncio
async def test_ai_understanding_generation_on_upload(client: AsyncClient) -> None:
    """
    Test that uploading a dataset automatically triggers the AI understanding agent
    and produces structured metadata, hierarchies, and recommended questions.
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,2,1200.0,800.0,Chicago,USA\n"
        b"1002,2024-01-16,Mouse,Electronics,5,25.0,10.0,New York,USA\n"
        b"1003,2024-01-17,Desk,Furniture,1,450.0,200.0,Dallas,USA\n"
    )

    files = {"file": ("sales_complete.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # Fetch AI understanding
    res = await client.get(f"/api/v1/datasets/{dataset_id}/ai-understanding")
    assert res.status_code == 200
    data = res.json()

    assert data["dataset_id"] == dataset_id
    assert data["domain"] in ["ecommerce", "sales"]
    assert len(data["business_summary"]) > 20
    assert len(data["recommended_metrics"]) >= 3
    assert len(data["candidate_business_questions"]) >= 2
    assert data["confidence_score"] >= 0.8

    # Verify dimensional hierarchies
    hierarchies = data["dimension_hierarchies"]
    assert len(hierarchies) >= 1
    # Check that hierarchy items are valid columns
    for path in hierarchies:
        for col_name in path:
            assert isinstance(col_name, str)


def test_anti_hallucination_sanitization() -> None:
    """
    Unit test ensuring that hallucinated/non-existent columns proposed by an LLM
    are stripped before persistence.
    """
    valid_cols = ["order_id", "order_date", "product", "price"]

    raw_ai_output = AIDatasetUnderstanding(
        dataset_id="ds_test",
        domain="sales",
        business_summary="Test sales summary",
        primary_date_column="hallucinated_timestamp_col",  # Invalid
        refined_mappings={
            "product_column": "product",                  # Valid
            "cost_price_column": "fake_cost_col",         # Invalid
        },
        dimension_hierarchies=[
            ["country", "state", "city"],                 # None exist -> should be stripped
            ["product", "fake_variant"],                  # product exists -> trimmed to ["product"]
        ],
        recommended_metrics=["total_revenue"],
        candidate_business_questions=["What is revenue?"],
        confidence_score=0.95,
    )

    sanitized = SchemaUnderstandingAgent.sanitize_understanding(raw_ai_output, valid_cols)

    # primary_date_column was stripped to None
    assert sanitized.primary_date_column is None
    # fake_cost_col was stripped
    assert "cost_price_column" not in sanitized.refined_mappings
    assert sanitized.refined_mappings["product_column"] == "product"
    # only valid hierarchies retained
    assert sanitized.dimension_hierarchies == [["product"]]


@pytest.mark.asyncio
async def test_trigger_ai_understanding_post_endpoint(client: AsyncClient) -> None:
    """
    Test explicitly re-triggering AI understanding via POST endpoint.
    """
    csv_content = b"trans_id,date,item,qty,sp\n101,2024-01-01,Phone,1,799.0"
    files = {"file": ("simple_pos.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    post_res = await client.post(f"/api/v1/datasets/{dataset_id}/ai-understanding")
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["dataset_id"] == dataset_id
    assert "total_revenue" in data["recommended_metrics"]
