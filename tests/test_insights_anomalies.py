import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_automated_insights_and_anomalies(client: AsyncClient) -> None:
    """
    Test Phases 21, 22, 23: Automated Pareto concentration insights,
    time-series statistical anomaly detection, and root cause decomposition.
    """
    # Jan: 1 Laptop @ $1000 = $1000 rev
    # Feb: 5 Laptops @ $1000 = $5000 rev (+400% spike in Electronics!)
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,1,1000.0,700.0,Chicago,USA\n"
        b"1002,2024-02-15,Laptop,Electronics,5,1000.0,700.0,Chicago,USA\n"
        b"1003,2024-02-16,Mouse,Electronics,2,50.0,20.0,Dallas,USA\n"
    )

    files = {"file": ("sales_insights.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Fetch automated business insights (Phase 21)
    ins_res = await client.get(f"/api/v1/datasets/{dataset_id}/insights")
    assert ins_res.status_code == 200
    ins_data = ins_res.json()
    assert ins_data["total_insights"] >= 1
    assert len(ins_data["insights"]) >= 1

    first_ins = ins_data["insights"][0]
    assert first_ins["impact_score"] > 0
    assert "Electronics" in first_ins["title"] or "Revenue" in first_ins["title"] or "Concentration" in first_ins["title"]

    # 2. Fetch statistical anomalies and root cause analysis (Phases 22 & 23)
    anom_res = await client.get(f"/api/v1/datasets/{dataset_id}/anomalies")
    assert anom_res.status_code == 200
    anom_data = anom_res.json()
    assert anom_data["total_anomalies"] >= 1

    first_anom = anom_data["anomalies"][0]
    assert first_anom["anomaly_type"] in ["spike", "drop"]
    assert first_anom["deviation_percentage"] > 0
    assert len(first_anom["explanation"]) > 0


@pytest.mark.asyncio
async def test_chat_session_persistence(client: AsyncClient) -> None:
    """
    Test Phase 24: Conversational session and message persistence.
    """
    csv_content = b"id,val\n1,100\n2,200"
    files = {"file": ("chat_session.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # Ask a question to trigger message persistence
    await client.post(
        f"/api/v1/datasets/{dataset_id}/chat",
        json={"query": "What is the total count?"},
    )

    # 1. List sessions
    sess_res = await client.get(f"/api/v1/datasets/{dataset_id}/chat/sessions")
    assert sess_res.status_code == 200
    sessions = sess_res.json()
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]

    # 2. List session messages
    msg_res = await client.get(f"/api/v1/datasets/{dataset_id}/chat/sessions/{session_id}/messages")
    assert msg_res.status_code == 200
    messages = msg_res.json()
    assert len(messages) >= 2  # user message + assistant message
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
