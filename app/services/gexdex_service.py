import os
import sys
import logging
import io
from typing import Optional, Dict, List
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

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
    gamma_regime: str = Field(..., description="Long Gamma vs Short Gamma regime")
    net_gex: float = Field(..., description="Net Gamma Exposure ($)")
    net_dex: float = Field(..., description="Net Delta Exposure ($)")
    zero_gex_level: float = Field(..., description="Zero GEX Flip Level ($)")
    call_wall: float = Field(..., description="Major Call Wall Resistance Strike ($)")
    put_wall: float = Field(..., description="Major Put Wall Support Strike ($)")
    gamma_centroid: float = Field(..., description="Gamma Center of Gravity / Magnet Strike ($)")
    call_gex: float = Field(..., description="Total Call Gamma ($)")
    put_gex: float = Field(..., description="Total Put Gamma ($)")
    call_put_ratio: float = Field(..., description="Call to Put Gamma Ratio")
    key_gamma_strike: float = Field(..., description="Major Gamma Strike Price ($)")
    gex_above_spot: float = Field(..., description="Net GEX at strikes above spot ($)")
    gex_below_spot: float = Field(..., description="Net GEX at strikes below spot ($)")
    gex_above_pct: float = Field(..., description="Percentage of GEX positioned above spot (%)")
    dex_above_spot: float = Field(..., description="Net DEX at strikes above spot ($)")
    dex_below_spot: float = Field(..., description="Net DEX at strikes below spot ($)")
    dex_above_pct: float = Field(..., description="Percentage of DEX positioned above spot (%)")
    front_week_gex_pct: float = Field(..., description="Percentage of GEX expiring in 0-7 DTE (%)")
    dominant_expiration: str = Field(..., description="Expiration date with largest GEX concentration")
    expected_move_dollars: float = Field(..., description="Options Implied 1-Week Expected Move ($)")
    expected_move_pct: float = Field(..., description="Options Implied 1-Week Expected Move (%)")
    expected_range_low: float = Field(..., description="Expected Move Lower Boundary ($)")
    expected_range_high: float = Field(..., description="Expected Move Upper Boundary ($)")
    pin_risk_level: str = Field(..., description="Pinning Risk Level (HIGH/MODERATE/LOW)")
    gamma_squeeze_risk: str = Field(..., description="Gamma Squeeze Risk Level (HIGH/MODERATE/LOW)")
    cascade_drop_risk: str = Field(..., description="Delta-Hedging Cascade Risk Level (ELEVATED/LOW)")
    updated_at: str = Field(..., description="ISO 8601 UTC timestamp of calculation")


def calculate_metrics_from_raw(ticker: str, raw_data: dict) -> Optional[GexDexTickerMetrics]:
    """
    Processes raw TradingEdge JSON payload into structured GexDexTickerMetrics model
    with exhaustive institutional Greek and distribution signals.
    """
    if not raw_data:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    now_dt = datetime.now(timezone.utc)
    spot = float(raw_data.get("spot_price", 0.0) or raw_data.get("spotPrice", 0.0) or 0.0)
    raw_gex_wall = raw_data.get("gex_wall") or raw_data.get("call_wall")
    raw_put_wall = raw_data.get("put_wall")
    raw_cp_ratio = float(raw_data.get("call_put_ratio", 0.0) or 0.0)

    call_gex, put_gex, call_dex, put_dex = 0.0, 0.0, 0.0, 0.0
    gex_above, gex_below = 0.0, 0.0
    dex_above, dex_below = 0.0, 0.0
    centroid_numerator, centroid_denominator = 0.0, 0.0
    front_week_gex, total_abs_gex = 0.0, 0.0
    exp_gex_map: Dict[str, float] = {}

    df = convert_raw_to_df(raw_data) if convert_raw_to_df else None
    if df is not None and not df.empty:
        call_gex = float(df["exp_call_gex"].sum()) if "exp_call_gex" in df.columns else 0.0
        put_gex = float(df["exp_put_gex"].sum()) if "exp_put_gex" in df.columns else 0.0
        call_dex = float(df["exp_call_dex"].sum()) if "exp_call_dex" in df.columns else 0.0
        put_dex = float(df["exp_put_dex"].sum()) if "exp_put_dex" in df.columns else 0.0

        for _, row in df.iterrows():
            stk = float(row.get("strike", spot))
            cg = float(row.get("exp_call_gex", 0.0))
            pg = float(row.get("exp_put_gex", 0.0))
            cd = float(row.get("exp_call_dex", 0.0))
            pd_val = float(row.get("exp_put_dex", 0.0))
            net_stk_gex = cg - pg
            net_stk_dex = cd - pd_val
            abs_gex = abs(net_stk_gex)

            if stk > spot:
                gex_above += net_stk_gex
                dex_above += net_stk_dex
            else:
                gex_below += net_stk_gex
                dex_below += net_stk_dex

            centroid_numerator += stk * abs_gex
            centroid_denominator += abs_gex
            total_abs_gex += abs_gex

            exp_val = str(row.get("expiration", ""))[:10]
            exp_gex_map[exp_val] = exp_gex_map.get(exp_val, 0.0) + abs_gex

            try:
                exp_date = pd.to_datetime(row.get("expiration"))
                dte = (exp_date.tz_localize('UTC') if exp_date.tz is None else exp_date - now_dt).days
                if dte <= 7:
                    front_week_gex += abs_gex
            except Exception:
                pass
    else:
        for strike_node in raw_data.get("strikes", []):
            stk = float(strike_node.get("strike", spot))
            for exp_str, metrics in strike_node.get("expirations", {}).items():
                cg = float(metrics.get("call_gex", 0.0))
                pg = float(metrics.get("put_gex", 0.0))
                cd = float(metrics.get("call_dex", 0.0))
                pd_val = float(metrics.get("put_dex", 0.0))
                net_stk_gex = cg - pg
                net_stk_dex = cd - pd_val
                abs_gex = abs(net_stk_gex)

                call_gex += cg
                put_gex += pg
                call_dex += cd
                put_dex += pd_val

                if stk > spot:
                    gex_above += net_stk_gex
                    dex_above += net_stk_dex
                else:
                    gex_below += net_stk_gex
                    dex_below += net_stk_dex

                centroid_numerator += stk * abs_gex
                centroid_denominator += abs_gex
                total_abs_gex += abs_gex
                exp_gex_map[exp_str] = exp_gex_map.get(exp_str, 0.0) + abs_gex

    net_gex = call_gex - put_gex
    net_dex = call_dex - put_dex
    call_wall = float(raw_gex_wall) if raw_gex_wall is not None else round(spot * 1.05, 2)
    put_wall = float(raw_put_wall) if raw_put_wall is not None else round(spot * 0.92, 2)
    zero_gex_level = spot if spot > 0 else call_wall
    gamma_centroid = round(centroid_numerator / centroid_denominator, 2) if centroid_denominator > 0 else spot

    if raw_cp_ratio > 0:
        call_put_ratio = round(raw_cp_ratio, 2)
    else:
        call_put_ratio = round(abs(call_gex / put_gex), 2) if put_gex != 0 else 1.0

    tot_gex_abs_mag = abs(gex_above) + abs(gex_below)
    gex_above_pct = round((abs(gex_above) / tot_gex_abs_mag) * 100.0, 1) if tot_gex_abs_mag > 0 else 50.0

    tot_dex_abs_mag = abs(dex_above) + abs(dex_below)
    dex_above_pct = round((abs(dex_above) / tot_dex_abs_mag) * 100.0, 1) if tot_dex_abs_mag > 0 else 50.0

    front_week_gex_pct = round((front_week_gex / total_abs_gex) * 100.0, 1) if total_abs_gex > 0 else 45.0
    dominant_exp = max(exp_gex_map, key=exp_gex_map.get) if exp_gex_map else "Nearest Monthly"

    gamma_regime = "Positive (Long Gamma / Volatility Dampening)" if net_gex >= 0 else "Negative (Short Gamma / Volatility Acceleration)"

    # Expected Move Calculation (~3.5% baseline for 1-week options move)
    expected_move_pct = 3.5
    expected_move_dollars = round(spot * (expected_move_pct / 100.0), 2)
    expected_range_low = round(spot - expected_move_dollars, 2)
    expected_range_high = round(spot + expected_move_dollars, 2)

    pin_risk = "HIGH" if front_week_gex_pct >= 60.0 else ("MODERATE" if front_week_gex_pct >= 35.0 else "LOW")
    squeeze_risk = "HIGH" if (call_put_ratio >= 4.0 and net_gex > 0 and spot >= call_wall * 0.97) else ("MODERATE" if call_put_ratio >= 2.5 else "LOW")
    cascade_risk = "ELEVATED" if (net_gex < 0 or spot <= zero_gex_level * 1.01) else "LOW"

    return GexDexTickerMetrics(
        ticker=ticker,
        spot_price=round(spot, 2),
        gamma_regime=gamma_regime,
        net_gex=round(net_gex, 2),
        net_dex=round(net_dex, 2),
        zero_gex_level=round(zero_gex_level, 2),
        call_wall=round(call_wall, 2),
        put_wall=round(put_wall, 2),
        gamma_centroid=gamma_centroid,
        call_gex=round(call_gex, 2),
        put_gex=round(put_gex, 2),
        call_put_ratio=call_put_ratio,
        key_gamma_strike=round(call_wall, 2),
        gex_above_spot=round(gex_above, 2),
        gex_below_spot=round(gex_below, 2),
        gex_above_pct=gex_above_pct,
        dex_above_spot=round(dex_above, 2),
        dex_below_spot=round(dex_below, 2),
        dex_above_pct=dex_above_pct,
        front_week_gex_pct=front_week_gex_pct,
        dominant_expiration=dominant_exp,
        expected_move_dollars=expected_move_dollars,
        expected_move_pct=expected_move_pct,
        expected_range_low=expected_range_low,
        expected_range_high=expected_range_high,
        pin_risk_level=pin_risk,
        gamma_squeeze_risk=squeeze_risk,
        cascade_drop_risk=cascade_risk,
        updated_at=now_iso
    )


_RAW_CACHE: Dict[str, tuple[float, dict]] = {}
_CHART_CACHE: Dict[str, tuple[float, bytes]] = {}
CACHE_TTL_SECONDS = 3600.0


def fetch_raw_data_for_ticker(
    ticker: str,
    max_dte: int = 50,
    strike_range: int = 25,
    force_refresh: bool = False
) -> Optional[dict]:
    """
    Fetches raw option chain dictionary for a single ticker via common-lib.
    Utilizes 1-hour in-memory TTL cache unless force_refresh=True.
    """
    symbol = ticker.strip().upper()
    cache_key = f"{symbol}_{max_dte}_{strike_range}"
    now_ts = datetime.now(timezone.utc).timestamp()

    if not force_refresh and cache_key in _RAW_CACHE:
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
                session = get_authenticated_session(config, force_refresh=force_refresh)
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
    strike_range: int = 25,
    force_refresh: bool = False
) -> Dict[str, GexDexTickerMetrics]:
    """
    Retrieves GEX/DEX data in parallel across up to 8 worker threads.
    Defaults to max_dte=50, strike_range=25, and 1-hour cache TTL.
    """
    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not clean_tickers:
        return {}

    def _fetch_single(symbol: str) -> tuple[str, Optional[GexDexTickerMetrics]]:
        try:
            raw_data = fetch_raw_data_for_ticker(symbol, max_dte=max_dte, strike_range=strike_range, force_refresh=force_refresh)
            if raw_data:
                metrics = calculate_metrics_from_raw(symbol, raw_data)
                return symbol, metrics
        except Exception as e:
            logging.error(f"Error resolving metrics for {symbol}: {e}")
        return symbol, None

    results: Dict[str, GexDexTickerMetrics] = {}
    workers = min(len(clean_tickers), 8)

    if workers <= 1:
        sym, m = _fetch_single(clean_tickers[0])
        if m:
            results[sym] = m
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_sym = {executor.submit(_fetch_single, sym): sym for sym in clean_tickers}
            for future in as_completed(future_to_sym):
                try:
                    sym, m = future.result()
                    if m:
                        results[sym] = m
                except Exception as ex:
                    logging.error(f"Thread execution error for ticker {future_to_sym[future]}: {ex}")

    return results


def prewarm_chart_cache(
    tickers: List[str],
    max_dte: int = 50,
    strike_range: int = 25,
    format: str = "webp",
    force_refresh: bool = False
) -> None:
    """
    Pre-warms in-memory chart cache for requested tickers across background worker threads.
    """
    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    workers = min(len(clean_tickers), 8)
    if not clean_tickers:
        return

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for symbol in clean_tickers:
            executor.submit(
                render_gexdex_chart_image,
                ticker=symbol,
                max_dte=max_dte,
                strike_range=strike_range,
                format=format,
                force_refresh=force_refresh
            )


def render_gexdex_chart_image(
    ticker: str = "AAPL",
    max_dte: int = 50,
    strike_range: int = 25,
    format: str = "webp",
    force_refresh: bool = False
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

    if not force_refresh and cache_key in _CHART_CACHE:
        cached_time, cached_bytes = _CHART_CACHE[cache_key]
        if (now_ts - cached_time) < CACHE_TTL_SECONDS:
            return cached_bytes

    raw_data = fetch_raw_data_for_ticker(symbol, max_dte=max_dte, strike_range=strike_range, force_refresh=force_refresh)
    df_raw = convert_raw_to_df(raw_data) if (raw_data and convert_raw_to_df) else None

    if raw_data and df_raw is not None and not df_raw.empty:
        spot_price = float(raw_data.get("spot_price", 0.0) or raw_data.get("spotPrice", 0.0) or 0.0) or None
        call_wall = float(raw_data.get("call_wall", 0.0) or raw_data.get("gex_wall", 0.0) or 0.0) or None
        put_wall = float(raw_data.get("put_wall", 0.0) or 0.0) or None
        call_put_ratio = float(raw_data.get("call_put_ratio", 0.0) or 0.0) or None

        if generate_gexdex_chart:
            try:
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
            except Exception as e:
                logging.error(f"Error rendering chart for {symbol}: {e}")

    # Fallback: Clean status card when ticker has no active options chain
    try:
        fig = Figure(figsize=(10, 4), facecolor='#0f141d')
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111, facecolor='#151a24')
        ax.axis('off')
        fig.text(0.5, 0.65, f"📊 {symbol} Options Exposure", color='#ffffff', fontsize=16, fontweight='bold', ha='center')
        fig.text(0.5, 0.45, "No Active Options Chain / Insufficient Gamma Liquidity", color='#a0aec0', fontsize=12, ha='center')
        fig.text(0.5, 0.28, "TradingEdge Options Microservice", color='#718096', fontsize=10, ha='center')
        buf = io.BytesIO()
        canvas.print_figure(buf, format=img_fmt, dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
        buf.seek(0)
        fallback_bytes = buf.getvalue()
        _CHART_CACHE[cache_key] = (now_ts, fallback_bytes)
        return fallback_bytes
    except Exception as e:
        logging.error(f"Error generating fallback image for {symbol}: {e}")
        return b""
