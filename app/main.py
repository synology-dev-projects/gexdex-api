from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

app = FastAPI(
    title="Quant GEX/DEX Options Exposure API",
    description="Real-time options Gamma Exposure (GEX) and Delta Exposure (DEX) analytics microservice running 24/7 on Synology NAS.",
    version="1.0.0"
)

# Enable CORS for cross-origin requests from web clients & Gemini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", summary="Health Check")
def health_check():
    """Health check endpoint for Docker container orchestration and Synology NAS monitoring."""
    return {"status": "ok"}

# Register master V1 router under /api/v1
app.include_router(api_router, prefix="/api/v1")

