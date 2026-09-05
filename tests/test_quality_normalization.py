import io
from pathlib import Path
import pytest
from httpx import AsyncClient
import polars as pl

from app.schemas.quality import NegativeMeasureHandling


@pytest.mark.asyncio
async def test_default_normalization_and_quality_report(client: AsyncClient) -> None:
    """
    Test that uploading a dataset creates both raw storage and clean Parquet,
    standardizes column names, and generates an initial DataQualityReport.
    """
    csv_content = (
        b"Order ID,Order Date,Product Category,Quantity,Sale Price\n"
        b" 101 ,2024-01-10, Electronics ,2,1200.0\n"
        b" 102 ,2024-01-11, Furniture ,5,25.0\n"
        b" 103 ,2024-01-12, Furniture ,1,150.0\n"
    )

    files = {"file": ("sales_raw.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # Fetch quality report
    report_res = await client.get(f"/api/v1/datasets/{dataset_id}/quality-report")
    assert report_res.status_code == 200
    data = report_res.json()

    assert data["dataset_id"] == dataset_id
    assert data["quality_score"] == 100.0  # Clean dataset
    assert data["total_rows"] == 3
    assert data["clean_rows"] == 3
    assert data["dropped_rows"] == 0
    assert data["clean_file_path"] is not None
    assert data["clean_file_path"].endswith("clean_data.parquet")

    # Verify Parquet file can be read and strings are trimmed & column names snake_case
    clean_df = pl.read_parquet(data["clean_file_path"])
    assert "order_id" in clean_df.columns
    assert "order_date" in clean_df.columns
    assert "product_category" in clean_df.columns
    assert clean_df["product_category"].to_list() == ["Electronics", "Furniture", "Furniture"]


@pytest.mark.asyncio
async def test_dirty_dataset_coercion_and_issues(client: AsyncClient) -> None:
    """
    Test normalizing dirty data with formatted currency strings ($1,200.00),
    negative prices, missing values, and duplicate rows.
    """
    csv_content = (
        b"Order_ID,City,Sale_Price,Quantity\n"
        b'101,New York,"$1,200.00",2\n'
        b"102,,-50.00,1\n"         # missing City, negative Sale_Price
        b"103,,$250.50,3\n"        # missing City
        b'101,New York,"$1,200.00",2\n'  # duplicate row
    )

    files = {"file": ("dirty_sales.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # Fetch quality report
    report_res = await client.get(f"/api/v1/datasets/{dataset_id}/quality-report")
    assert report_res.status_code == 200
    data = report_res.json()

    # Quality score should reflect penalties
    assert data["quality_score"] < 100.0
    assert data["issues_summary"].get("negative_measures") == 1
    assert data["issues_summary"].get("missing_values") == 2

    # Verify Parquet file coerced currency to Float64
    clean_df = pl.read_parquet(data["clean_file_path"])
    assert clean_df["sale_price"].dtype == pl.Float64
    assert clean_df["sale_price"][0] == 1200.0


@pytest.mark.asyncio
async def test_custom_cleaning_policy(client: AsyncClient) -> None:
    """
    Test applying a custom cleaning policy (handle_negative_measures='abs', drop_duplicates=True).
    """
    csv_content = (
        b"ID,Product,Price\n"
        b"1,Mouse,-25.0\n"
        b"2,Keyboard,-50.0\n"
        b"1,Mouse,-25.0\n"  # duplicate
    )

    files = {"file": ("neg_prices.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # Apply custom policy
    custom_policy = {
        "handle_negative_measures": NegativeMeasureHandling.ABS.value,
        "drop_duplicates": True,
        "standardize_column_names": True,
        "trim_whitespace": True,
    }

    normalize_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/normalize",
        json=custom_policy,
    )
    assert normalize_res.status_code == 200
    data = normalize_res.json()

    # Check rows dropped
    assert data["total_rows"] == 3
    assert data["clean_rows"] == 2
    assert data["dropped_rows"] == 1

    # Check Parquet values were converted to absolute positive values
    clean_df = pl.read_parquet(data["clean_file_path"])
    assert clean_df.height == 2
    assert (clean_df["price"] >= 0).all()
    assert sorted(clean_df["price"].to_list()) == [25.0, 50.0]


@pytest.mark.asyncio
async def test_outlier_detection_iqr(client: AsyncClient) -> None:
    """
    Test detecting statistical outliers with IQR method.
    """
    # 20 distributed values between 10.0 and 30.0, plus two massive outliers (5000 and 6000)
    normal_values = [f"{i},Item,{10.0 + i}" for i in range(1, 21)]
    outlier_values = ["21,Item,5000.0", "22,Item,6000.0"]
    csv_lines = ["ID,Product,Price"] + normal_values + outlier_values
    csv_content = "\n".join(csv_lines).encode("utf-8")

    files = {"file": ("outliers.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    report_res = await client.get(f"/api/v1/datasets/{dataset_id}/quality-report")
    assert report_res.status_code == 200
    data = report_res.json()

    assert len(data["outliers"]) > 0
    price_outlier = next((o for o in data["outliers"] if o["column_name"] == "price"), None)
    assert price_outlier is not None
    assert price_outlier["outlier_count"] == 2
    assert 5000.0 in price_outlier["sample_outliers"]
