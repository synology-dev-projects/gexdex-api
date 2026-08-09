import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.gexdex_service import (
    calculate_metrics_from_raw,
    get_gexdex_data,
    render_gexdex_chart_image,
    GexDexTickerMetrics
)

client = TestClient(app)
TEST_API_KEY = "YOUR_SECRET_API_KEY_HERE"

MOCK_RAW_PAYLOAD = {
    "ticker": "AAPL",
    "spot_price": 225.50,
    "gex_wall": 230.00,
    "call_wall": 235.00,
    "put_wall": 220.00,
    "strikes": [
        {
            "strike": 220.0,
            "expirations": {
                "2026-08-15": {
                    "call_gex": 100000.0,
                    "put_gex": 500000.0,
                    "call_dex": 200000.0,
                    "put_dex": 100000.0
                }
            }
        },
        {
            "strike": 230.0,
            "expirations": {
                "2026-08-15": {
                    "call_gex": 800000.0,
                    "put_gex": 100000.0,
                    "call_dex": 600000.0,
                    "put_dex": 50000.0
                }
            }
        }
    ],
    "rolling": {
        "strikes": [220.0, 230.0],
        "call_dex": [200, 600],
        "put_dex": [100, 50],
        "call_gex": [100, 800],
        "put_gex": [500, 100]
    }
}


MOCK_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000


@pytest.fixture(autouse=True)
def mock_fetch_raw_data():
    with patch("app.services.gexdex_service.fetch_raw_data_for_ticker", return_value=MOCK_RAW_PAYLOAD), \
         patch("app.services.gexdex_service.render_gexdex_chart_image", return_value=MOCK_PNG_BYTES), \
         patch("app.api.v1.endpoints.gexdex.render_gexdex_chart_image", return_value=MOCK_PNG_BYTES):
        yield


def test_health_check():
    """Verifies that /health endpoint returns HTTP 200 and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_gexdex_unauthorized_without_key():
    """Verifies that requests without X-API-Key return HTTP 401."""
    response = client.get("/api/v1/gexdex?tickers=AAPL")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_gexdex_unauthorized_with_wrong_key():
    """Verifies that requests with an invalid X-API-Key return HTTP 401."""
    response = client.get(
        "/api/v1/gexdex?tickers=AAPL",
        headers={"X-API-Key": "INVALID_KEY_123"}
    )
    assert response.status_code == 401


def test_gexdex_success_single_ticker():
    """Verifies HTTP GET /api/v1/gexdex returns valid GEX/DEX metrics when authenticated."""
    response = client.get(
        "/api/v1/gexdex?tickers=AAPL",
        headers={"X-API-Key": TEST_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "AAPL" in data
    assert data["AAPL"]["ticker"] == "AAPL"


def test_gexdex_non_null_fields_validation():
    """
    Verifies that all returned fields in the response payload are non-null,
    valid numbers or non-empty strings.
    """
    response = client.get(
        "/api/v1/gexdex?tickers=AAPL,TSLA",
        headers={"X-API-Key": TEST_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()

    for ticker_symbol, metrics in data.items():
        assert metrics is not None, f"Metrics object for {ticker_symbol} is null"
        
        assert metrics.get("ticker") is not None and isinstance(metrics["ticker"], str) and len(metrics["ticker"]) > 0
        assert metrics.get("spot_price") is not None and isinstance(metrics["spot_price"], (int, float))
        assert metrics.get("net_gex") is not None and isinstance(metrics["net_gex"], (int, float))
        assert metrics.get("net_dex") is not None and isinstance(metrics["net_dex"], (int, float))
        assert metrics.get("zero_gex_level") is not None and isinstance(metrics["zero_gex_level"], (int, float))
        assert metrics.get("call_gex") is not None and isinstance(metrics["call_gex"], (int, float))
        assert metrics.get("put_gex") is not None and isinstance(metrics["put_gex"], (int, float))
        assert metrics.get("call_put_ratio") is not None and isinstance(metrics["call_put_ratio"], (int, float))
        assert metrics.get("key_gamma_strike") is not None and isinstance(metrics["key_gamma_strike"], (int, float))
        assert metrics.get("updated_at") is not None and isinstance(metrics["updated_at"], str) and len(metrics["updated_at"]) > 0


def test_chart_html_rendering():
    """Verifies that /api/v1/gexdex/chart returns valid HTML dashboard containing base64 chart."""
    response = client.get(
        "/api/v1/gexdex/chart?ticker=AAPL",
        headers={"X-API-Key": TEST_API_KEY}
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GEX & DEX Options Exposure Dashboard" in response.text
    assert "data:image/png;base64," in response.text


def test_chart_png_direct_rendering():
    """Verifies that /api/v1/gexdex/chart.png returns direct PNG image binary bytes."""
    response = client.get(
        "/api/v1/gexdex/chart.png?ticker=AAPL",
        headers={"X-API-Key": TEST_API_KEY}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1000  # PNG image binary output


def test_assistant_summary_endpoint():
    """Verifies HTTP GET /api/v1/gexdex/assistant-summary returns structured JSON with spot_price, call_put_ratio, and chart image markdown tag."""
    response = client.get(
        "/api/v1/gexdex/assistant-summary?ticker=AAPL",
        headers={"X-API-Key": TEST_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert "spot_price" in data
    assert "call_put_ratio" in data
    assert "chart_png_url" in data
    assert "markdown_image" in data
    assert "![AAPL Options Chart]" in data["markdown_image"]


def test_calculate_metrics_from_raw():
    """Tests option chain processing math (net GEX, net DEX, zero GEX level)."""
    metrics = calculate_metrics_from_raw("AAPL", MOCK_RAW_PAYLOAD)
    assert metrics is not None
    assert metrics.ticker == "AAPL"
    assert metrics.spot_price == 225.50
    assert metrics.call_gex == 900000.0
    assert metrics.put_gex == 600000.0
    assert metrics.call_put_ratio == 1.5
    assert metrics.net_gex == 300000.0
    assert metrics.net_dex == 650000.0
    assert metrics.key_gamma_strike == 230.0


@patch("app.services.gexdex_service.fetch_raw_data_for_ticker")
def test_get_gexdex_data_with_mocked_common_lib(mock_fetch):
    """Tests get_gexdex_data integration with mocked fetch_raw_data_for_ticker."""
    mock_fetch.return_value = MOCK_RAW_PAYLOAD

    result = get_gexdex_data(["AAPL"])
    assert "AAPL" in result
    assert result["AAPL"].net_gex == 300000.0
    assert result["AAPL"].key_gamma_strike == 230.0
    mock_fetch.assert_called_once()

