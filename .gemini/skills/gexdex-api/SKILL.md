---
name: gexdex-api
description: Fetch and analyze Gamma Exposure (GEX) and Delta Exposure (DEX) options data for single or multiple stock tickers. Defaults: max_dte=50, strike_range=25. Use when asked for GEX, DEX, options exposure, zero GEX flip level, key gamma strikes, or GEX/DEX chart visualization.
---

# GEX/DEX Options Data & Chart Skill

Use this skill when the user asks for Gamma Exposure (GEX), Delta Exposure (DEX), Zero GEX flip levels, or visual GEX/DEX options charts for stock tickers.

## Default Parameters
* **`max_dte`**: Defaults to `50` (Maximum Days to Expiration).
* **`strike_range`**: Defaults to `25` (Strikes above/below spot price).

---

## 1. Execute API Query (JSON Data)

To retrieve real-time options exposure metrics:

```bash
curl -s -X GET "https://gexdex.yourname.synology.me/api/v1/gexdex?tickers={TICKERS}&max_dte=50&strike_range=25" \
  -H "X-API-Key: YOUR_SECRET_API_KEY_HERE"
```

Replace `{TICKERS}` with a comma-separated list of stock tickers (e.g., `AAPL,TSLA,NVDA`).

---

## 2. Execute Chart Endpoint (Visual Graph)

To fetch or embed the **GEX & DEX Options Exposure Chart** (bi-directional double-sided horizontal bar chart across zero axis):

```bash
# Fetch PNG Image Binary directly for rendering:
curl -s -X GET "https://gexdex.yourname.synology.me/api/v1/gexdex/chart.png?ticker={TICKER}&max_dte=50&strike_range=25" \
  -H "X-API-Key: YOUR_SECRET_API_KEY_HERE" -o gexdex_chart.png
```

Or open the interactive HTML Dashboard at `https://gexdex.yourname.synology.me/api/v1/gexdex/chart?ticker={TICKER}&max_dte=50&strike_range=25&api_key=YOUR_SECRET_API_KEY_HERE`.

---

## 3. Response Formatting

Format JSON data into a clean GitHub-Flavored Markdown summary table:

| Ticker | Net GEX ($) | Net DEX ($) | Zero GEX Flip ($) | Call GEX ($) | Put GEX ($) | Key Gamma Strike ($) | Updated At (UTC) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AAPL** | +$1,250,000.50 | +$850,200.00 | $225.50 | +$3,400,000.00 | -$2,149,999.50 | $230.00 | 2026-08-01T17:50:00Z |
| **TSLA** | -$450,000.25 | +$1,200,300.75 | $215.00 | +$3,400,000.00 | -$2,149,999.50 | $220.00 | 2026-08-01T17:50:00Z |

---

## 4. Market Maker Exposure Analysis

When presenting results to the user:
1. **Net GEX > 0 (Positive Gamma):** Market makers suppress price volatility; expect range-bound behavior.
2. **Net GEX < 0 (Negative Gamma):** Market makers amplify price momentum; expect breakout / volatile conditions.
3. **Zero GEX Flip Level:** Critical support/resistance boundary between positive and negative gamma regimes.
