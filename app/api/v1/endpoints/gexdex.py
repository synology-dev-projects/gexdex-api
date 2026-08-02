import base64
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response, HTMLResponse

from app.config import get_api_key
from app.services.gexdex_service import (
    GexDexTickerMetrics,
    get_gexdex_data,
    render_gexdex_chart_image
)

router = APIRouter()


@router.get(
    "",
    response_model=Dict[str, GexDexTickerMetrics],
    summary="Get GEX/DEX Metrics for Tickers",
    dependencies=[Depends(get_api_key)]
)
def read_gexdex(
    tickers: str = Query(..., description="Comma-separated ticker list, e.g. AAPL,TSLA"),
    max_dte: int = Query(50, description="Maximum days to expiration (default: 50)"),
    strike_range: int = Query(25, description="Strike range above/below spot price (default: 25)")
):
    """
    Fetch GEX (Gamma Exposure) and DEX (Delta Exposure) options data for one or multiple stock tickers.
    Defaults to max_dte=50 and strike_range=25.
    
    Requires header `X-API-Key` or query parameter `api_key`.
    """
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid tickers provided in query parameter 'tickers'",
        )
    
    return get_gexdex_data(ticker_list, max_dte=max_dte, strike_range=strike_range)


@router.get(
    "/chart",
    summary="Get GEX/DEX Exposure Chart Dashboard",
    dependencies=[Depends(get_api_key)]
)
def get_gexdex_chart(
    ticker: str = Query("AAPL", description="Stock ticker symbol (e.g. AAPL, TSLA, NVDA)"),
    max_dte: int = Query(50, description="Maximum days to expiration (default: 50)"),
    strike_range: int = Query(25, description="Strike range above/below spot price (default: 25)"),
    format: str = Query("html", description="Output format: 'html' for interactive dashboard or 'png' for image binary")
):
    """
    Renders a high-definition dark-mode GEX & DEX Dual Horizontal Bar Chart matching the user's dashboard design.
    Defaults to max_dte=50 and strike_range=25.
    """
    img_bytes = render_gexdex_chart_image(ticker, max_dte=max_dte, strike_range=strike_range)

    if format.lower() == "png":
        return Response(content=img_bytes, media_type="image/png")

    b64_img = base64.b64encode(img_bytes).decode("utf-8")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{ticker.upper()} - GEX & DEX Options Exposure Dashboard</title>
        <style>
            body {{
                background-color: #0b0e14;
                color: #e1e6ed;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }}
            .dashboard-container {{
                background-color: #0f141d;
                border: 1px solid #1e2430;
                border-radius: 12px;
                padding: 24px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                max-width: 1200px;
                width: 100%;
            }}
            .chart-img {{
                width: 100%;
                height: auto;
                border-radius: 8px;
                display: block;
            }}
            .footer {{
                margin-top: 15px;
                color: #718096;
                font-size: 13px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="dashboard-container">
            <img class="chart-img" src="data:image/png;base64,{b64_img}" alt="{ticker.upper()} GEX/DEX Options Chart" />
            <div class="footer">
                24/7 GEX/DEX Microservice • Synology NAS Docker Engine • Real-Time Options Exposure
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get(
    "/chart.png",
    summary="Get GEX/DEX Chart PNG Image Binary",
    dependencies=[Depends(get_api_key)]
)
def get_gexdex_chart_png_direct(
    ticker: str = Query("AAPL", description="Stock ticker symbol"),
    max_dte: int = Query(50, description="Maximum days to expiration (default: 50)"),
    strike_range: int = Query(25, description="Strike range above/below spot price (default: 25)")
):
    """
    Returns direct PNG image binary (`image/png`) for embedding in markdown, Discord, Slack, or web UIs.
    Defaults to max_dte=50 and strike_range=25.
    """
    img_bytes = render_gexdex_chart_image(ticker, max_dte=max_dte, strike_range=strike_range)
    return Response(content=img_bytes, media_type="image/png")
