from fastapi import APIRouter
from app.api.v1.endpoints import gexdex

api_router = APIRouter()

# Register Skill 1: GEX & DEX Options Exposure
api_router.include_router(gexdex.router, prefix="/gexdex", tags=["GEX/DEX Options Skill"])

# Future skills can be included here easily:
# api_router.include_router(ibkr.router, prefix="/ibkr", tags=["IBKR Market Data Skill"])
# api_router.include_router(darkpool.router, prefix="/darkpool", tags=["Darkpool Flow Skill"])
