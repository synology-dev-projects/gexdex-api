# ⚠️ DEPRECATED & ARCHIVED: gexdex-api

**Status**: **ARCHIVED / DECOMMISSIONED**  
**Decommission Date**: September 2026  
**Replacement Engine**: In-Process Gateway Engine inside `quant-pwa/gateway/app/engine/service.py`  
**Live Endpoint**: `http://192.168.1.68:8095/api/v1/gexdex` (`quant-gateway-prod`) and `:8096` (`quant-gateway-dev`)

---

## 1. Reason for Deprecation & Archival

1. **Elimination of Multi-Hop Latency**:  
   Previously, requests to `quant-pwa`'s Gateway had to jump across Docker container networks via HTTP to `gexdex-api-prod:8000`, adding 5–15ms per ticker and creating connection pool overhead.
2. **Resource Reclaim on Synology NAS**:  
   Running a standalone microservice container for `gexdex-api` consumed ~300MB RAM. The options microstructure calculation engine has been consolidated directly in-process into `quant-pwa/gateway/app/engine/service.py`, saving ~300MB RAM and font-cache startup delays.
3. **Unified Microstructure Gateway**:  
   All options microstructure calculations (GEX, DEX, strikes, profiles, 0DTE/Monthly heatmaps, regime shifts) are now served directly by `quant-gateway-prod` (port `8095`) and `quant-gateway-dev` (port `8096`).
4. **Zero-Token Client-Side Charting**:  
   Matplotlib server-side chart rendering has been replaced with client-side HTML5 Canvas rendering in `quant-pwa`, removing heavy plotting libraries from the container image.

---

## 2. Migration Guide for Clients & Pipelines

### Internal Pipelines & Scripts
Any script previously calling `http://gexdex-api-prod:8000/api/v1/gexdex` or `http://192.168.1.68:8090/api/v1/gexdex` should now call:
- **Base URL**: `http://192.168.1.68:8095` (Prod) or `http://192.168.1.68:8096` (Dev)
- **Endpoint**: `GET /api/v1/gexdex?symbol={ticker}`
- **Authentication**: `X-API-Key: {GEXDEX_API_KEY}`

### Example Python Caller
```python
import os
import requests

GEXDEX_API_URL = os.getenv("GEXDEX_API_URL", "http://192.168.1.68:8095")
GEXDEX_API_KEY = os.getenv("GEXDEX_API_KEY", "YOUR_SECRET_API_KEY")

response = requests.get(
    f"{GEXDEX_API_URL}/api/v1/gexdex",
    params={"symbol": "SPY"},
    headers={"X-API-Key": GEXDEX_API_KEY},
    timeout=30
)
data = response.json()
```

### Docker Status on Synology NAS
The container `gexdex-api-prod` (host port 8090) has been stopped. The service will not be restarted.
