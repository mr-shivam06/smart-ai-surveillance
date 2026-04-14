"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/api_main.py
=============================================================
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.init_db import init_db
from app.api import (
    routes_auth,
    routes_camera,
    routes_tracking,
    routes_alerts,
    routes_vehicles,
    routes_stream,
)

# ── App factory ───────────────────────────────────────────────

app = FastAPI(
    title       = "Smart AI Surveillance API",
    description = "Multi-camera AI surveillance — detection, tracking, ReID, alerts",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:5173", "http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Startup (NO CAMERA AUTO START) ────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    print("[INFO] Backend started (no cameras auto-started)")


# ── REST routers ──────────────────────────────────────────────

app.include_router(routes_auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(routes_camera.router,   prefix="/cameras",  tags=["Cameras"])
app.include_router(routes_tracking.router, prefix="/tracking", tags=["Tracking"])
app.include_router(routes_alerts.router,   prefix="/alerts",   tags=["Alerts"])
app.include_router(routes_vehicles.router, prefix="/vehicles", tags=["Vehicles"])

# ── WebSocket stream router ───────────────────────────────────

app.include_router(routes_stream.router,   prefix="/stream",   tags=["Stream"])

# ── Health check ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Smart AI Surveillance API"}


@app.get("/health", tags=["Health"])
def health():
    from app.cross_camera_tracker import GLOBAL_TRACKER
    from app.alert_system import ALERT_SYSTEM
    from app.stream_bridge import STREAM_BRIDGE

    return {
        "status"          : "healthy",
        "global_ids"      : GLOBAL_TRACKER.active_count,
        "cross_cam"       : GLOBAL_TRACKER.multicamera_count,
        "unacked_alerts"  : ALERT_SYSTEM.unacknowledged_count(),
        "streaming_cams"  : STREAM_BRIDGE.active_camera_ids(),
    }