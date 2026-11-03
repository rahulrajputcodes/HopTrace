"""
HopTrace FastAPI application entry point.

Responsibilities:
  - Milestone 1: Health, topology endpoints, and CORS middleware.
  - Milestone 2: SQLite database initialization, subscriber listing, and payment reminder recording.
  - Milestone 3: Incident retrieval and affected-subscriber endpoints.

Ownership:
  - Member 1 owns app/engine/ (Neo4j, graph engine).
  - Member 2 owns app/api/, app/providers/, app/schemas/, app/db/ (this file).
  - Member 3 owns frontend/.
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
from app.api.telemetry_ws import router as telemetry_ws_router
from app.api.topology import router as topology_router
from app.api.topology_v2 import router as topology_v2_router
from app.config import settings
from app.db.init import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize SQLite database and graph engine on startup."""
    init_db(
        db_path=settings.sqlite_db_path,
        seed_demo=settings.seed_demo_subscribers,
        seed_incidents=settings.seed_demo_incidents,
    )

    if settings.topology_provider.lower() == "engine":
        try:
            from app.engine.facade import seed_topology

            seed_topology(force_in_memory=True)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize graph engine topology during startup: {exc}"
            ) from exc

    yield


app = FastAPI(
    title="HopTrace API",
    version=settings.app_version,
    description=(
        "HopTrace – ISP network fault localisation and subscriber operations. "
        "hackFront India · Theme T3: Telecom and Connectivity."
    ),
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow only the origins listed in CORS_ORIGINS (default: local Vite dev server).
# Do NOT use allow_origins=["*"] – that would expose the API to any browser tab.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
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
