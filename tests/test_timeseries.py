import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_timeseries_monthly_trends_and_growth(client: AsyncClient) -> None:
    """
    Test Phase 8: Time-Series trend aggregations and MoM period-over-period growth calculation.
    """
    # Jan 2024: 1 Laptop @ $1000 = $1000 rev
    # Feb 2024: 2 Laptops @ $1000 = $2000 rev (+100% MoM growth!)
    csv_content = (
        b"Order_ID,Order_Date,Product,Quantity,Sale_Price\n"
        b"1001,2024-01-15,Laptop,1,1000.0\n"
        b"1002,2024-02-15,Laptop,2,1000.0\n"
    )

    files = {"file": ("sales_timeseries.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # Request monthly time series
    ts_payload = {
        "granularity": "month",
        "metrics": ["total_revenue", "units_sold"],
    }
    res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/timeseries",
        json=ts_payload,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["dataset_id"] == dataset_id
    assert data["granularity"] == "month"
    assert len(data["points"]) == 2

    # Check Jan & Feb points
    jan_pt = data["points"][0]
    assert "2024-01" in jan_pt["period_start"]
    assert jan_pt["period_label"] == "2024-01"
    assert jan_pt["values"]["total_revenue"] == 1000.0
    assert jan_pt["values"]["units_sold"] == 1.0

    feb_pt = data["points"][1]
    assert "2024-02" in feb_pt["period_start"]
    assert feb_pt["period_label"] == "2024-02"
    assert feb_pt["values"]["total_revenue"] == 2000.0
    assert feb_pt["values"]["units_sold"] == 2.0

    # Check Period-over-Period growth summary
    growth = data["growth_summary"]
    rev_growth = growth["total_revenue"]
    assert rev_growth["prior_value"] == 1000.0
    assert rev_growth["current_value"] == 2000.0
    assert rev_growth["absolute_change"] == 1000.0
    assert rev_growth["growth_percentage"] == 100.0
    assert rev_growth["trend"] == "up"


@pytest.mark.asyncio
async def test_timeseries_confidence_and_headline_insight(client: AsyncClient) -> None:
    """
    Test that PeriodOverPeriodGrowth includes:
      - data_quality_score (0-100) derived from the profiler
      - confidence_factors list with at least the 4 standard dimensions
      - headline_insight (deterministic one-sentence narrative)
    """
    # Three months of data, two categories, so the headline insight has a
    # clear leading segment to report.
    csv_content = (
        b"Order_ID,Order_Date,Category,Quantity,Sale_Price\n"
        b"1001,2024-01-15,Electronics,1,1000.0\n"
        b"1002,2024-01-20,Electronics,1,1000.0\n"
        b"1003,2024-01-22,Furniture,1,500.0\n"
        b"1004,2024-02-10,Electronics,1,1000.0\n"
        b"1005,2024-02-12,Electronics,1,1000.0\n"
        b"1006,2024-02-15,Furniture,1,500.0\n"
        b"1007,2024-03-05,Electronics,1,1000.0\n"
        b"1008,2024-03-07,Electronics,1,1000.0\n"
        b"1009,2024-03-09,Electronics,1,1000.0\n"
        b"1010,2024-03-12,Furniture,1,500.0\n"
    )

    files = {"file": ("sales_confidence.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/timeseries",
        json={"granularity": "month", "metrics": ["total_revenue"]},
    )
    assert res.status_code == 200
    data = res.json()

    growth = data["growth_summary"]["total_revenue"]
    # The new fields are present
    assert "data_quality_score" in growth
    assert "confidence_label" in growth
    assert "confidence_factors" in growth
    assert "headline_insight" in growth

    # Score is a 0-100 number
    score = growth["data_quality_score"]
    assert score is not None
    assert 0 <= score <= 100

    # Label is human-readable
    assert growth["confidence_label"] in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Low confidence",
    }

    # Factors are a list with the 4 standard dimensions
    factor_labels = {f["label"] for f in growth["confidence_factors"]}
    assert {"Sample size", "Data completeness", "Data quality", "Trend depth"}.issubset(factor_labels)
    for f in growth["confidence_factors"]:
        assert 0 <= f["score"] <= 100
        assert "detail" in f

    # Headline insight mentions the leading segment and is non-trivial
    headline = growth["headline_insight"]
    assert headline and isinstance(headline, str)
    # The leading segment should appear in the headline (Electronics dominates).
    assert "Electronics" in headline or "leading segment" in headline


@pytest.mark.asyncio
async def test_timeseries_single_period_uses_limited_history(client: AsyncClient) -> None:
    """
    A dataset with only one month of data should still produce a growth_summary
    entry, but the label should reflect the limited history and no headline
    should imply a real trend.
    """
    csv_content = (
        b"Order_ID,Order_Date,Category,Quantity,Sale_Price\n"
        b"1001,2024-01-15,Electronics,1,1000.0\n"
        b"1002,2024-01-20,Furniture,1,500.0\n"
    )

    files = {"file": ("sales_single_period.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = await client.post("/api/v1/datasets/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    res = await client.post(
        f"/api/v1/datasets/{dataset_id}/analytics/timeseries",
        json={"granularity": "month", "metrics": ["total_revenue"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["points"]) == 1

    growth = data["growth_summary"]["total_revenue"]
    # Still has a confidence score — but trend depth should be 0
    assert "data_quality_score" in growth
    factors = {f["label"]: f for f in growth["confidence_factors"]}
    assert factors["Trend depth"]["score"] < 100
    assert "Insufficient history" in (growth["headline_insight"] or "")


def test_data_quality_score_unit_high_quality() -> None:
    """
    Pure unit test: with 10k rows, 0% nulls, no warnings, the score should
    be near 100 and the label should be "High confidence".
    """
    from app.analytics.timeseries import _compute_data_quality_score
    from app.schemas.metrics import MetricDefinition, MetricType

    metric = MetricDefinition(
        id="total_revenue",
        name="total_revenue",
        label="Total Revenue",
        description="",
        metric_type=MetricType.CURRENCY,
        unit="$",
        sql_template="SUM(Sale_Price)",
    )

    score, label, factors = _compute_data_quality_score(
        metric,
        {
            "row_count": 12_000,
            "avg_null_percentage": 0.5,
            "quality_warnings_count": 0,
            "critical_warnings_count": 0,
            "has_periods": True,
        },
    )
    assert score is not None
    assert score >= 90
    assert label == "High confidence"
    factor_dicts = [f.model_dump() for f in factors]
    assert any(f["label"] == "Sample size" and f["score"] == 100 for f in factor_dicts)


def test_data_quality_score_unit_low_quality() -> None:
    """
    With sparse rows, high null %, many warnings and no period history, the
    score should land in the "Low confidence" bucket.
    """
    from app.analytics.timeseries import _compute_data_quality_score
    from app.schemas.metrics import MetricDefinition, MetricType

    metric = MetricDefinition(
        id="total_revenue",
        name="total_revenue",
        label="Total Revenue",
        description="",
        metric_type=MetricType.CURRENCY,
        unit="$",
        sql_template="SUM(Sale_Price)",
    )

    score, label, _factors = _compute_data_quality_score(
        metric,
        {
            "row_count": 30,
            "avg_null_percentage": 45.0,
            "quality_warnings_count": 5,
            "critical_warnings_count": 1,
            "has_periods": False,
        },
    )
    assert score is not None
    assert score < 40
    assert label in {"Low confidence", "Limited confidence"}

