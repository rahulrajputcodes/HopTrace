"""
HopTrace FastAPI application entry point — v2.

v2 additions:
  - WebSocket streaming endpoint /ws/telemetry
  - topology/risk, topology/history, /villages endpoints
  - Background telemetry streaming loop (started in lifespan)
  - Expanded 14-link, 3-village topology seeded on startup
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.explanations import router as explanations_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.lab import router as lab_router
from app.api.measurements import router as measurements_router
from app.api.subscribers import router as subscribers_router
from app.api.telemetry_ws import (
    router as telemetry_ws_router,
    start_streaming_loop,
    stop_streaming_loop,
)
from app.api.topology import router as topology_router
from app.api.topology_v2 import router as topology_v2_router
from app.config import settings
from app.db.init import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database, graph engine, and streaming loop."""
    # Initialize SQLite
    init_db(
        db_path=settings.sqlite_db_path,
        seed_demo=settings.seed_demo_subscribers,
        seed_incidents=settings.seed_demo_incidents,
    )

    # Seed the expanded 14-link topology
    if settings.topology_provider.lower() == "engine":
        try:
            from app.engine.facade import seed_topology
            seed_topology(force_in_memory=True)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize graph engine topology during startup: {exc}"
            ) from exc

    # Start WebSocket telemetry streaming background loop
    start_streaming_loop()

    yield

    # Shutdown
    stop_streaming_loop()


app = FastAPI(
    title="HopTrace API v2",
    version="2.0.0",
    description=(
        "HopTrace v2 — Advanced ISP network fault localisation and subscriber operations. "
        "Multi-village topology · EWMA anomaly detection · Sarvam AI structured reports · "
        "Live WebSocket telemetry streaming. hackFront India · Theme T3: Telecom and Connectivity."
    ),
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(health_router, prefix=API_PREFIX, tags=["health"])
app.include_router(topology_router, prefix=API_PREFIX, tags=["topology"])
app.include_router(topology_v2_router, prefix=API_PREFIX, tags=["topology"])
app.include_router(subscribers_router, prefix=API_PREFIX, tags=["subscribers"])
app.include_router(incidents_router, prefix=API_PREFIX, tags=["incidents"])
app.include_router(lab_router, prefix=API_PREFIX, tags=["lab"])
app.include_router(measurements_router, prefix=API_PREFIX, tags=["measurements"])
app.include_router(explanations_router, prefix=API_PREFIX, tags=["explanations"])
app.include_router(telemetry_ws_router, prefix=API_PREFIX, tags=["telemetry"])
app.include_router(telemetry_ws_router, tags=["realtime"])
