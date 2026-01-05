# backend\app\main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

from .routes_api import router as routes_router
from .parcels_api import router as parcels_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/route-test")
async def route_test():
    coords = "21.0122,52.2297;19.4550,51.7592"
    url = f"{OSRM_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)

    return r.json()


# PODŁĄCZENIE ROUTERA
app.include_router(routes_router)
app.include_router(parcels_router)

