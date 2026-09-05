import io
from pathlib import Path
import pytest
from httpx import AsyncClient
import openpyxl

from app.core.config import settings
from app.models.dataset import DatasetStatus


@pytest.mark.asyncio
async def test_upload_csv_dataset_success(client: AsyncClient) -> None:
    """
    Test uploading a valid CSV file.
    """
    csv_content = b"Order_ID,Product,Quantity,Sale_Price\n1001,Laptop,2,1200\n1002,Mouse,5,25"
    files = {
        "file": ("sales_sample.csv", io.BytesIO(csv_content), "text/csv")
    }

    response = await client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 201
    data = response.json()

    assert "dataset_id" in data
    assert data["dataset_id"].startswith("ds_")
    assert data["filename"] == "sales_sample.csv"
    assert data["status"] == DatasetStatus.READY.value
    assert data["file_size_bytes"] == len(csv_content)


@pytest.mark.asyncio
async def test_upload_xlsx_dataset_success(client: AsyncClient) -> None:
    """
    Test uploading a valid XLSX file.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Order_ID", "Product", "Quantity", "Sale_Price"])
    ws.append([2001, "Keyboard", 10, 45])

    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_bytes = excel_buffer.getvalue()

    files = {
        "file": ("sales.xlsx", io.BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }

    response = await client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 201
    data = response.json()

    assert data["dataset_id"].startswith("ds_")
    assert data["filename"] == "sales.xlsx"
    assert data["status"] == DatasetStatus.READY.value


@pytest.mark.asyncio
async def test_upload_invalid_extension(client: AsyncClient) -> None:
    """
    Test uploading a file with an unsupported extension (e.g. .txt).
    """
    files = {
        "file": ("notes.txt", io.BytesIO(b"some plain text"), "text/plain")
    }

    response = await client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file extension" in data["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file(client: AsyncClient) -> None:
    """
    Test uploading an empty file (0 bytes).
    """
    files = {
        "file": ("empty.csv", io.BytesIO(b""), "text/csv")
    }

    response = await client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "empty" in data["detail"].lower()


@pytest.mark.asyncio
async def test_upload_file_exceeds_size_limit(client: AsyncClient, monkeypatch) -> None:
    """
    Test that uploading a file larger than max_upload_size_bytes raises 413.
    """
    monkeypatch.setattr(settings, "max_upload_size_bytes", 500)

    large_content = b"A" * 1024  # 1KB > 500B limit
    files = {
        "file": ("large.csv", io.BytesIO(large_content), "text/csv")
    }

    response = await client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_dataset_by_id(client: AsyncClient) -> None:
    """
    Test retrieving a dataset by its ID.
    """
    csv_content = b"ID,Name\n1,Alpha"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}

    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    get_res = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == dataset_id
    assert data["filename"] == "test.csv"
    assert data["status"] == DatasetStatus.READY.value
    assert data["file_size_bytes"] == len(csv_content)


@pytest.mark.asyncio
async def test_get_dataset_not_found(client: AsyncClient) -> None:
    """
    Test 404 error when requesting a non-existent dataset.
    """
    response = await client.get("/api/v1/datasets/ds_nonexistent123")
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_datasets(client: AsyncClient) -> None:
    """
    Test listing datasets with pagination.
    """
    # Upload 2 datasets
    for i in range(2):
        files = {"file": (f"test_{i}.csv", io.BytesIO(b"col1\nval"), "text/csv")}
        res = await client.post("/api/v1/datasets/upload", files=files)
        assert res.status_code == 201

    list_res = await client.get("/api/v1/datasets?skip=0&limit=10")
    assert list_res.status_code == 200
    data = list_res.json()
    assert "items" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_delete_dataset(client: AsyncClient) -> None:
    """
    Test deleting a dataset and verifying file cleanup.
    """
    csv_content = b"col1,col2\nval1,val2"
    files = {"file": ("to_delete.csv", io.BytesIO(csv_content), "text/csv")}

    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # Delete dataset
    delete_res = await client.delete(f"/api/v1/datasets/{dataset_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["deleted"] is True

    # Verify 404 on subsequent get
    get_res = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_res.status_code == 404
