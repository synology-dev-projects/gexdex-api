# 🚀 Quant Multi-Skill Microservice API (`gexdex-api`)

A 24/7 high-performance, modular FastAPI microservice deployed on a Synology NAS via Docker. Designed with an extensible `APIRouter` architecture hosting quantitative trading & analysis skills (GEX/DEX Options Exposure, IBKR Streaming Data, Darkpool Flow, Oracle DB metrics) in a single container.

---

## 🏗️ Project Architecture

```
gexdex-api/
├── app/
│   ├── main.py                     # Master FastAPI application entrypoint & health check
│   ├── config.py                   # Service-wide X-API-Key security authentication
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # Master V1 APIRouter aggregating all skill routers
│   │       └── endpoints/          # 🧩 INDIVIDUAL SKILL ENDPOINTS
│   │           └── gexdex.py       # Skill 1: GEX & DEX Options Exposure endpoints (Batch-enabled)
│   └── services/                   # 🧠 BUSINESS LOGIC & COMMON-LIB ORCHESTRATION
│       └── gexdex_service.py       # ThreadPoolExecutor (max_workers=8), caching & pre-warm engine
├── .github/
│   └── workflows/
│       └── deploy.yml              # Synology self-hosted CI/CD runner deployment workflow
├── tests/                          # 🧪 PYTEST SUITE
│   └── test_main.py                # 10 unit tests covering auth, batch endpoints, and charts
├── Dockerfile                      # Container build specification (python:3.13-slim)
├── docker-compose.yml              # Synology NAS Docker Compose (Port 8090:8000)
└── README.md
```

---

## 🎯 Design Goals & High-Performance Architecture

1. **Lock-Free Concurrency & Object-Oriented Figure Rendering**:
   - Eliminates `matplotlib.pyplot` global state. Charts are rendered on isolated instances of `matplotlib.figure.Figure` + `FigureCanvasAgg` across up to 8 threads concurrently with zero locks.
2. **Batch Multi-Ticker Processing (`max_workers = 8`)**:
   - The `/assistant-summary` endpoint accepts single or comma-separated lists of tickers (e.g. `BLDP,AAOI,ADEA,INTC,SHLS`), resolving numerical metrics simultaneously across `ThreadPoolExecutor(max_workers=min(N, 8))`.
3. **Sub-5ms Background Chart Pre-Warming**:
   - Uses FastAPI `BackgroundTasks` to immediately return numerical JSON metrics to the caller (<150ms) while pre-rendering and warming `_CHART_CACHE` in the background. When the client browser requests the `<img>` binary, it is served from memory in <5ms.
4. **Resilient Fallback Generation**:
   - If an options chain is empty or fails, renders a clean, dark-mode status card directly rather than returning a 502 or broken image.

---

## 🛠️ API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Container health check | No |
| `GET` | `/api/v1/gexdex?tickers=AAPL,TSLA` | Real-time JSON GEX & DEX metrics for multiple tickers | Yes (`X-API-Key`) |
| `GET` | `/api/v1/gexdex/assistant-summary?tickers=INTC,BLDP` | AI Assistant summary with batch data & background pre-warming | Yes (`X-API-Key`) |
| `GET` | `/api/v1/gexdex/strikes?ticker=SPY` | Granular strike distribution with multi-expiration matrix & Zero Gamma Flip | Yes (`X-API-Key`) |
| `GET` | `/api/v1/gexdex/chart?ticker=AAOI` | Dark-mode HTML dashboard container | Yes (`X-API-Key`) |
| `GET` | `/api/v1/gexdex/chart.png?ticker=AAOI&format=webp` | Direct WebP or PNG binary image output | Yes (`X-API-Key`) |

### Quantitative Metrics Computed:
- **Zero Gamma Flip Point**: Exact price level calculated via linear interpolation of cumulative net gamma ($S(K) = 0$). Above this point, dealers are long gamma (volatility dampening); below, dealers are short gamma (volatility acceleration).
- **Call Wall & Put Wall**: Strikes with the largest positive Call GEX and negative Put GEX.
- **Gamma Centroid**: Weighted average strike price of aggregate options gamma.

---

## 🧪 Testing & Verification

Run the full test suite locally:
```powershell
py -3.13 -m pytest tests/ -v
```
