"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/api_main.py
  Purpose : FastAPI application entry point.

  Run:
    uvicorn app.api_main:app --reload --port 8000
    (from smart-ai-surveillance/ root)

  Docs:
    http://localhost:8000/docs   ← Swagger UI
    http://localhost:8000/redoc  ← ReDoc

  Architecture:
    api_main.py         ← you are here (app factory + startup)
    core/config.py      ← settings from .env
    core/security.py    ← JWT helpers
    db/database.py      ← SQLite via SQLAlchemy
    db/init_db.py       ← table creation on startup
    models/user_model.py
    models/camera_model.py
    schemas/            ← Pydantic request/response models
    api/routes_auth.py
    api/routes_camera.py
    api/routes_tracking.py
    api/routes_alerts.py
    api/routes_vehicles.py
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
)

# ── App factory ───────────────────────────────────────────────

app = FastAPI(
    title       = "Smart AI Surveillance API",
    description = "Multi-camera AI surveillance — detection, tracking, ReID, alerts",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS — allow React dev server ────────────────────────────

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

# ── Routers ───────────────────────────────────────────────────

app.include_router(routes_auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(routes_camera.router,   prefix="/cameras",  tags=["Cameras"])
app.include_router(routes_tracking.router, prefix="/tracking", tags=["Tracking"])
app.include_router(routes_alerts.router,   prefix="/alerts",   tags=["Alerts"])
app.include_router(routes_vehicles.router, prefix="/vehicles", tags=["Vehicles"])

# ── Health check ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Smart AI Surveillance API"}

@app.get("/health", tags=["Health"])
def health():
    from app.cross_camera_tracker import GLOBAL_TRACKER
    from app.alert_system import ALERT_SYSTEM
    return {
        "status"          : "healthy",
        "global_ids"      : GLOBAL_TRACKER.active_count,
        "cross_cam"       : GLOBAL_TRACKER.multicamera_count,
        "unacked_alerts"  : ALERT_SYSTEM.unacknowledged_count(),
    }