from fastapi import FastAPI
from app.api.v1.router import api_router

app = FastAPI(
    title="Quant Multi-Skill Microservice API",
    description="24/7 Modular Quant & Options Data API Microservice running on Synology NAS via Docker.",
    version="1.0.0"
)

@app.get("/health", summary="Health Check")
def health_check():
    """
    Health check endpoint for Docker container orchestration and Synology NAS monitoring.
    """
    return {"status": "ok"}

# Register master V1 router under /api/v1
app.include_router(api_router, prefix="/api/v1")
