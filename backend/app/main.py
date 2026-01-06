# backend/app/main.py - UPDATED
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
import logging

from .routes_api import router as routes_router
from .parcels_api import router as parcels_router
from .admin_api import router as admin_router
from .osrm import OSRMError, OSRMTimeoutError, OSRMNoRouteError

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Transport MVP API",
    description="System dopasowywania tras kurierskich do przesyłek",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")


# Global exception handlers
@app.exception_handler(OSRMTimeoutError)
async def osrm_timeout_handler(request: Request, exc: OSRMTimeoutError):
    logger.error(f"OSRM timeout: {str(exc)}")
    return JSONResponse(
        status_code=504,
        content={
            "detail": str(exc),
            "error_type": "osrm_timeout"
        }
    )


@app.exception_handler(OSRMNoRouteError)
async def osrm_no_route_handler(request: Request, exc: OSRMNoRouteError):
    logger.warning(f"OSRM no route: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "error_type": "osrm_no_route"
        }
    )


@app.exception_handler(OSRMError)
async def osrm_error_handler(request: Request, exc: OSRMError):
    logger.error(f"OSRM error: {str(exc)}")
    return JSONResponse(
        status_code=502,
        content={
            "detail": str(exc),
            "error_type": "osrm_error"
        }
    )


@app.get("/health")
def health():
    """Prosty healthcheck."""
    return {"status": "ok"}


@app.get("/route-test")
async def route_test():
    """Test OSRM - Warszawa → Łódź."""
    coords = "21.0122,52.2297;19.4550,51.7592"
    url = f"{OSRM_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)

    return r.json()


# Podłączenie routerów
app.include_router(routes_router)
app.include_router(parcels_router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Transport MVP API started")
    logger.info(f"📍 OSRM URL: {OSRM_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Transport MVP API shutting down")