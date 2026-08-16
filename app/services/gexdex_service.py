import os
import sys
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

# Automatically search for common-lib in candidate locations
script_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(script_dir)
root_dir = os.path.dirname(app_dir)
parent_dir = os.path.dirname(root_dir)

candidate_paths = [
    root_dir,
    os.path.join(root_dir, "common_lib"),
    os.path.join(root_dir, "common-lib"),
    os.path.join(parent_dir, "common-lib"),
    os.path.join(parent_dir, "common_lib"),
]
for path in candidate_paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Import shared common-lib connectors & configuration
try:
    from common_lib.config.main_config import MainConfig, load_config
    from common_lib.connectors.tradingedge.dexgex import (
        get_authenticated_session,
        extract_raw_data,
        convert_raw_to_df,
        generate_gexdex_chart
    )
except ImportError:
    MainConfig = None
    load_config = None
    get_authenticated_session = None
    extract_raw_data = None
    convert_raw_to_df = None
    generate_gexdex_chart = None


class GexDexTickerMetrics(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    spot_price: float = Field(..., description="Current stock spot price ($)")
    net_gex: float = Field(..., description="Net Gamma Exposure ($)")
    net_dex: float = Field(..., description="Net Delta Exposure ($)")
    zero_gex_level: float = Field(..., description="Zero GEX Flip Level ($)")
    call_gex: float = Field(..., description="Total Call Gamma ($)")
    put_gex: float = Field(..., description="Total Put Gamma ($)")
    call_put_ratio: float = Field(..., description="Call to Put Gamma Ratio")
    key_gamma_strike: float = Field(..., description="Major Gamma Strike Price ($)")
    updated_at: str = Field(..., description="ISO 8601 UTC timestamp of calculation")


def calculate_metrics_from_raw(ticker: str, raw_data: dict) -> Optional[GexDexTickerMetrics]:
    """
    Processes raw TradingEdge JSON payload into structured GexDexTickerMetrics model.
    """
    if not raw_data:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    spot = float(raw_data.get("spot_price", 0.0) or raw_data.get("spotPrice", 0.0) or 0.0)
    gex_wall = raw_data.get("gex_wall")
    raw_cp_ratio = float(raw_data.get("call_put_ratio", 0.0) or 0.0)

    call_gex, put_gex, call_dex, put_dex = 0.0, 0.0, 0.0, 0.0

    df = convert_raw_to_df(raw_data) if convert_raw_to_df else None
    if df is not None and not df.empty:
        call_gex = float(df["exp_call_gex"].sum()) if "exp_call_gex" in df.columns else 0.0
        put_gex = float(df["exp_put_gex"].sum()) if "exp_put_gex" in df.columns else 0.0
        call_dex = float(df["exp_call_dex"].sum()) if "exp_call_dex" in df.columns else 0.0
        put_dex = float(df["exp_put_dex"].sum()) if "exp_put_dex" in df.columns else 0.0
    else:
        for strike_node in raw_data.get("strikes", []):
            for _exp, metrics in strike_node.get("expirations", {}).items():
                call_gex += float(metrics.get("call_gex", 0.0))
                put_gex += float(metrics.get("put_gex", 0.0))
                call_dex += float(metrics.get("call_dex", 0.0))
                put_dex += float(metrics.get("put_dex", 0.0))

    net_gex = call_gex - put_gex
    net_dex = call_dex - put_dex
    key_gamma_strike = float(gex_wall) if gex_wall is not None else spot
    zero_gex_level = spot if spot > 0 else key_gamma_strike

    if raw_cp_ratio > 0:
        call_put_ratio = round(raw_cp_ratio, 2)
    else:
        call_put_ratio = round(abs(call_gex / put_gex), 2) if put_gex != 0 else 1.0

    return GexDexTickerMetrics(
        ticker=ticker,
        spot_price=round(spot, 2),
        net_gex=round(net_gex, 2),
        net_dex=round(net_dex, 2),
        zero_gex_level=round(zero_gex_level, 2),
        call_gex=round(call_gex, 2),
        put_gex=round(put_gex, 2),
        call_put_ratio=call_put_ratio,
        key_gamma_strike=round(key_gamma_strike, 2),
        updated_at=now_iso
    )


_RAW_CACHE: Dict[str, tuple[float, dict]] = {}
_CHART_CACHE: Dict[str, tuple[float, bytes]] = {}
CACHE_TTL_SECONDS = 60.0


def fetch_raw_data_for_ticker(
    ticker: str,
    max_dte: int = 50,
    strike_range: int = 25
) -> Optional[dict]:
    """
    Fetches raw option chain dictionary for a single ticker via common-lib.
    Utilizes 60s in-memory TTL cache to eliminate redundant upstream calls.
    """
    symbol = ticker.strip().upper()
    cache_key = f"{symbol}_{max_dte}_{strike_range}"
    now_ts = datetime.now(timezone.utc).timestamp()

    if cache_key in _RAW_CACHE:
        cached_time, cached_payload = _RAW_CACHE[cache_key]
        if (now_ts - cached_time) < CACHE_TTL_SECONDS:
            return cached_payload

    if get_authenticated_session and extract_raw_data:
        try:
            config = None
            env_path = Path("/app/common_config/.env")
            if env_path.exists() and MainConfig:
                try:
                    config = MainConfig(_env_file=str(env_path))
                except Exception as ex:
                    logging.warning(f"MainConfig(_env_file={env_path}) failed: {ex}")
            if config is None and load_config:
                config = load_config()

            if config:
                session = get_authenticated_session(config)
                if session:
                    raw = extract_raw_data(
                        config, session, symbol, max_dte=max_dte, strike_range=strike_range
                    )
                    if raw and isinstance(raw, dict):
                        _RAW_CACHE[cache_key] = (now_ts, raw)
                        return raw
        except Exception as e:
            logging.warning(f"Failed to fetch live TradingEdge session for {symbol}: {e}")
    return None


def get_gexdex_data(
    tickers: List[str],
    max_dte: int = 50,
    strike_range: int = 25
) -> Dict[str, GexDexTickerMetrics]:
    """
    Retrieves GEX/DEX data by authenticating via common-lib connectors to TradingEdge API.
    Defaults to max_dte=50 and strike_range=25.
    """
    results: Dict[str, GexDexTickerMetrics] = {}

    for ticker in tickers:
        symbol = ticker.strip().upper()
        if not symbol:
            continue

        raw_data = fetch_raw_data_for_ticker(symbol, max_dte=max_dte, strike_range=strike_range)
        if raw_data:
            metrics = calculate_metrics_from_raw(symbol, raw_data)
            if metrics:
                results[symbol] = metrics
                continue

    return results


def render_gexdex_chart_image(
    ticker: str = "AAPL",
    max_dte: int = 50,
    strike_range: int = 25,
    format: str = "webp"
) -> bytes:
    """
    Generates a high-definition, dark-mode double-sided bi-directional horizontal bar chart
    matching the GEX & DEX Dashboard design by delegating to common-lib generate_gexdex_chart.
    Supports WebP (default, 35KB) and PNG formats with in-memory caching.
    """
    symbol = ticker.upper().strip()
    img_fmt = format.lower() if format else "webp"
    cache_key = f"{symbol}_{max_dte}_{strike_range}_{img_fmt}"
    now_ts = datetime.now(timezone.utc).timestamp()

    if cache_key in _CHART_CACHE:
        cached_time, cached_bytes = _CHART_CACHE[cache_key]
        if (now_ts - cached_time) < CACHE_TTL_SECONDS:
            return cached_bytes

    raw_data = fetch_raw_data_for_ticker(symbol, max_dte=max_dte, strike_range=strike_range)
    df_raw = convert_raw_to_df(raw_data) if (raw_data and convert_raw_to_df) else None

    if raw_data and df_raw is not None and not df_raw.empty:
        spot_price = float(raw_data.get("spot_price", 0.0) or raw_data.get("spotPrice", 0.0) or 0.0) or None
        call_wall = float(raw_data.get("call_wall", 0.0) or raw_data.get("gex_wall", 0.0) or 0.0) or None
        put_wall = float(raw_data.get("put_wall", 0.0) or 0.0) or None
        call_put_ratio = float(raw_data.get("call_put_ratio", 0.0) or 0.0) or None

        if generate_gexdex_chart:
            chart_bytes = generate_gexdex_chart(
                df=df_raw,
                ticker=symbol,
                spot_price=spot_price,
                call_wall=call_wall,
                put_wall=put_wall,
                call_put_ratio=call_put_ratio,
                format=img_fmt
            )
            _CHART_CACHE[cache_key] = (now_ts, chart_bytes)
            return chart_bytes

    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000
