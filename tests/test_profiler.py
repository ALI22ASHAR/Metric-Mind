import io
import pytest
from httpx import AsyncClient

from app.schemas.profile import ColumnRole, ColumnType, WarningSeverity


@pytest.mark.asyncio
async def test_dataset_profiling_basic(client: AsyncClient) -> None:
    """
    Test profiling a standard sales dataset with measures, dimensions, dates, and IDs.
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price\n"
        b"101,2024-01-10,Laptop,Electronics,2,1200.0\n"
        b"102,2024-01-11,Mouse,Electronics,5,25.0\n"
        b"103,2024-01-12,Chair,Furniture,1,150.0\n"
        b"104,2024-01-13,Desk,Furniture,2,300.0\n"
    )

    files = {"file": ("sales_sample.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # Fetch profile
    profile_res = await client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert profile_res.status_code == 200
    data = profile_res.json()

    # Verify Summary
    assert data["summary"]["row_count"] == 4
    assert data["summary"]["column_count"] == 6
    assert data["summary"]["duplicate_rows"] == 0

    # Build lookup map for column profiles
    cols_map = {col["name"]: col for col in data["columns_info"]}

    # Verify Order_ID
    assert cols_map["Order_ID"]["role"] == ColumnRole.ID.value

    # Verify Order_Date
    assert cols_map["Order_Date"]["role"] == ColumnRole.TIME_DIMENSION.value
    assert cols_map["Order_Date"]["detected_type"] in (ColumnType.DATE.value, ColumnType.DATETIME.value)

    # Verify Category
    assert cols_map["Category"]["role"] == ColumnRole.DIMENSION.value
    assert cols_map["Category"]["detected_type"] == ColumnType.CATEGORICAL.value

    # Verify Quantity
    assert cols_map["Quantity"]["role"] == ColumnRole.MEASURE.value
    assert cols_map["Quantity"]["detected_type"] == ColumnType.NUMERIC.value
    assert cols_map["Quantity"]["numeric_stats"]["min"] == 1.0
    assert cols_map["Quantity"]["numeric_stats"]["max"] == 5.0
    assert cols_map["Quantity"]["numeric_stats"]["mean"] == 2.5

    # Verify Sale_Price
    assert cols_map["Sale_Price"]["role"] == ColumnRole.MEASURE.value
    assert cols_map["Sale_Price"]["numeric_stats"]["min"] == 25.0
    assert cols_map["Sale_Price"]["numeric_stats"]["max"] == 1200.0


@pytest.mark.asyncio
async def test_data_quality_warnings_detected(client: AsyncClient) -> None:
    """
    Test that data quality issues (duplicates, negative prices, missing values, constant column)
    are accurately identified in quality_warnings.
    """
    csv_content = (
        b"Order_ID,City,Sale_Price,Status\n"
        b"101,New York,100.0,ACTIVE\n"
        b"102,,-50.0,ACTIVE\n"  # missing City, negative Sale_Price
        b"103,,200.0,ACTIVE\n"   # missing City
        b"101,New York,100.0,ACTIVE\n"  # duplicate of row 1
    )

    files = {"file": ("dirty_data.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    profile_res = await client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert profile_res.status_code == 200
    data = profile_res.json()

    warnings = data["quality_warnings"]
    warning_types = [w["warning_type"] for w in warnings]

    # Verify duplicate rows detected
    assert "duplicate_rows" in warning_types

    # Verify missing values in City detected (2 out of 4 rows = 50%)
    assert "missing_values" in warning_types or "high_missing_values" in warning_types
    city_warning = next((w for w in warnings if w["column_name"] == "City"), None)
    assert city_warning is not None
    assert city_warning["metric_value"] == 50.0

    # Verify negative price warning
    assert "negative_values" in warning_types
    price_warning = next((w for w in warnings if w["column_name"] == "Sale_Price"), None)
    assert price_warning is not None
    assert price_warning["metric_value"] == -50.0

    # Verify constant column warning for Status
    assert "constant_column" in warning_types
    status_warning = next((w for w in warnings if w["column_name"] == "Status"), None)
    assert status_warning is not None


@pytest.mark.asyncio
async def test_re_profile_endpoint(client: AsyncClient) -> None:
    """
    Test explicit re-profiling endpoint.
    """
    csv_content = b"A,B\n1,10\n2,20\n3,30"
    files = {"file": ("ab.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    re_profile_res = await client.post(f"/api/v1/datasets/{dataset_id}/profile")
    assert re_profile_res.status_code == 200
    data = re_profile_res.json()
    assert data["summary"]["row_count"] == 3
    assert data["summary"]["column_count"] == 2
