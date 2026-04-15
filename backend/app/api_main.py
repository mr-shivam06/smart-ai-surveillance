"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/api_main.py
  Purpose : FastAPI application entry point.

  Run from backend/ folder:
    uvicorn app.api_main:app --reload --port 8000

  STARTUP BEHAVIOUR:
    On startup, reads all active cameras from the database
    and starts their AI pipeline threads automatically.
    This means you don't need to toggle each camera after
    restarting the server — they resume automatically.
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

# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()

    # Auto-start all cameras that were active when server last ran
    try:
        from app.db.database import SessionLocal
        from app.models.camera_model import Camera
        from app.camera_worker import start_camera

        db = SessionLocal()
        active_cams = db.query(Camera).filter(Camera.is_active == True).all()
        db.close()

        if active_cams:
            print(f"[Startup] Auto-starting {len(active_cams)} active camera(s)...")
            for cam in active_cams:
                start_camera(cam.id, cam.source)
                print(f"[Startup]   → Camera {cam.id} '{cam.name}' (source={cam.source!r})")
        else:
            print("[Startup] No active cameras in DB. Add cameras via the dashboard.")

    except Exception as e:
        print(f"[Startup] Camera auto-start failed: {e}")

# ── REST routers ──────────────────────────────────────────────
app.include_router(routes_auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(routes_camera.refresh_router, tags=["Cameras"])
app.include_router(routes_camera.router,   prefix="/cameras",  tags=["Cameras"])
app.include_router(routes_tracking.router, prefix="/tracking", tags=["Tracking"])
app.include_router(routes_alerts.router,   prefix="/alerts",   tags=["Alerts"])
app.include_router(routes_vehicles.router, prefix="/vehicles", tags=["Vehicles"])

# ── WebSocket stream ──────────────────────────────────────────
# ws://localhost:8000/stream/{camera_id}?token=<jwt>
app.include_router(routes_stream.router,   prefix="/stream",   tags=["Stream"])

# ── Health ────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Smart AI Surveillance API"}

@app.get("/health", tags=["Health"])
def health():
    from app.cross_camera_tracker import GLOBAL_TRACKER
    from app.alert_system import ALERT_SYSTEM
    from app.stream_bridge import STREAM_BRIDGE
    return {
        "status"         : "healthy",
        "global_ids"     : GLOBAL_TRACKER.active_count,
        "cross_cam"      : GLOBAL_TRACKER.multicamera_count,
        "unacked_alerts" : ALERT_SYSTEM.unacknowledged_count(),
        "streaming_cams" : STREAM_BRIDGE.active_camera_ids(),
    }
