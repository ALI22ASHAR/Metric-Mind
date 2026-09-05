import io
import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.mark.asyncio
async def test_user_registration_login_profile(client: AsyncClient) -> None:
    """
    Test Phase 31 & 32: User registration, login, JWT token verification, and workspace retrieval.
    """
    email = "executive@metricmind.ai"
    password = "SecurePassword123!"

    # 1. Register User
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Executive Analyst",
            "workspace_name": "Acme Corp Analytics",
        },
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["email"] == email

    # 2. Login User
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 3. Fetch User Profile
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email
    assert len(me_data["workspaces"]) >= 1
    assert me_data["workspaces"][0]["name"] == "Acme Corp Analytics"


@pytest.mark.asyncio
async def test_dataset_exports_csv_excel_report(client: AsyncClient) -> None:
    """
    Test Phase 33: Data export engine (CSV, Excel, Markdown Report, HTML Report).
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City\n"
        b"101,2024-01-01,Widget A,Gadgets,5,100.0,60.0,Austin\n"
        b"102,2024-01-02,Widget B,Gadgets,10,150.0,90.0,Austin\n"
    )
    files = {"file": ("export_test.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Export CSV
    csv_res = await client.get(f"/api/v1/datasets/{dataset_id}/export/csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert b"Widget A" in csv_res.content

    # 2. Export Excel
    excel_res = await client.get(f"/api/v1/datasets/{dataset_id}/export/excel")
    assert excel_res.status_code == 200
    assert "spreadsheetml" in excel_res.headers.get("content-type", "")
    assert len(excel_res.content) > 100

    # 3. Export Markdown Report
    rep_md_res = await client.get(f"/api/v1/datasets/{dataset_id}/export/report?format=markdown")
    assert rep_md_res.status_code == 200
    assert "text/markdown" in rep_md_res.headers.get("content-type", "")
    assert b"# Executive Intelligence Brief" in rep_md_res.content

    # 4. Export HTML Report
    rep_html_res = await client.get(f"/api/v1/datasets/{dataset_id}/export/report?format=html")
    assert rep_html_res.status_code == 200
    assert "text/html" in rep_html_res.headers.get("content-type", "")
    assert b"<!DOCTYPE html>" in rep_html_res.content


@pytest.mark.asyncio
async def test_api_auth_can_be_enforced(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)

    protected = await client.get("/api/v1/datasets")
    assert protected.status_code == 401

    public = await client.get("/api/v1/health")
    assert public.status_code in (200, 503)
