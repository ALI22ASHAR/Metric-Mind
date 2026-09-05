import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_spa_root_endpoint_serving(client: AsyncClient) -> None:
    """
    Test Phase 13: Web UI SPA index.html is served at / and /dashboard with correct metadata.
    """
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "<title>MetricMind | AI-Powered Business Intelligence</title>" in res.text
    assert "upload-modal" in res.text
    assert "dashboard-grid" in res.text

    dash_res = await client.get("/dashboard")
    assert dash_res.status_code == 200
    assert "<title>MetricMind | AI-Powered Business Intelligence</title>" in dash_res.text


@pytest.mark.asyncio
async def test_static_assets_serving(client: AsyncClient) -> None:
    """
    Test Phase 13: CSS, JS modules are properly served under /static/
    """
    css_res = await client.get("/static/css/main.css")
    assert css_res.status_code == 200
    assert "--bg-main" in css_res.text
    assert ".dashboard-grid" in css_res.text

    js_res = await client.get("/static/js/app.js")
    assert js_res.status_code == 200
    assert "MetricMindApp" in js_res.text

    charts_js_res = await client.get("/static/js/charts.js")
    assert charts_js_res.status_code == 200
    assert "ChartManager" in charts_js_res.text
