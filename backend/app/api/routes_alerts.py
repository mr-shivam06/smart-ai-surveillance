"""
=============================================================
  File : backend/app/api/routes_alerts.py
  Purpose : Alert management endpoints

  Endpoints:
    GET  /alerts              → recent alerts (filterable)
    POST /alerts/acknowledge  → acknowledge an alert
    GET  /alerts/count        → unacknowledged count
    GET  /alerts/types        → all alert types
=============================================================
"""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.core.security import get_current_user
from app.schemas.schemas import AlertOut, AcknowledgeRequest

router = APIRouter()


@router.get("", response_model=List[AlertOut])
def get_alerts(
    limit        : int            = Query(50,  ge=1, le=200),
    since        : float          = Query(0.0, ge=0),
    alert_type   : Optional[str]  = Query(None),
    camera_id    : int            = Query(-1),
    current_user : dict           = Depends(get_current_user),
):
    """
    Get recent alerts. Supports filtering by type and camera.

    Examples:
      GET /alerts?limit=20
      GET /alerts?alert_type=ACCIDENT_DETECTED
      GET /alerts?camera_id=1
    """
    from app.alert_system import ALERT_SYSTEM
    return ALERT_SYSTEM.get_recent(
        limit      = limit,
        since      = since,
        alert_type = alert_type or "",
        camera_id  = camera_id,
    )


@router.post("/acknowledge")
def acknowledge_alert(
    req          : AcknowledgeRequest,
    current_user : dict = Depends(get_current_user),
):
    """Mark an alert as acknowledged."""
    from app.alert_system import ALERT_SYSTEM
    success = ALERT_SYSTEM.acknowledge(req.alert_id)
    if not success:
        return {"success": False, "message": "Alert not found"}
    return {"success": True, "alert_id": req.alert_id}


@router.get("/count")
def alert_count(current_user: dict = Depends(get_current_user)):
    """Unacknowledged alert count — for dashboard badge."""
    from app.alert_system import ALERT_SYSTEM
    return {"unacknowledged": ALERT_SYSTEM.unacknowledged_count()}


@router.get("/types")
def alert_types(current_user: dict = Depends(get_current_user)):
    """All supported alert types and their severity."""
    return {
        "types": [
            {"type": "ACCIDENT_DETECTED",   "severity": "CRITICAL", "cooldown_s": 0},
            {"type": "AMBULANCE_DETECTED",  "severity": "CRITICAL", "cooldown_s": 15},
            {"type": "FIRE_DETECTED",       "severity": "CRITICAL", "cooldown_s": 0},
            {"type": "SMOKE_DETECTED",      "severity": "HIGH",     "cooldown_s": 5},
            {"type": "CROWD_DETECTED",      "severity": "HIGH",     "cooldown_s": 30},
            {"type": "HEAVY_TRAFFIC",       "severity": "MEDIUM",   "cooldown_s": 30},
            {"type": "CONGESTION",          "severity": "MEDIUM",   "cooldown_s": 30},
            {"type": "LOITERING",           "severity": "HIGH",     "cooldown_s": 60},
            {"type": "ZONE_ENTER",          "severity": "INFO",     "cooldown_s": 5},
            {"type": "ZONE_EXIT",           "severity": "INFO",     "cooldown_s": 5},
        ]
    }