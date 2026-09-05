import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_natural_language_queries(client: AsyncClient) -> None:
    """
    Test Phases 17, 18, 19, 20: Natural-language text-to-SQL translation,
    security guardrails, deterministic DuckDB execution, and executive AI answer synthesis.
    """
    csv_content = (
        b"Order_ID,Order_Date,Product,Category,Quantity,Sale_Price,Cost_Price,City,Country\n"
        b"1001,2024-01-15,Laptop,Electronics,2,1200.0,800.0,Chicago,USA\n"
        b"1002,2024-01-16,Mouse,Electronics,5,25.0,10.0,New York,USA\n"
        b"1003,2024-02-17,Desk,Furniture,1,450.0,200.0,Dallas,USA\n"
    )

    files = {"file": ("sales_chat.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Total revenue query
    chat_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/chat",
        json={"query": "What is our total revenue?"},
    )
    assert chat_res.status_code == 200
    res_data = chat_res.json()

    assert res_data["question"] == "What is our total revenue?"
    assert len(res_data["data"]) >= 1
    assert "total_revenue" in res_data["sql_query"] or "Sale_Price" in res_data["sql_query"]
    assert len(res_data["insights"]) >= 1
    assert len(res_data["suggested_followups"]) >= 1
    assert res_data["execution_time_ms"] > 0

    # 2. Ranking query (Top Categories)
    rank_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/chat",
        json={"query": "What are our top categories by sales?"},
    )
    assert rank_res.status_code == 200
    rank_data = rank_res.json()
    assert len(rank_data["data"]) >= 2
    assert rank_data["chart_type"] in ["bar_chart", "table", "kpi_card"]

    # 3. Suggested questions endpoint
    sugg_res = await client.get(f"/api/v1/datasets/{dataset_id}/chat/suggested-questions")
    assert sugg_res.status_code == 200
    sugg_data = sugg_res.json()
    assert len(sugg_data["questions"]) >= 2

    # 3a. Greeting should not mention profit/revenue for an HR dataset
    greeting_res = await client.post(
        f"/api/v1/datasets/{dataset_id}/chat",
        json={"query": "hEY"},
    )
    assert greeting_res.status_code == 200
    greeting_text = greeting_res.json()["answer_text"]
    greeting_followups = greeting_res.json()["suggested_followups"]
    # This dataset is sales so revenue IS fine; the assertion below is a
    # regression guard for the broader fix: domain must appear in the greeting.
    assert "Business Intelligence Analyst" in greeting_text


@pytest.mark.asyncio
async def test_chat_greeting_is_domain_aware_for_hr_dataset(client: AsyncClient) -> None:
    """
    Regression: greeting and suggested questions on an HR dataset must NOT
    mention sales-economics concepts (revenue, profit, margin, categories).
    """
    csv_content = (
        b"EmployeeID,FullName,Department,JobTitle,AnnualSalaryUSD,HireDate,Country,City,Age,TenureYears\n"
        b"EMP-1,Alice,Sales,Manager,85000,2020-01-15,USA,NYC,35,5.2\n"
        b"EMP-2,Bob,Engineering,Engineer,95000,2019-06-10,USA,SF,30,6.1\n"
        b"EMP-3,Carol,Marketing,Lead,72000,2021-03-20,USA,LA,28,4.3\n"
    )
    files = {"file": ("hr_test_chat.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    sugg_res = await client.get(f"/api/v1/datasets/{dataset_id}/chat/suggested-questions")
    assert sugg_res.status_code == 200
    questions = sugg_res.json()["questions"]

    # Greeting response
    greeting = await client.post(
        f"/api/v1/datasets/{dataset_id}/chat",
        json={"query": "hEY"},
    )
    assert greeting.status_code == 200
    answer = greeting.json()["answer_text"]
    followups = greeting.json()["suggested_followups"]

    # No suggested question or follow-up should claim this dataset has revenue/profit
    for q in questions + followups:
        q_lower = q.lower()
        assert "revenue" not in q_lower, f"Sales concept leaked into HR suggestion: {q!r}"
        assert "profit margin" not in q_lower, f"Sales concept leaked into HR suggestion: {q!r}"
    # The greeting should mention the HR domain
    assert "human resources" in answer.lower() or "headcount" in answer.lower()
