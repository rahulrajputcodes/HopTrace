"""
HopTrace FastAPI application entry point — v2.

v2 additions:
  - WebSocket streaming endpoint /ws/telemetry
  - topology/risk, topology/history, /villages endpoints
  - Background telemetry streaming loop (started in lifespan)
  - Expanded 14-link, 3-village topology seeded on startup
  - Agent heartbeat & status endpoints for blind-spot detection
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.explanations import router as explanations_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
# M3: Notification routes
from app.api.notify import router as notify_router
from app.api.lab import router as lab_router
from app.api.measurements import router as measurements_router
from app.api.probes import router as probes_router
from app.api.subscribers import router as subscribers_router
from app.api.telemetry_ws import (
    router as telemetry_ws_router,
    start_streaming_loop,
    stop_streaming_loop,
)
from app.api.topology import router as topology_router
from app.api.topology_v2 import router as topology_v2_router
from fastapi import Depends
from app.api.auth import router as auth_router
from app.auth.deps import enforce_rbac, require_agent_key
from app.middleware.rate_limit import RateLimitMiddleware
from app.config import settings
from app.db.init import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database, graph engine, and streaming loop."""
    if not settings.auth_disabled and not getattr(settings, "auth_secret", "").strip():
        raise RuntimeError("AUTH_DISABLED is false but AUTH_SECRET is not configured.")
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
class WebSocketAuthMiddleware:
    """Enforces token verification for WebSocket telemetry stream when auth is active."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket" and scope.get("path") in ("/ws/telemetry", "/api/v1/ws/telemetry"):
            if not getattr(settings, "auth_disabled", False):
                from urllib.parse import parse_qs
                from app.auth.security import decode_access_token
                query_string = scope.get("query_string", b"").decode("ascii")
                params = parse_qs(query_string)
                token_list = params.get("token", [])
                token = token_list[0] if token_list else None
                user = decode_access_token(token, getattr(settings, "auth_secret", ""))
                if user is None:
                    await send({"type": "websocket.close", "code": 4001, "reason": "Unauthorized"})
                    return
        await self.app(scope, receive, send)


app.add_middleware(WebSocketAuthMiddleware)
app.add_middleware(RateLimitMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

# Public (no authentication required)
app.include_router(health_router,        prefix=API_PREFIX, tags=["health"])
app.include_router(health_router,        tags=["health"])
app.include_router(auth_router,          prefix=API_PREFIX, tags=["auth"])

# Agent endpoints (authenticated via X-API-Key == ingest_api_key)
app.include_router(measurements_router,  prefix=API_PREFIX, tags=["measurements"], dependencies=[Depends(require_agent_key)])
app.include_router(probes_router,        prefix=API_PREFIX, tags=["probes"], dependencies=[Depends(require_agent_key)])
app.include_router(agents_router,        prefix=API_PREFIX, tags=["agents"], dependencies=[Depends(require_agent_key)])

# Protected endpoints (GET/HEAD: viewer | operator; Modifications: operator only)
app.include_router(topology_router,      prefix=API_PREFIX, tags=["topology"], dependencies=[Depends(enforce_rbac)])
app.include_router(topology_v2_router,   prefix=API_PREFIX, tags=["topology"], dependencies=[Depends(enforce_rbac)])   # risk, history, villages
app.include_router(subscribers_router,   prefix=API_PREFIX, tags=["subscribers"], dependencies=[Depends(enforce_rbac)])
app.include_router(incidents_router,     prefix=API_PREFIX, tags=["incidents"], dependencies=[Depends(enforce_rbac)])
app.include_router(notify_router,        prefix=API_PREFIX, tags=["notifications"], dependencies=[Depends(enforce_rbac)])
app.include_router(lab_router,           prefix=API_PREFIX, tags=["lab"], dependencies=[Depends(enforce_rbac)])
app.include_router(explanations_router,  prefix=API_PREFIX, tags=["explanations"], dependencies=[Depends(enforce_rbac)])

# Realtime WebSocket
app.include_router(telemetry_ws_router,  prefix=API_PREFIX, tags=["telemetry"])
app.include_router(telemetry_ws_router,  tags=["realtime"])


# --- Production SPA static file serving (Layout B: Single-Container PaaS) ---
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException

_FRONTEND_DIST = os.environ.get(
    "FRONTEND_DIST_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static"),
)
if not os.path.isdir(_FRONTEND_DIST):
    _alt_dist = os.path.join(os.getcwd(), "frontend", "dist")
    if os.path.isdir(_alt_dist):
        _FRONTEND_DIST = _alt_dist

if os.path.isdir(_FRONTEND_DIST):
    _assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
