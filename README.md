# Quant Multi-Skill Microservice API

A modular, 24/7 FastAPI microservice designed to run on a Synology NAS via Docker. Built using an extensible APIRouter architecture so you can host multiple quantitative analysis skills (e.g. GEX/DEX options, IBKR streaming data, Darkpool flow) in a single container.

---

## 🏗️ Project Architecture

```
gexdex-api/
├── app/
│   ├── main.py                     # Master FastAPI application & health check
│   ├── config.py                   # Service-wide API key authentication
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # Master V1 router aggregating all skills
│   │       └── endpoints/          # 🧩 INDIVIDUAL SKILL ENDPOINTS
│   │           └── gexdex.py       # Skill 1: GEX & DEX Options Exposure
│   └── services/                   # 🧠 BUSINESS LOGIC & COMMON-LIB INTEGRATION
│       └── gexdex_service.py       # Options exposure math & chart rendering
├── .gemini/skills/                 # 🤖 GEMINI AGENT SKILL DEFINITIONS
│   └── gexdex-api/SKILL.md         # Skill 1 Markdown instructions
├── tests/                          # 🧪 PYTEST SUITE
│   └── test_main.py                # 9 unit tests covering authentication & charts
├── Dockerfile                      # Container build specification (python:3.11-slim)
├── docker-compose.yml              # Synology NAS Docker Compose (Port 8090:8000)
└── requirements.txt                # Container dependencies
```

---

## 🚀 How to Add New Skills

Adding a new skill (e.g., `ibkr` or `darkpool`) takes only 2 simple steps:

1. **Create Endpoint File (`app/api/v1/endpoints/new_skill.py`):**
   ```python
   from fastapi import APIRouter, Depends
   from app.config import get_api_key

   router = APIRouter()

   @router.get("", dependencies=[Depends(get_api_key)])
   def read_new_skill_data():
       return {"data": "Your new quant metrics"}
   ```

2. **Register in Router (`app/api/v1/router.py`):**
   ```python
   from app.api.v1.endpoints import gexdex, new_skill

   api_router.include_router(gexdex.router, prefix="/gexdex", tags=["GEX/DEX"])
   api_router.include_router(new_skill.router, prefix="/new_skill", tags=["New Skill"])
   ```

---

## 🛠️ Included Skill 1: GEX/DEX Options Exposure

### Endpoints
* **`GET /health`** - Container health check (No auth).
* **`GET /api/v1/gexdex?tickers=AAPL,TSLA&max_dte=50&strike_range=25`** - Real-time JSON GEX & DEX metrics.
* **`GET /api/v1/gexdex/chart?ticker=TSLA&format=html`** - Dark-mode double-sided horizontal bar dashboard.
* **`GET /api/v1/gexdex/chart.png?ticker=TSLA`** - Direct PNG binary for embedding in Discord/Slack/Markdown.

---

## 🧪 Testing

Run pytest suite across all skills:

```bash
python -m pytest tests/ -v
```
