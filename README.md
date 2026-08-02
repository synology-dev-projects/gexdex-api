# 🚀 Quant Multi-Skill Microservice API

A 24/7 high-performance, modular FastAPI microservice deployed on a Synology NAS via Docker. Designed with an extensible `APIRouter` architecture so you can host multiple quantitative trading & analysis skills (GEX/DEX Options Exposure, IBKR Streaming Data, Darkpool Flow, Oracle DB metrics) in a single container.

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
│   │           └── gexdex.py       # Skill 1: GEX & DEX Options Exposure endpoints
│   └── services/                   # 🧠 BUSINESS LOGIC & COMMON-LIB ORCHESTRATION
│       └── gexdex_service.py       # End-to-end workflow orchestrator & data transformer
├── .github/
│   └── workflows/
│       └── deploy.yml              # Synology self-hosted CI/CD runner deployment workflow
├── .gemini/skills/                 # 🤖 GEMINI AGENT SKILL DEFINITIONS
│   └── gexdex-api/SKILL.md         # Skill 1 Markdown instructions for AI agents
├── tests/                          # 🧪 PYTEST SUITE
│   └── test_main.py                # 9 unit tests covering authentication & charts
├── Dockerfile                      # Container build specification (python:3.13-slim)
├── docker-compose.yml              # Synology NAS Docker Compose (Port 8090:8000)
├── verify.sh                       # Local & CI/CD runner verification test script
└── requirements.txt                # Microservice dependencies & editable common-lib link
```

---

## 🧠 Architectural Design Principles

### Separation of Concerns: Orchestrator vs. Pure Renderer
This project cleanly separates data orchestration from graphics rendering:

* **`render_gexdex_chart_image`** (*in `app/services/gexdex_service.py`*):
  * **Workflow Orchestrator:** Handles authentication, API network calls, parsing JSON responses into pandas DataFrames, error handling, and offline fallback fallbacks.
* **`generate_gexdex_chart`** (*in `common-lib`*):
  * **Pure Graphics Engine:** Receives a pandas DataFrame and renders a dark-mode horizontal bar chart PNG. Has zero network or API dependencies.

---

## 🚀 How to Add New Skills

Adding a new skill (e.g. `ibkr` or `darkpool`) takes only 2 simple steps:

### Step 1: Create Endpoint File (`app/api/v1/endpoints/new_skill.py`)
```python
from fastapi import APIRouter, Depends
from app.config import get_api_key

router = APIRouter()

@router.get("", dependencies=[Depends(get_api_key)])
def read_new_skill_data():
    return {"status": "ok", "data": "Your new quant metrics"}
```

### Step 2: Register in Master Router (`app/api/v1/router.py`)
```python
from app.api.v1.endpoints import gexdex, new_skill

api_router.include_router(gexdex.router, prefix="/gexdex", tags=["GEX/DEX"])
api_router.include_router(new_skill.router, prefix="/new_skill", tags=["New Skill"])
```

---

## 🛠️ Included Skill 1: GEX/DEX Options Exposure

### API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Container health check | No |
| `GET` | `/api/v1/gexdex?tickers=AAPL,TSLA&max_dte=50&strike_range=25` | Real-time JSON GEX & DEX metrics | Yes (`X-API-Key`) |
| `GET` | `/api/v1/gexdex/chart?ticker=AAOI` | Dark-mode HTML dashboard container | Yes (`X-API-Key`) |
| `GET` | `/api/v1/gexdex/chart.png?ticker=AAOI` | Direct PNG binary image output | Yes (`X-API-Key`) |

### Key Exposure Features
* **Dynamic Scale Adjustment:** Automatically scales X-axis units between **`M`** (Millions for mid-caps like `AAOI`, `GLXY`) and **`B`** (Billions for mega-caps like `TSLA`, `AAPL`).
* **Double-Sided Layout:** Calls extend to the left (-X), Puts extend to the right (+X) across a centered zero axis.
* **Key Levels Overlay:** Highlights Spot Price (blue), Call Wall (teal), and Put Wall (pink).

---

## 🔄 Synology NAS CI/CD Deployment

The repository is integrated with a self-hosted GitHub Actions runner running directly on the Synology NAS (`/volume2/docker/develop/gexdex-api`):

1. **Pushing to `develop`:** Triggers the pipeline, syncs project files, updates the virtualenv, and runs `./verify.sh` unit tests (**9/9 tests**).
2. **Auto-Promotion to `master`:** Upon test passage, the pipeline automatically merges `develop` into `master` (`[Skip CI]`).
3. **Container Execution:** Spins up the container on port **`8090`** (`docker-compose up -d`).

---

## 🧪 Local Testing & Verification

Run the full pytest suite locally before committing:

```bash
cd gexdex-api
python -m pytest tests/ -v
```
