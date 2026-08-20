import base64
from typing import Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import Response, HTMLResponse

from app.config import get_api_key
from app.services.gexdex_service import (
    GexDexTickerMetrics,
    StrikeDistributionResponse,
    get_gexdex_data,
    get_strike_distribution,
    render_gexdex_chart_image,
    prewarm_chart_cache
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
    "/strikes",
    response_model=StrikeDistributionResponse,
    summary="Get Granular Strike-Level GEX/DEX Distribution for Client-Side Charts",
    dependencies=[Depends(get_api_key)]
)
def read_gexdex_strikes(
    ticker: str = Query("AAPL", description="Stock ticker symbol (e.g. AAPL, TSLA, NVDA)"),
    max_dte: int = Query(50, description="Maximum days to expiration (default: 50)"),
    strike_range: int = Query(25, description="Strike range above/below spot price (default: 25)"),
    force_refresh: bool = Query(False, description="Bypass 1-hour cache and force live data fetch")
):
    """
    Returns granular strike-by-strike and expiration-by-expiration GEX & DEX values (~2-4 KB JSON).
    Enables zero-latency, 100% reliable interactive HTML5 Canvas chart rendering on mobile client.
    """
    clean_ticker = ticker.strip().upper()
    return get_strike_distribution(
        ticker=clean_ticker,
        max_dte=max_dte,
        strike_range=strike_range,
        force_refresh=force_refresh
    )


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
    summary="Get GEX/DEX Chart Image Binary",
    dependencies=[Depends(get_api_key)]
)
def get_gexdex_chart_png_direct(
    ticker: str = Query("AAPL", description="Stock ticker symbol"),
    max_dte: int = Query(50, description="Maximum days to expiration (default: 50)"),
    strike_range: int = Query(25, description="Strike range above/below spot price (default: 25)"),
    format: str = Query("png", description="Image format: 'png' or 'webp'"),
    force_refresh: bool = Query(False, description="Bypass 1-hour cache and force live chart re-render")
):
    """
    Returns direct image binary (PNG or WebP) for embedding in markdown, Discord, or web UIs.
    Defaults to format='png'.
    """
    img_fmt = format.lower() if format else "png"
    img_bytes = render_gexdex_chart_image(
        ticker, max_dte=max_dte, strike_range=strike_range, format=img_fmt, force_refresh=force_refresh
    )
    media_type = "image/webp" if img_fmt == "webp" else "image/png"
    return Response(content=img_bytes, media_type=media_type)


@router.get(
    "/assistant-summary",
    summary="Get Options Exposure Summary & Chart Image Link for AI Assistants",
    dependencies=[Depends(get_api_key)]
)
def get_gexdex_assistant_summary(
    background_tasks: BackgroundTasks,
    tickers: Optional[str] = Query(None, description="Single ticker or comma-separated list (e.g. AAPL,INTC,SPY)"),
    ticker: Optional[str] = Query(None, description="Legacy single ticker parameter"),
    max_dte: int = Query(50, description="Maximum days to expiration (default: 50)"),
    strike_range: int = Query(25, description="Strike range above/below spot price (default: 25)"),
    force_refresh: bool = Query(False, description="Bypass 1-hour cache and force live data fetch")
):
    """
    Designed specifically for AI Assistants (Google Gemini, Custom GPTs).
    Fetches real-time GEX/DEX options exposure metrics for single or multiple tickers in parallel.
    Pre-warms chart caches in background worker threads for sub-5ms image loading.
    """
    raw_param = tickers or ticker or "AAPL"
    ticker_list = [t.strip().upper() for t in raw_param.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid tickers provided in 'tickers' or 'ticker' query parameter."
        )

    data = get_gexdex_data(ticker_list, max_dte=max_dte, strike_range=strike_range, force_refresh=force_refresh)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No options exposure data found for tickers: {', '.join(ticker_list)}"
        )

    # Pre-warm chart cache in background threads for instant image retrieval
    background_tasks.add_task(
        prewarm_chart_cache,
        tickers=list(data.keys()),
        max_dte=max_dte,
        strike_range=strike_range,
        format="webp",
        force_refresh=force_refresh
    )

    refresh_param = "&force_refresh=true" if force_refresh else ""
    ticker_results = {}
    cards = []
    ai_contexts = []

    for sym, metrics in data.items():
        chart_png_url = f"/api/v1/gexdex/chart.png?ticker={sym}&max_dte={max_dte}&strike_range={strike_range}&format=webp{refresh_param}"
        item = metrics.model_dump()
        item["chart_png_url"] = chart_png_url
        item["markdown_image"] = f"![{sym} Options Chart]({chart_png_url})"
        
        # Attach granular strike distribution for client-side Canvas rendering (hits RAM cache <0.1ms)
        strike_dist = get_strike_distribution(sym, max_dte=max_dte, strike_range=strike_range, force_refresh=force_refresh)
        item["strike_distribution"] = strike_dist.model_dump()
        
        ticker_results[sym] = item

        ctx = f"Ticker {sym}: Spot ${item.get('spot_price')}, Call Wall ${item.get('call_wall')}, Put Wall ${item.get('put_wall')}, GEX Above: {item.get('gex_above_pct')}%, Front-Week GEX: {item.get('front_week_gex_pct')}%, Regime: {item.get('gamma_regime')}"
        ai_contexts.append(ctx)

    first_sym = ticker_list[0] if ticker_list[0] in ticker_results else list(ticker_results.keys())[0]
    primary_result = dict(ticker_results[first_sym])

    # Add batch metadata
    primary_result["count"] = len(ticker_results)
    primary_result["tickers"] = list(ticker_results.keys())
    primary_result["batch_data"] = ticker_results
    primary_result["combined_context"] = "; ".join(ai_contexts)

    return primary_result

